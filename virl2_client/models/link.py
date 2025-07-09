#
# This file is part of VIRL 2
# Copyright (c) 2019-2025, Cisco Systems, Inc.
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
import warnings
from typing import TYPE_CHECKING

from ..utils import check_stale, get_url_from_template, locked
from ..utils import property_s as property

if TYPE_CHECKING:
    import httpx

    from .interface import Interface
    from .lab import Lab
    from .node import Node

_LOGGER = logging.getLogger(__name__)


class Link:
    _URL_TEMPLATES = {
        "link": "{lab}/links/{id}",
        "check_if_converged": "{lab}/links/{id}/check_if_converged",
        "state": "{lab}/links/{id}/state",
        "start": "{lab}/links/{id}/state/start",
        "stop": "{lab}/links/{id}/state/stop",
        "condition": "{lab}/links/{id}/condition",
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

    def __str__(self):
        return f"Link: {self._label}{' (STALE)' if self._stale else ''}"

    def __repr__(self):
        return (
            f"{self.__class__.__name__}("
            f"{str(self._lab)!r}, "
            f"{self._id!r}, "
            f"{self._label!r})"
        )

    def __eq__(self, other: object):
        if not isinstance(other, Link):
            return False
        return self._id == other._id

    def __hash__(self):
        return hash(self._id)

    def _url_for(self, endpoint, **kwargs):
        """
        Generate the URL for a given API endpoint.

        :param endpoint: The desired endpoint.
        :param **kwargs: Keyword arguments used to format the URL.
        :returns: The formatted URL.
        """
        kwargs["lab"] = self._lab._url_for("lab")
        kwargs["id"] = self.id
        return get_url_from_template(endpoint, self._URL_TEMPLATES, kwargs)

    @property
    def lab(self) -> Lab:
        """Return the lab of the link."""
        return self._lab

    @property
    def id(self) -> str:
        """Return the ID of the link."""
        return self._id

    @property
    def interface_a(self) -> Interface:
        """Return the first interface of the link."""
        return self._interface_a

    @property
    def interface_b(self) -> Interface:
        """Return the second interface of the link."""
        return self._interface_b

    @property
    @locked
    def state(self) -> str | None:
        """Return the current state of the link."""
        self._lab.sync_states_if_outdated()
        if self._state is None:
            url = self._url_for("link")
            self._state = self._session.get(url).json()["state"]
        return self._state

    @property
    def readbytes(self) -> int:
        """Return the number of read bytes on the link."""
        self._lab.sync_statistics_if_outdated()
        return self.statistics["readbytes"]

    @property
    def readpackets(self) -> int:
        """Return the number of read packets on the link."""
        self._lab.sync_statistics_if_outdated()
        return self.statistics["readpackets"]

    @property
    def writebytes(self) -> int:
        """Return the number of written bytes on the link."""
        self._lab.sync_statistics_if_outdated()
        return self.statistics["writebytes"]

    @property
    def writepackets(self) -> int:
        """Return the number of written packets on the link."""
        self._lab.sync_statistics_if_outdated()
        return self.statistics["writepackets"]

    @property
    def node_a(self) -> Node:
        """Return the first node connected to the link."""
        return self.interface_a.node

    @property
    def node_b(self) -> Node:
        """Return the second node connected to the link."""
        return self.interface_b.node

    @property
    @locked
    def nodes(self) -> tuple[Node, Node]:
        """Return the nodes connected by the link."""
        return self.node_a, self.node_b

    @property
    @locked
    def interfaces(self) -> tuple[Interface, Interface]:
        """Return the interfaces connected by the link."""
        return self.interface_a, self.interface_b

    @property
    def label(self) -> str | None:
        """Return the label of the link."""
        return self._label

    @locked
    def as_dict(self) -> dict[str, str]:
        """
        Convert the link object to a dictionary representation.

        :returns: A dictionary representation of the link object.
        """
        return {
            "id": self.id,
            "interface_a": self.interface_a.id,
            "interface_b": self.interface_b.id,
        }

    def remove(self):
        """Remove the link from the lab."""
        self._lab.remove_link(self)

    @check_stale
    def _remove_on_server(self) -> None:
        _LOGGER.info(f"Removing link {self}")
        url = self._url_for("link")
        self._session.delete(url)

    def remove_on_server(self) -> None:
        """
        DEPRECATED: Use `.remove()` instead.
        (Reason: was never meant to be public, removing only on server is not useful)

        Remove the link on the server.
        """
        warnings.warn(
            "'Link.remove_on_server()' is deprecated. Use '.remove()' instead.",
        )
        self._remove_on_server()

    def wait_until_converged(
        self, max_iterations: int | None = None, wait_time: int | None = None
    ) -> None:
        """
        Wait until the link has converged.

        :param max_iterations: The maximum number of iterations to wait for convergence.
        :param wait_time: The time to wait between iterations.
        :raises RuntimeError: If the link does not converge within the specified number
            of iterations.
        """
        _LOGGER.info(f"Waiting for link {self.id} to converge")
        max_iter = (
            self._lab.wait_max_iterations if max_iterations is None else max_iterations
        )
        wait_time = self._lab.wait_time if wait_time is None else wait_time
        for index in range(max_iter):
            converged = self.has_converged()
            if converged:
                _LOGGER.info(f"Link {self.id} has converged")
                return

            if index % 10 == 0:
                _LOGGER.info(
                    f"Link has not converged, attempt {index}/{max_iter}, waiting..."
                )
            time.sleep(wait_time)

        msg = f"Link {self.id} has not converged, maximum tries {max_iter} exceeded"
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
        self, bandwidth: int, latency: int, jitter: int, loss: float
    ) -> None:
        """
        Set the conditioning parameters for the link.

        :param bandwidth: The desired bandwidth in kbps (0-10000000).
        :param latency: The desired latency in ms (0-10000).
        :param jitter: The desired jitter in ms (0-10000).
        :param loss: The desired packet loss percentage (0-100).
        """
        url = self._url_for("condition")
        data = {
            "bandwidth": bandwidth,
            "latency": latency,
            "jitter": jitter,
            "loss": loss,
        }
        self._session.patch(url, json=data)

    @check_stale
    def get_condition(self) -> dict:
        """
        Get the current conditioning parameters for the link.

        :returns: A dictionary containing the current conditioning parameters.
        """
        url = self._url_for("condition")
        condition = self._session.get(url).json()
        keys = ["bandwidth", "latency", "jitter", "loss"]
        return {k: v for k, v in condition.items() if k in keys}

    @check_stale
    def remove_condition(self) -> None:
        """Remove the link conditioning."""
        url = self._url_for("condition")
        self._session.delete(url)

    def set_condition_by_name(self, name: str) -> None:
        """
        A convenience function to provide
        some commonly used link condition settings for various link types.

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
        self.set_condition(bandwidth, latency, 0, loss)
