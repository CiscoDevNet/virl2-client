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
import warnings
from typing import TYPE_CHECKING, Any

from ..utils import check_stale, get_url_from_template, locked
from ..utils import property_s as property

if TYPE_CHECKING:
    import httpx

    from .link import Link
    from .node import Node

_LOGGER = logging.getLogger(__name__)


class Interface:
    _URL_TEMPLATES = {
        "interface": "{lab}/interfaces/{id}",
        "state": "{lab}/interfaces/{id}/state",
        "start": "{lab}/interfaces/{id}/state/start",
        "stop": "{lab}/interfaces/{id}/state/stop",
    }

    def __init__(
        self,
        iid: str,
        node: Node,
        label: str,
        slot: int | None,
        iface_type: str = "physical",
        mac_address: str | None = None,
    ) -> None:
        """
        A CML 2 network interface, part of a node.

        :param iid: The interface ID.
        :param node: The node object.
        :param label: The label of the interface.
        :param slot: The slot of the interface.
        :param iface_type: The type of the interface.
        :param mac_address: The MAC address of the interface.
        """
        self._id = iid
        self._node = node
        self._type = iface_type
        self._label = label
        self._slot = slot
        self._mac_address = mac_address
        self._state: str | None = None
        self._session: httpx.Client = node._lab._session
        self._stale = False
        self.statistics = {
            "readbytes": 0,
            "readpackets": 0,
            "writebytes": 0,
            "writepackets": 0,
        }
        self._ip_snooped_info: dict[str, str | None] = {
            "mac_address": None,
            "ipv4": None,
            "ipv6": None,
        }
        self._deployed_mac_address = None

    def __eq__(self, other):
        if not isinstance(other, Interface):
            return False
        return self._id == other._id

    def __str__(self):
        return f"Interface: {self._label}{' (STALE)' if self._stale else ''}"

    def __repr__(self):
        return (
            f"{self.__class__.__name__}("
            f"{self._node!r}, "
            f"{self._id!r}, "
            f"{self._label!r}, "
            f"{self._slot!r})"
        )

    def __hash__(self):
        return hash(self._id)

    def _url_for(self, endpoint, **kwargs):
        """
        Generate the URL for a given API endpoint.

        :param endpoint: The desired endpoint.
        :param **kwargs: Keyword arguments used to format the URL.
        :returns: The formatted URL.
        """
        kwargs["lab"] = self.node._lab._url_for("lab")
        kwargs["id"] = self.id
        return get_url_from_template(endpoint, self._URL_TEMPLATES, kwargs)

    @property
    def id(self) -> str:
        """Return the ID of the interface."""
        return self._id

    @property
    def node(self) -> Node:
        """Return the node object to which the interface belongs."""
        return self._node

    @property
    def type(self) -> str:
        """Return the type of the interface."""
        return self._type

    @property
    def label(self) -> str:
        """Return the label of the interface."""
        return self._label

    @property
    def slot(self) -> int | None:
        """Return the slot of the interface."""
        return self._slot

    @property
    def physical(self) -> bool:
        """Check if the interface is physical."""
        return self.type == "physical"

    @property
    def mac_address(self) -> str | None:
        """Return the MAC address set to the interface.
        This is the address that will be used when the device is started."""
        self.node._lab.sync_topology_if_outdated()
        return self._mac_address

    @mac_address.setter
    @locked
    def mac_address(self, value: str | None) -> None:
        """Set the MAC address of the node to the given value."""
        self._set_interface_property("mac_address", value)
        self._mac_address = value

    @property
    def connected(self) -> bool:
        """Check if the interface is connected to a link."""
        return self.link is not None

    @property
    def state(self) -> str | None:
        """Return the state of the interface."""
        self.node._lab.sync_states_if_outdated()
        if self._state is None:
            url = self._url_for("state")
            self._state = self._session.get(url).json()["state"]
        return self._state

    @property
    def link(self) -> Link | None:
        """Get the link if the interface is connected, otherwise None."""
        self.node._lab.sync_topology_if_outdated()
        for link in self.node._lab.links():
            if self in link.interfaces:
                return link
        return None

    @property
    def peer_interface(self) -> Interface | None:
        """Return the peer interface connected to the interface."""
        link = self.link
        if link is None:
            return None
        interfaces = link.interfaces
        if interfaces[0] is self:
            return interfaces[1]
        return interfaces[0]

    @property
    def peer_node(self) -> Node | None:
        """Return the node to which the peer interface belongs."""
        peer_interface = self.peer_interface
        return peer_interface.node if peer_interface is not None else None

    @property
    def readbytes(self) -> int:
        """Return the number of bytes read by the interface."""
        self.node._lab.sync_statistics_if_outdated()
        return int(self.statistics["readbytes"])

    @property
    def readpackets(self) -> int:
        """Return the number of packets read by the interface."""
        self.node._lab.sync_statistics_if_outdated()
        return int(self.statistics["readpackets"])

    @property
    def writebytes(self) -> int:
        """Return the number of bytes written by the interface."""
        self.node._lab.sync_statistics_if_outdated()
        return int(self.statistics["writebytes"])

    @property
    def writepackets(self) -> int:
        """Return the number of packets written by the interface."""
        self.node._lab.sync_statistics_if_outdated()
        return int(self.statistics["writepackets"])

    @property
    def ip_snooped_info(self) -> dict[str, str | None]:
        """
        Return the discovered MAC, IPv4 and IPv6 addresses
        of the interface in a dictionary.
        """
        self.node.sync_l3_addresses_if_outdated()
        return self._ip_snooped_info.copy()

    @property
    def discovered_mac_address(self) -> str | None:
        """Return the discovered MAC address of the interface."""
        self.node.sync_l3_addresses_if_outdated()
        return self._ip_snooped_info["mac_address"]

    @property
    def discovered_ipv4(self) -> str | None:
        """Return the discovered IPv4 address of the interface."""
        self.node.sync_l3_addresses_if_outdated()
        return self._ip_snooped_info["ipv4"]

    @property
    def discovered_ipv6(self) -> str | None:
        """Return the discovered IPv6 address of the interface."""
        self.node.sync_l3_addresses_if_outdated()
        return self._ip_snooped_info["ipv6"]

    @property
    def deployed_mac_address(self) -> str | None:
        """Return the deployed MAC address of the interface."""
        self.node.sync_interface_operational()
        return self._deployed_mac_address

    @property
    def is_physical(self) -> bool:
        """
        DEPRECATED: Use `.physical` instead.
        (Reason: renamed to match similar parameters)

        Check if the interface is physical.
        """
        warnings.warn(
            "'Interface.is_physical' is deprecated. Use '.physical' instead.",
        )
        return self.physical

    def as_dict(self) -> dict[str, str]:
        """Convert the interface to a dictionary representation."""
        return {
            "id": self.id,
            "node": self.node.id,
            "data": {
                "lab_id": self.node._lab.id,
                "label": self.label,
                "slot": self.slot,
                "type": self.type,
                "mac_address": self.discovered_mac_address,
                "is_connected": self.connected,
                "state": self.state,
            },
        }

    def get_link_to(self, other_interface: Interface) -> Link | None:
        """
        Return the link between this interface and another.

        :param other_interface: The other interface.
        :returns: A Link object if a link exists between the interfaces, None otherwise.
        """
        link = self.link
        if link is not None and other_interface in link.interfaces:
            return link
        return None

    def remove(self) -> None:
        """Remove the interface from the node."""
        self.node._lab.remove_interface(self)

    @check_stale
    def _remove_on_server(self) -> None:
        """
        Remove the interface on the server.

        This method is internal and should not be used directly. Use 'remove' instead.
        """
        _LOGGER.info(f"Removing interface {self}")
        url = self._url_for("interface")
        self._session.delete(url)

    def remove_on_server(self) -> None:
        """
        DEPRECATED: Use `.remove()` instead.
        (Reason: was never meant to be public, removing only on server is not useful)

        Remove the interface on the server.
        """
        warnings.warn(
            "'Interface.remove_on_server()' is deprecated. Use '.remove()' instead.",
        )
        self._remove_on_server()

    @check_stale
    def bring_up(self) -> None:
        """Bring up the interface."""
        url = self._url_for("start")
        self._session.put(url)

    @check_stale
    def shutdown(self) -> None:
        """Shutdown the interface."""
        url = self._url_for("stop")
        self._session.put(url)

    def peer_interfaces(self):
        """
        DEPRECATED: Use `.peer_interface` instead.
        (Reason: pointless plural, could have been a parameter)

        Return the peer interface connected to this interface in a set.
        """
        warnings.warn(
            "'Interface.peer_interfaces()' is deprecated, "
            "use '.peer_interface' instead.",
        )
        return {self.peer_interface}

    def peer_nodes(self):
        """
        DEPRECATED: Use `.peer_node` instead.
        (Reason: pointless plural, could have been a parameter)

        Return the node of the peer interface in a set.
        """
        warnings.warn(
            "'Interface.peer_nodes() is deprecated. Use '.peer_node' instead.",
        )
        return {self.peer_node}

    def links(self):
        """
        DEPRECATED: Use `.link` instead.
        (Reason: pointless plural, could have been a parameter)

        Return the link connected to this interface in a list.
        """
        warnings.warn(
            "'Interface.links()' is deprecated. Use '.link' instead.",
        )
        link = self.link
        if link is None:
            return []
        return [link]

    def degree(self):
        """
        DEPRECATED: Use `.connected` instead.
        (Reason: degree always 0 or 1)

        Return the degree of the interface.
        """
        warnings.warn(
            "'Interface.degree()' is deprecated. Use '.connected' instead.",
        )
        return int(self.connected)

    def is_connected(self):
        """
        DEPRECATED: Use `.connected` instead.
        (Reason: should have been a parameter, renamed to match similar parameters)

        Check if the interface is connected to a link.
        """
        warnings.warn(
            "'Interface.is_connected()' is deprecated. Use '.connected' instead.",
        )
        return self.connected

    @check_stale
    @locked
    def _update(
        self,
        interface_data: dict[str, Any],
        push_to_server: bool = True,
    ) -> None:
        """
        Update the interface_data with the provided data.

        :param interface_data: The data to update the interface with.
        :param push_to_server: Whether to push the changes to the server.
        """
        if push_to_server:
            self._set_interface_properties(interface_data)
        if "data" in interface_data:
            interface_data = interface_data["data"]
        for key, value in interface_data.items():
            setattr(self, f"_{key}", value)

    def _set_interface_property(self, key: str, val: Any) -> None:
        """
        Set a property of the interface.

        :param key: The key of the property to set.
        :param val: The value to set.
        """
        _LOGGER.debug(f"Setting node property {self} {key}: {val}")
        self._set_interface_properties({key: val})

    @check_stale
    def _set_interface_properties(self, interface_data: dict[str, Any]) -> None:
        """
        Set multiple properties of the interface.

        :param node_data: A dictionary containing the properties to set.
        """
        url = self._url_for("interface")
        self._session.patch(url, json=interface_data)
