#
# This file is part of VIRL 2
# Copyright (c) 2019-2026, Cisco Systems, Inc.
# All rights reserved.
#
# Python bindings for the Cisco VIRL 2 Network Simulation Platform
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any, ClassVar

from ..utils import UNCHANGED, _Sentinel, check_stale, get_url_from_template, locked
from ..utils import property_s as property

if TYPE_CHECKING:
    import httpx

    from .interface import Interface
    from .lab import Lab
    from .node import Node

_LOGGER = logging.getLogger(__name__)


class Link:
    """A VIRL2 network link connecting two interfaces on different nodes."""

    _URL_TEMPLATES: ClassVar[dict[str, str]] = {
        "link": "{lab}/links/{id}",
        "check_if_converged": "{lab}/links/{id}/check_if_converged",
        "state": "{lab}/links/{id}/state",
        "start": "{lab}/links/{id}/state/start",
        "stop": "{lab}/links/{id}/state/stop",
        "condition": "{lab}/links/{id}/condition",
        "capture_start": "{lab}/links/{id}/capture/start",
        "capture_stop": "{lab}/links/{id}/capture/stop",
        "capture_status": "{lab}/links/{id}/capture/status",
        "pcap_file": "pcap/{id}",
        "pcap_packets": "pcap/{id}/packets",
        "pcap_packet": "pcap/{id}/packets/{packet_id}",
    }

    def __init__(
        self,
        lab: Lab,
        lid: str,
        iface_a: Interface,
        iface_b: Interface,
        label: str | None = None,
    ) -> None:
        """
        A VIRL2 network link between two nodes, connecting
        to two interfaces on these nodes.

        :param lab: The lab object to which the link belongs.
        :param lid: The ID of the link.
        :param iface_a: The first interface of the link.
        :param iface_b: The second interface of the link.
        :param label: The label of the link.
        """
        self._id = lid
        self._interface_a = iface_a
        self._interface_b = iface_b
        self._label = label
        self._lab = lab
        self._session: httpx.Client = lab._session
        self._state: str | None = None
        # When the link is removed on the server, this link object is marked stale
        # and can no longer be interacted with - the user should discard it
        self._stale = False
        self.statistics = {
            "readbytes": 0,
            "readpackets": 0,
            "writebytes": 0,
            "writepackets": 0,
        }

    def __str__(self) -> str:
        """Return user-friendly link description.

        :returns: Link label with stale marker when applicable.
        """
        return f"Link: {self._label}{' (STALE)' if self._stale else ''}"

    def __repr__(self) -> str:
        """Return debug representation for this link.

        :returns: Representation containing lab, id, and label.
        """
        return (
            f"{self.__class__.__name__}("
            f"{str(self._lab)!r}, "
            f"{self._id!r}, "
            f"{self._label!r})"
        )

    def __eq__(self, other: object) -> bool:
        """Compare links by identifier.

        :param other: Object to compare against.
        :returns: True when other is a link with same id.
        """
        if not isinstance(other, Link):
            return False
        return self._id == other._id

    def __hash__(self) -> int:
        """Return hash based on link identifier.

        :returns: Stable hash value for this link id.
        """
        return hash(self._id)

    def _url_for(self, endpoint: str, **kwargs: str) -> str:
        """
        Generate the URL for a given API endpoint.

        :param endpoint: The desired endpoint.
        :param kwargs: Keyword arguments used to format the URL.
        :returns: The formatted URL.
        """
        # PCAP endpoints live at /api/v0/pcap/... (a sibling of /api/v0/labs/...),
        # so they don't need the {lab} prefix. All other Link endpoints are
        # nested under the lab URL.
        if not endpoint.startswith("pcap"):
            kwargs["lab"] = self._lab._url_for("lab")
        kwargs["id"] = self._id
        return get_url_from_template(endpoint, self._URL_TEMPLATES, kwargs)

    @property
    def lab(self) -> Lab:
        """
        Return the lab of the link.

        :returns: The Lab instance this link belongs to.
        """
        return self._lab

    @property
    def id(self) -> str:
        """
        Return the ID of the link.

        :returns: The link ID.
        """
        return self._id

    @property
    def interface_a(self) -> Interface:
        """
        Return the first interface of the link.

        :returns: The first Interface of the link.
        """
        return self._interface_a

    @property
    def interface_b(self) -> Interface:
        """
        Return the second interface of the link.

        :returns: The second Interface of the link.
        """
        return self._interface_b

    @property
    @locked
    def state(self) -> str | None:
        """
        Return the current state of the link.

        :returns: The link state, or None if unknown.
        """
        self._lab.sync_states_if_outdated()
        if self._state is None:
            url = self._url_for("link")
            self._state = self._session.get(url).json()["state"]
        return self._state

    @property
    def readbytes(self) -> int:
        """
        Return the number of read bytes on the link.

        :returns: The number of read bytes.
        """
        self._lab.sync_statistics_if_outdated()
        return self.statistics["readbytes"]

    @property
    def readpackets(self) -> int:
        """
        Return the number of read packets on the link.

        :returns: The number of read packets.
        """
        self._lab.sync_statistics_if_outdated()
        return self.statistics["readpackets"]

    @property
    def writebytes(self) -> int:
        """
        Return the number of written bytes on the link.

        :returns: The number of written bytes.
        """
        self._lab.sync_statistics_if_outdated()
        return self.statistics["writebytes"]

    @property
    def writepackets(self) -> int:
        """
        Return the number of written packets on the link.

        :returns: The number of written packets.
        """
        self._lab.sync_statistics_if_outdated()
        return self.statistics["writepackets"]

    @property
    def node_a(self) -> Node:
        """
        Return the first node connected to the link.

        :returns: The first Node connected to the link.
        """
        return self.interface_a.node

    @property
    def node_b(self) -> Node:
        """
        Return the second node connected to the link.

        :returns: The second Node connected to the link.
        """
        return self.interface_b.node

    @property
    @locked
    def nodes(self) -> tuple[Node, Node]:
        """
        Return the nodes connected by the link.

        :returns: Tuple of (node_a, node_b).
        """
        return self.node_a, self.node_b

    @property
    @locked
    def interfaces(self) -> tuple[Interface, Interface]:
        """
        Return the interfaces connected by the link.

        :returns: Tuple of (interface_a, interface_b).
        """
        return self.interface_a, self.interface_b

    @property
    def label(self) -> str | None:
        """
        Return the label of the link.

        :returns: The link label, or None if unset.
        """
        return self._label

    @locked
    def as_dict(self) -> dict[str, str]:
        """
        Convert the link object to a dictionary representation.

        :returns: A dictionary representation of the link object.
        """
        return {
            "id": self._id,
            "interface_a": self.interface_a.id,
            "interface_b": self.interface_b.id,
        }

    def remove(self) -> None:
        """
        Remove the link from the lab.

        """
        self._lab.remove_link(self)

    @check_stale
    def _remove_on_server(self) -> None:
        """
        Remove the link on the server.

        """
        _LOGGER.info("Removing link %s", self)
        url = self._url_for("link")
        self._session.delete(url)

    def wait_until_converged(
        self, max_iterations: int | None = None, wait_time: int | None = None
    ) -> None:
        """
        Wait until the link has converged.

        :param max_iterations: The maximum number of iterations to wait for convergence.
        :param wait_time: The time to wait between iterations in seconds.
        :raises RuntimeError: If the link does not converge within the specified number
            of iterations.
        """
        _LOGGER.info("Waiting for link %s to converge", self._id)
        max_iter = (
            self._lab.wait_max_iterations if max_iterations is None else max_iterations
        )
        wait_time = self._lab.wait_time if wait_time is None else wait_time
        for index in range(max_iter):
            converged = self.has_converged()
            if converged:
                _LOGGER.info("Link %s has converged", self._id)
                return

            if index % 10 == 0:
                _LOGGER.info(
                    "Link has not converged, attempt %s/%s, waiting...",
                    index,
                    max_iter,
                )
            time.sleep(wait_time)

        msg = f"Link {self._id} has not converged, maximum tries {max_iter} exceeded"
        _LOGGER.error(msg)
        # after maximum retries are exceeded and link has not converged
        # error must be raised - it makes no sense to just log info
        # and let client fail with something else if wait is explicitly
        # specified
        raise RuntimeError(msg)

    @check_stale
    def has_converged(self) -> bool:
        """
        Check if the link has converged.

        :returns: True if the link has converged, False otherwise.
        """
        url = self._url_for("check_if_converged")
        return self._session.get(url).json()

    @check_stale
    def start(self, wait: bool | None = None) -> None:
        """
        Start the link.

        :param wait: Whether to wait for convergence after starting the link.
        """
        url = self._url_for("start")
        self._session.put(url)
        if self._lab.need_to_wait(wait):
            self.wait_until_converged()

    @check_stale
    def stop(self, wait: bool | None = None) -> None:
        """
        Stop the link.

        :param wait: Whether to wait for convergence after stopping the link.
        """
        url = self._url_for("stop")
        self._session.put(url)
        if self._lab.need_to_wait(wait):
            self.wait_until_converged()

    @check_stale
    def set_condition(
        self,
        bandwidth: int | None | _Sentinel = UNCHANGED,
        latency: int | None | _Sentinel = UNCHANGED,
        jitter: int | None | _Sentinel = UNCHANGED,
        loss: float | None | _Sentinel = UNCHANGED,
        **kwargs: float | int | bool | None,
    ) -> None:
        """
        Set the conditioning parameters for the link.

        :param bandwidth: The desired bandwidth in kbps (0-10000000).
        :param latency: The desired latency in ms (0-10000).
        :param jitter: The desired jitter in ms (0-10000).
        :param loss: The desired packet loss in percent (0-100).
        :param kwargs: Additional parameters. See below.

        :Keyword Arguments:
            - enabled: Whether the link conditioning is enabled.
            - delay_corr: The desired packet loss correlation in percent (0-100).
            - limit: The desired maximum delay in ms (0-10000).
            - loss_corr: The desired packet loss correlation in percent (0-100).
            - gap: The desired gap between packets in ms (0-10000).
            - duplicate: The desired probability of duplicates in percent (0-100).
            - duplicate_corr: The desired correlation of duplicates in percent (0-100).
            - reorder_prob: The desired probability of re-orders in percent (0-100).
            - reorder_corr: The desired re-order correlation in percent (0-100).
            - corrupt_prob: The desired corruption probability in percent (0-100).
            - corrupt_corr: The desired corruption correlation in percent (0-100).
        """
        url = self._url_for("condition")
        data: dict[str, float | int | bool] = {}
        if bandwidth is not UNCHANGED:
            data["bandwidth"] = bandwidth
        if latency is not UNCHANGED:
            data["latency"] = latency
        if jitter is not UNCHANGED:
            data["jitter"] = jitter
        if loss is not UNCHANGED:
            data["loss"] = loss
        expected_params = [
            "enabled",
            "delay_corr",
            "limit",
            "loss_corr",
            "gap",
            "duplicate",
            "duplicate_corr",
            "reorder_prob",
            "reorder_corr",
            "corrupt_prob",
            "corrupt_corr",
        ]
        for key, value in kwargs.items():
            if key in expected_params:
                data[key] = value
        self._session.patch(url, json=data)

    @check_stale
    def get_condition(self) -> dict[str, Any]:
        """
        Get the current conditioning parameters for the link.

        :returns: A dictionary containing the current conditioning parameters.
        """
        url = self._url_for("condition")
        return self._session.get(url).json()

    @check_stale
    def remove_condition(self) -> None:
        """
        Remove the link conditioning.

        """
        url = self._url_for("condition")
        self._session.delete(url)

    def set_condition_by_name(self, name: str) -> None:
        """
        Apply predefined link condition settings by name.

        A convenience function to provide commonly used link condition settings
        for various link types.

        Inspired by:  https://github.com/tylertreat/comcast

        ========= ============ =========  ========
        Name      Latency (ms) Bandwidth  Loss (%)
        ========= ============ =========  ========
        gprs               500   50 kbps       2.0
        edge               300  250 kbps       1.5
        3g                 250  750 kbps       1.5
        dialup             185   40 kbps       2.0
        dsl1                70    2 mbps       2.0
        dsl2                40    8 mbps       0.5
        wifi                10   30 mbps       0.1
        wan1                80  256 kbps       0.2
        wan2                80  100 mbps       0.2
        satellite         1500    1 mbps       0.2
        ========= ============ =========  ========

        :param name: The name of the predefined link condition.
        :raises ValueError: If the given name is not a known predefined condition.
        """
        options = {
            "gprs": (500, 50, 2.0),
            "edge": (300, 250, 1.5),
            "3g": (250, 750, 1.5),
            "dialup": (185, 40, 2.0),
            "dsl1": (70, 2000, 2.0),
            "dsl2": (40, 8000, 0.5),
            "wifi": (40, 30000, 0.2),
            "wan1": (80, 256, 0.2),
            "wan2": (80, 100000, 0.2),
            "satellite": (1500, 1000, 0.2),
        }

        if name not in options:
            msg = (
                f"Unknown condition name: '{name}', "
                f"known values: '{', '.join(sorted(options))}'"
            )
            _LOGGER.error(msg)
            raise ValueError(msg)

        latency, bandwidth, loss = options[name]
        self.set_condition(bandwidth=bandwidth, latency=latency, loss=loss)

    @check_stale
    def start_capture(
        self,
        maxpackets: int | None = None,
        maxtime: int | None = None,
        bpfilter: str | None = None,
        encap: str = "ethernet",
    ) -> dict[str, Any]:
        """
        Start a packet capture on this link.

        :param maxpackets: Maximum number of packets to capture (1-1000000). If None, server sets default.
        :param maxtime: Maximum time in seconds to capture (1-86400). If None, server sets default.
        :param bpfilter: Berkeley packet filter string (1-128 chars).
        :param encap: Link encapsulation type.
        :returns: Dictionary containing the capture status and configuration.
        """
        url = self._url_for("capture_start")
        data: dict[str, str | int] = {"encap": encap}

        if maxpackets is not None:
            data["maxpackets"] = maxpackets
        if maxtime is not None:
            data["maxtime"] = maxtime
        if bpfilter is not None:
            data["bpfilter"] = bpfilter

        _LOGGER.info("Starting packet capture on link %s", self._id)
        return self._session.put(url, json=data).json()

    @check_stale
    def stop_capture(self) -> None:
        """
        Stop the packet capture on this link.

        """
        url = self._url_for("capture_stop")
        _LOGGER.info("Stopping packet capture on link %s", self._id)
        self._session.put(url)

    @check_stale
    def capture_status(self) -> dict[str, Any]:
        """
        Get the current packet capture status for this link.

        :returns: Dictionary containing capture configuration, start time, and packet count.
        """
        url = self._url_for("capture_status")
        return self._session.get(url).json()

    def download_capture(self) -> bytes:
        """
        Download the PCAP file for this link's last capture.

        :returns: The PCAP file content as bytes.
        """
        url = self._url_for("pcap_file")
        _LOGGER.info("Downloading PCAP for link %s", self._id)
        return self._session.get(url).content

    def get_capture_packets(self) -> list[dict[str, Any]]:
        """
        Get a list of all captured packets in decoded format from last capture.

        :returns: List of packet dictionaries with decoded packet information.
        """
        url = self._url_for("pcap_packets")
        _LOGGER.info("Getting packet list for link %s", self._id)
        return self._session.get(url).json()

    def get_capture_packet(self, packet_id: int) -> dict[str, Any]:
        """
        Get a specific packet from the last capture in decoded format.

        :param packet_id: The ID of the packet (1-based index).
        :returns: Dictionary containing the decoded packet information.
        """
        url = self._url_for("pcap_packet", packet_id=packet_id)
        _LOGGER.info("Downloading packet %s for link %s", packet_id, self._id)
        return self._session.get(url).json()
