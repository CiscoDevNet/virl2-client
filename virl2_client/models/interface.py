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
import warnings
from functools import total_ordering
from typing import TYPE_CHECKING, Optional

from ..utils import check_stale
from ..utils import property_s as property

if TYPE_CHECKING:
    import httpx

    from .link import Link
    from .node import Node

_LOGGER = logging.getLogger(__name__)


@total_ordering
class Interface:
    def __init__(
        self,
        iid: str,
        node: Node,
        label: str,
        slot: Optional[int],
        iface_type: str = "physical",
    ) -> None:
        """
        A VIRL2 network interface, part of a node.

        :param iid: interface ID
        :param node: node object
        :param label: the label of the interface
        :param slot: the slot of the interface
        :param iface_type: the type of the interface, defaults to "physical"
        """
        self._id = iid
        self._node = node
        self._type = iface_type
        self._label = label
        self._slot = slot
        self._state: Optional[str] = None
        self._session: httpx.Client = node.lab.session
        self._stale = False
        self.statistics = {
            "readbytes": 0,
            "readpackets": 0,
            "writebytes": 0,
            "writepackets": 0,
        }
        self.ip_snooped_info: dict[str, Optional[str]] = {
            "mac_address": None,
            "ipv4": None,
            "ipv6": None,
        }

    def __eq__(self, other):
        if not isinstance(other, Interface):
            return False
        return self._id == other._id

    def __lt__(self, other):
        if not isinstance(other, Interface):
            return False
        return self._id < other._id

    def __str__(self):
        return f"Interface: {self._label}{' (STALE)' if self._stale else ''}"

    def __repr__(self):
        return "{}({!r}, {!r}, {!r}, {!r}, {!r})".format(
            self.__class__.__name__,
            self._id,
            self._node,
            self._label,
            self._slot,
            self._type,
        )

    def __hash__(self):
        return hash(self._id)

    @property
    def lab_base_url(self) -> str:
        return self.node.lab_base_url

    @property
    def _base_url(self) -> str:
        return self.lab_base_url + "/interfaces/{}".format(self.id)

    @property
    def id(self) -> str:
        return self._id

    @property
    def node(self) -> Node:
        return self._node

    @property
    def type(self) -> str:
        return self._type

    @property
    def label(self) -> str:
        return self._label

    @property
    def slot(self) -> Optional[int]:
        return self._slot

    @property
    def physical(self) -> bool:
        """Whether the interface is physical."""
        self.node.lab.sync_topology_if_outdated()
        return self.type == "physical"

    @property
    def connected(self) -> bool:
        """Whether the interface is connected to a link."""
        return self.link is not None

    @property
    def state(self) -> Optional[str]:
        self.node.lab.sync_states_if_outdated()
        if self._state is None:
            url = self._base_url + "/state"
            self._state = self._session.get(url).json()["state"]
        return self._state

    @property
    def link(self) -> Optional[Link]:
        """Is link if connected, otherwise None."""
        self.node.lab.sync_topology_if_outdated()
        for link in self.node.lab.links():
            if self in link.interfaces:
                return link
        return None

    @property
    def peer_interface(self) -> Optional[Interface]:
        link = self.link
        if link is None:
            return None
        interfaces = link.interfaces
        if interfaces[0] is self:
            return interfaces[1]
        return interfaces[0]

    @property
    def peer_node(self) -> Optional[Node]:
        peer_interface = self.peer_interface
        return peer_interface.node if peer_interface is not None else None

    @property
    def readbytes(self) -> int:
        self.node.lab.sync_statistics_if_outdated()
        return int(self.statistics["readbytes"])

    @property
    def readpackets(self) -> int:
        self.node.lab.sync_statistics_if_outdated()
        return int(self.statistics["readpackets"])

    @property
    def writebytes(self) -> int:
        self.node.lab.sync_statistics_if_outdated()
        return int(self.statistics["writebytes"])

    @property
    def writepackets(self) -> int:
        self.node.lab.sync_statistics_if_outdated()
        return int(self.statistics["writepackets"])

    @property
    def discovered_mac_address(self) -> Optional[str]:
        self.node.lab.sync_l3_addresses_if_outdated()
        return self.ip_snooped_info["mac_address"]

    @property
    def discovered_ipv4(self) -> Optional[str]:
        self.node.lab.sync_l3_addresses_if_outdated()
        return self.ip_snooped_info["ipv4"]

    @property
    def discovered_ipv6(self) -> Optional[str]:
        self.node.lab.sync_l3_addresses_if_outdated()
        return self.ip_snooped_info["ipv6"]

    @property
    def is_physical(self):
        warnings.warn("Deprecated, use .physical instead.", DeprecationWarning)
        return self.physical

    def as_dict(self) -> dict[str, str]:
        # TODO what should be here in 'data' key?
        return {"id": self.id, "node": self.node.id, "data": self.id}

    def get_link_to(self, other_interface: Interface) -> Optional[Link]:
        """
        Returns the link between this interface and another.

        :param other_interface: the other interface
        :returns: A Link
        """
        link = self.link
        if link is not None and other_interface in link.interfaces:
            return link
        return None

    def remove(self) -> None:
        self.node.lab.remove_interface(self)

    @check_stale
    def _remove_on_server(self) -> None:
        _LOGGER.info("Removing interface %s", self)
        url = self._base_url
        self._session.delete(url)

    def remove_on_server(self) -> None:
        warnings.warn(
            "'Interface.remove_on_server()' is deprecated, "
            "use 'Interface.remove()' instead.",
            DeprecationWarning,
        )
        self._remove_on_server()

    @check_stale
    def bring_up(self) -> None:
        url = self._base_url + "/state/start"
        self._session.put(url)

    @check_stale
    def shutdown(self) -> None:
        url = self._base_url + "/state/stop"
        self._session.put(url)

    def peer_interfaces(self):
        warnings.warn("Deprecated, use .peer_interface instead.", DeprecationWarning)
        return {self.peer_interface}

    def peer_nodes(self):
        warnings.warn("Deprecated, use .peer_node instead.", DeprecationWarning)
        return {self.peer_node}

    def links(self):
        warnings.warn("Deprecated, use .link instead.", DeprecationWarning)
        link = self.link
        if link is None:
            return []
        return [link]

    def degree(self):
        warnings.warn("Deprecated, use .connected instead.", DeprecationWarning)
        return int(self.connected)

    def is_connected(self):
        warnings.warn("Deprecated, use .connected instead.", DeprecationWarning)
        return self.connected
