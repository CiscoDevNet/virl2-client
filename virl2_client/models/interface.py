#
# This file is part of VIRL 2
# Copyright (c) 2019-2022, Cisco Systems, Inc.
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

import logging
import warnings
from functools import total_ordering

_LOGGER = logging.getLogger(__name__)


@total_ordering
class Interface:
    def __init__(self, iid, node, label, slot, iface_type="physical"):
        """
        A VIRL2 network interface, part of a node.

        :param iid: interface ID
        :type iid: str
        :param node: node object
        :type node: models.Node
        :param label: the label of the interface
        :type label: str
        :param slot: the slot of the interface
        :type slot: int
        :param iface_type: the type of the interface, defaults to "physical"
        :type iface_type: str
        """
        self.id = iid
        self.node = node
        self.type = iface_type
        self.label = label
        self.slot = slot
        self._state = None
        self.session = node.session
        self.statistics = {
            "readbytes": 0,
            "readpackets": 0,
            "writebytes": 0,
            "writepackets": 0,
        }
        self.ip_snooped_info = {"mac_address": None, "ipv4": None, "ipv6": None}

    def __eq__(self, other):
        if not isinstance(other, Interface):
            return False
        return self.id == other.id

    def __lt__(self, other):
        if not isinstance(other, Interface):
            return False
        return int(self.id) < int(other.id)

    def __str__(self):
        return "Interface: {}".format(self.label)

    def __repr__(self):
        return "{}({!r}, {!r}, {!r}, {!r}, {!r})".format(
            self.__class__.__name__,
            self.id,
            self.node,
            self.label,
            self.slot,
            self.type,
        )

    def __hash__(self):
        return hash(self.id)

    @property
    def lab_base_url(self):
        return self.node.lab_base_url

    @property
    def _base_url(self):
        return self.lab_base_url + "/interfaces/{}".format(self.id)

    @property
    def physical(self):
        """Whether the interface is physical."""
        self.node.lab.sync_topology_if_outdated()
        return self.type == "physical"

    @property
    def connected(self):
        """Whether the interface is connected to a link."""
        return self.link is not None

    @property
    def state(self):
        self.node.lab.sync_states_if_outdated()
        return self._state

    @property
    def link(self):
        """Is link if connected, otherwise None."""
        self.node.lab.sync_topology_if_outdated()
        for link in self.node.lab.links():
            if self in link.interfaces:
                return link

    @property
    def peer_interface(self):
        link = self.link
        if link is None:
            return None
        interfaces = link.interfaces
        if interfaces[0] is self:
            return interfaces[1]
        return interfaces[0]

    @property
    def peer_node(self):
        peer_interface = self.peer_interface
        if peer_interface is None:
            return None
        return peer_interface.node

    @property
    def readbytes(self):
        self.node.lab.sync_statistics_if_outdated()
        return int(self.statistics["readbytes"])

    @property
    def readpackets(self):
        self.node.lab.sync_statistics_if_outdated()
        return int(self.statistics["readpackets"])

    @property
    def writebytes(self):
        self.node.lab.sync_statistics_if_outdated()
        return int(self.statistics["writebytes"])

    @property
    def writepackets(self):
        self.node.lab.sync_statistics_if_outdated()
        return int(self.statistics["writepackets"])

    @property
    def discovered_mac_address(self):
        self.node.lab.sync_l3_addresses_if_outdated()
        return self.ip_snooped_info["mac_address"]

    @property
    def discovered_ipv4(self):
        self.node.lab.sync_l3_addresses_if_outdated()
        return self.ip_snooped_info["ipv4"]

    @property
    def discovered_ipv6(self):
        self.node.lab.sync_l3_addresses_if_outdated()
        return self.ip_snooped_info["ipv6"]

    @property
    def is_physical(self):
        warnings.warn("Deprecated, use .physical instead.", DeprecationWarning)
        return self.physical

    def as_dict(self):
        # TODO what should be here in 'data' key?
        return {"id": self.id, "node": self.node.id, "data": self.id}

    def get_link_to(self, other_interface):
        """
        Returns the link between this interface and another.

        :param other_interface: the other interface
        :type other_interface: models.Interface
        :returns: A Link
        :rtype: models.Link
        """
        link = self.link
        return link if other_interface in link.interfaces else None

    def remove_on_server(self):
        _LOGGER.info("Removing interface %s", self)

        url = self._base_url
        response = self.node.session.delete(url)
        response.raise_for_status()

    def bring_up(self):
        url = self._base_url + "/state/start"
        response = self.session.put(url)
        response.raise_for_status()

    def shutdown(self):
        url = self._base_url + "/state/stop"
        response = self.session.put(url)
        response.raise_for_status()

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
