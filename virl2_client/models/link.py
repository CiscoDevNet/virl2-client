#
# This file is part of VIRL 2
# Copyright (c) 2019-2023, Cisco Systems, Inc.
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
from functools import total_ordering
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    import httpx

    from .interface import Interface
    from .lab import Lab
    from .node import Node

_LOGGER = logging.getLogger(__name__)


@total_ordering
class Link:
    def __init__(
        self,
        lab: Lab,
        lid: str,
        iface_a: Interface,
        iface_b: Interface,
        label: Optional[str] = None,
    ) -> None:
        """
        A VIRL2 network link between two nodes, connecting
        to two interfaces on these nodes.

        :param lab: the lab object
        :param lid: the link ID
        :param iface_a: the first interface of the link
        :param iface_b: the second interface of the link
        :param label: the link label
        """
        self.id = lid
        self.interface_a = iface_a
        self.interface_b = iface_b
        self._label = label
        self.lab = lab
        self._session: httpx.Client = lab.session
        self._state: Optional[str] = None
        self.statistics = {
            "readbytes": 0,
            "readpackets": 0,
            "writebytes": 0,
            "writepackets": 0,
        }

    @property
    def state(self) -> Optional[str]:
        self.lab.sync_states_if_outdated()
        return self._state

    @property
    def readbytes(self) -> int:
        self.lab.sync_statistics_if_outdated()
        return self.statistics["readbytes"]

    @property
    def readpackets(self) -> int:
        self.lab.sync_statistics_if_outdated()
        return self.statistics["readpackets"]

    @property
    def writebytes(self) -> int:
        self.lab.sync_statistics_if_outdated()
        return self.statistics["writebytes"]

    @property
    def writepackets(self) -> int:
        self.lab.sync_statistics_if_outdated()
        return self.statistics["writepackets"]

    def __str__(self):
        return "Link: {}".format(self.id)

    def __repr__(self):
        return "{}({!r}, {!r}, {!r}, {!r}, {!r})".format(
            self.__class__.__name__,
            str(self.lab),
            self.id,
            self.interface_a,
            self.interface_b,
            self.label,
        )

    def __eq__(self, other: object):
        if not isinstance(other, Link):
            return False
        return self.id == other.id

    def __lt__(self, other: object):
        if not isinstance(other, Link):
            return False
        return int(self.id) < int(other.id)

    def __hash__(self):
        return hash(self.id)

    @property
    def node_a(self) -> Node:
        self.lab.sync_topology_if_outdated()
        return self.interface_a.node

    @property
    def node_b(self) -> Node:
        self.lab.sync_topology_if_outdated()
        return self.interface_b.node

    @property
    def nodes(self) -> tuple[Node, Node]:
        """Return nodes this link connects."""
        self.lab.sync_topology_if_outdated()
        return self.node_a, self.node_b

    @property
    def interfaces(self) -> tuple[Interface, Interface]:
        self.lab.sync_topology_if_outdated()
        return self.interface_a, self.interface_b

    @property
    def label(self) -> Optional[str]:
        self.lab.sync_topology_if_outdated()
        return self._label

    def as_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "interface_a": self.interface_a.id,
            "interface_b": self.interface_b.id,
        }

    @property
    def lab_base_url(self) -> str:
        return self.lab.lab_base_url

    @property
    def base_url(self) -> str:
        return self.lab_base_url + "/links/{}".format(self.id)

    def remove_on_server(self) -> None:
        _LOGGER.info("Removing link %s", self)
        url = self.base_url
        self._session.delete(url)

    def wait_until_converged(
        self, max_iterations: Optional[int] = None, wait_time: Optional[int] = None
    ) -> None:
        _LOGGER.info("Waiting for link %s to converge", self.id)
        max_iter = (
            self.lab.wait_max_iterations if max_iterations is None else max_iterations
        )
        wait_time = self.lab.wait_time if wait_time is None else wait_time
        for index in range(max_iter):
            converged = self.has_converged()
            if converged:
                _LOGGER.info("Link %s has converged", self.id)
                return

            if index % 10 == 0:
                _LOGGER.info(
                    "Link has not converged, attempt %s/%s, waiting...",
                    index,
                    max_iter,
                )
            time.sleep(wait_time)

        msg = "Link %s has not converged, maximum tries %s exceeded" % (
            self.id,
            max_iter,
        )
        _LOGGER.error(msg)
        # after maximum retries are exceeded and link has not converged
        # error must be raised - it makes no sense to just log info
        # and let client fail with something else if wait is explicitly
        # specified
        raise RuntimeError(msg)

    def has_converged(self) -> bool:
        url = self.base_url + "/check_if_converged"
        converged = self._session.get(url).json()
        return converged

    def start(self, wait: Optional[bool] = None) -> None:
        url = self.base_url + "/state/start"
        self._session.put(url)
        if self.lab.need_to_wait(wait):
            self.wait_until_converged()

    def stop(self, wait: Optional[bool] = None) -> None:
        url = self.base_url + "/state/stop"
        self._session.put(url)
        if self.lab.need_to_wait(wait):
            self.wait_until_converged()

    def set_condition(
        self, bandwidth: int, latency: int, jitter: int, loss: float
    ) -> None:
        """
        Applies conditioning to this link.

        :param bandwidth: desired bandwidth, 0-10000000 kbps
        :type bandwidth: int
        :param latency: desired latency, 0-10000 ms
        :type latency: int
        :param jitter: desired jitter, 0-10000 ms
        :type jitter: int
        :param loss: desired loss, 0-100%
        :type loss: float
        """
        url = self.base_url + "/condition"
        data = {
            "bandwidth": bandwidth,
            "latency": latency,
            "jitter": jitter,
            "loss": loss,
        }
        self._session.patch(url, json=data)

    def get_condition(self) -> Optional[dict]:
        """
        Retrieves the current condition on this link.
        If there is no link condition specified, None is returned.

        :return: the applied link condition
        """
        url = self.base_url + "/condition"
        condition = self._session.get(url).json()
        if condition is None:
            return None

        keys = ["bandwidth", "latency", "jitter", "loss"]
        result = {k: v for (k, v) in condition.items() if k in keys}
        return result

    def remove_condition(self) -> None:
        """
        Removes link conditioning.
        If there's no condition applied then this is a no-op for the controller.
        """
        url = self.base_url + "/condition"
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

        :param name: the predefined condition name as outlined in the table above
        :raises ValueError: if the given name isn't known
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
            msg = "unknown condition name '{}', known values: '{}'".format(
                name,
                ", ".join(sorted(options)),
            )
            _LOGGER.error(msg)
            raise ValueError(msg)

        latency, bandwidth, loss = options[name]
        self.set_condition(bandwidth, latency, 0, loss)
