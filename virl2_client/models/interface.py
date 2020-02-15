#
# Python bindings for the Cisco VIRL 2 Network Simulation Platform
#
# This file is part of VIRL 2
#
# Copyright 2020 Cisco Systems Inc.
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
from functools import total_ordering

logger = logging.getLogger(__name__)


@total_ordering
class Interface:
    """A VIRL2 network interface, part of a node.

    :param iid: interface ID
    :type iid: str
    :param node: node object
    :type node: models.Node
    :param label: the label of the interface
    :type label: str
    :param slot: the slot of the interface
    :type slot: int
    :param iface_type: the type of the interface, defaults to "physical"
    :type iface_type: str, optional
    """
    def __init__(self, iid, node, label, slot, iface_type="physical"):
        """Constructor method"""
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
            "writepackets": 0
        }
        self.ip_snooped_info = {
            "mac_address": None,
            "ipv4": None,
            "ipv6": None
        }

    @property
    def is_physical(self):
        return self.type == "physical"

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
            self.__class__.__name__, self.id, self.node, self.label, self.slot,
            self.type)

    def __hash__(self):
        return hash(self.id)

    @property
    def lab_base_url(self):
        return self.node.lab_base_url

    @property
    def _base_url(self):
        return self.lab_base_url + "/interfaces/{}".format(self.id)

    def links(self):
        self.node.lab.sync_topology_if_outdated()
        return [lnk for lnk in self.node.lab.links() if self in lnk.interfaces]

    def degree(self):
        self.node.lab.sync_topology_if_outdated()
        return len(self.links())

    def is_connected(self):
        self.node.lab.sync_topology_if_outdated()
        return self.degree() > 0

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

    def peer_interfaces(self):
        self.node.lab.sync_topology_if_outdated()
        ifaces = set()
        for link in self.links():
            if link.interface_a.id == self.id:
                ifaces.add(link.interface_b)
            else:
                ifaces.add(link.interface_a)
        return ifaces

    def peer_nodes(self):
        self.node.lab.sync_topology_if_outdated()
        return {iface.node for iface in self.peer_interfaces()}

    def remove_on_server(self):
        logger.info("Removing interface %s", self)

        url = self._base_url
        response = self.node.session.delete(url)
        response.raise_for_status()

    def as_dict(self):
        # TODO what should be here in 'data' key?
        return {"id": self.id, "node": self.node.id, "data": self.id}

    def bring_up(self):
        url = self._base_url + "/state/start"
        response = self.session.put(url)
        response.raise_for_status()

    def shutdown(self):
        url = self._base_url + "/state/stop"
        response = self.session.put(url)
        response.raise_for_status()

    @property
    def state(self):
        return self._state
