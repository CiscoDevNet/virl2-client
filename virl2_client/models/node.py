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
import time
from functools import total_ordering

from ..exceptions import InterfaceNotFound

_LOGGER = logging.getLogger(__name__)


@total_ordering
class Node:
    def __init__(
        self,
        lab,
        nid,
        label,
        node_definition,
        image_definition,
        config,
        x,
        y,
        ram,
        cpus,
        cpu_limit,
        data_volume,
        boot_disk_size,
        tags,
    ):
        """
        A VIRL2 Node object. Typically a virtual machine representing a router,
        switch or server.

        :param lab: the Lab this nodes belongs to
        :type lab: models.Lab
        :param nid: the Node ID
        :type nid: str
        :param node_definition: The node definition of this node
        :type node_definition: str
        :param image_definition: The image definition of this node
        :type image_definition: str
        :param config: The day0 configuration of this node
        :type config: str
        :param x: X coordinate on topology canvas
        :type x: int
        :param y: Y coordinate on topology canvas
        :type y: int
        :param ram: memory of node in MiB (if applicable)
        :type ram: int
        :param cpus: Amount of CPUs in this node (if applicable)
        :type cpus: int
        :param cpu_limit: CPU limit (default at 100%)
        :type cpu_limit: int
        :param data_volume: Size in GiB of 2nd HDD (if > 0)
        :type data_volume: int
        :param boot_disk_size: Size in GiB of boot disk (will expand to this size)
        :type boot_disk_size: int
        :param tags: List of tags
        :type tags: List[str, str]
        """
        self.lab = lab
        self.id = nid
        self._label = label
        self._node_definition = node_definition
        self._x = x
        self._y = y
        self._state = None
        self.session = lab.session
        self._image_definition = image_definition
        self._ram = ram
        self._config = config
        self._cpus = cpus
        self._cpu_limit = cpu_limit
        self._data_volume = data_volume
        self._boot_disk_size = boot_disk_size
        self._tags = tags
        self._compute_id = None

        self.statistics = {"cpu_usage": 0, "disk_read": 0, "disk_write": 0}

    @property
    def state(self):
        self.lab.sync_states_if_outdated()
        return self._state

    def __str__(self):
        return "Node: {}".format(self._label)

    def __repr__(self):
        return (
            "{}({!r}, {!r}, {!r}, {!r}, {!r}, {!r}, "
            "{!r}, {!r}, {!r}, {!r}, {!r}, {!r}, {!r}, {!r})".format(
                self.__class__.__name__,
                str(self.lab),
                self.id,
                self._label,
                self._node_definition,
                self._image_definition,
                self._config,
                self._x,
                self._y,
                self._ram,
                self._cpus,
                self._cpu_limit,
                self._data_volume,
                self._boot_disk_size,
                self._tags,
            )
        )

    def __eq__(self, other):
        if not isinstance(other, Node):
            return False
        return self.id == other.id

    def __lt__(self, other):
        if not isinstance(other, Node):
            return False
        return int(self.id) < int(other.id)

    def __hash__(self):
        return hash(self.id)

    def interfaces(self):
        self.lab.sync_topology_if_outdated()
        return [iface for iface in self.lab.interfaces() if iface.node is self]

    def physical_interfaces(self):
        self.lab.sync_topology_if_outdated()
        return [iface for iface in self.interfaces() if iface.physical]

    def create_interface(self, slot=None, wait=False):
        """
        Create an interface in the specified slot or, if no slot is given, in the
        next available slot.

        :param slot: (optional)
        :type slot: int
        :param wait: Wait for the creation
        :type wait: bool
        :returns: The newly created interface
        :rtype: models.Interface
        """
        return self.lab.create_interface(self, slot, wait=wait)

    def next_available_interface(self):
        """
        Returns the next available physical interface on this node.

        Note: On XR 9000v, the first two physical interfaces are marked
        as "do not use"... Only the third physical interface can be used
        to connect to other nodes!

        :returns: an interface or None, if all existing ones are connected
        :rtype: models.Interface
        """
        for iface in self.interfaces():
            if not iface.connected and iface.physical:
                return iface
        return None

    def peer_interfaces(self):
        peer_ifaces = {
            iface.peer_interface for iface in self.interfaces() if iface is not None
        }
        return list(peer_ifaces)

    def peer_nodes(self):
        return list({iface.node for iface in self.peer_interfaces()})

    def links(self):
        """
        :returns: list of links
        :rtype: list[models.Link]
        """
        return list(
            {link for iface in self.interfaces() if (link := iface.link) is not None}
        )

    def degree(self):
        self.lab.sync_topology_if_outdated()
        return len(self.links())

    @property
    def label(self):
        self.lab.sync_topology_if_outdated()
        return self._label

    @label.setter
    def label(self, value):
        self._set_node_property("label", value)
        self._label = value

    @property
    def x(self):
        self.lab.sync_topology_if_outdated()
        return self._x

    @x.setter
    def x(self, value):
        self._set_node_property("x", value)
        self._x = value

    @property
    def y(self):
        self.lab.sync_topology_if_outdated()
        return self._y

    @y.setter
    def y(self, value):
        self._set_node_property("y", value)
        self._y = value

    @property
    def ram(self):
        self.lab.sync_topology_if_outdated()
        return self._ram

    @ram.setter
    def ram(self, value):
        self._set_node_property("ram", value)
        self._ram = value

    @property
    def cpus(self):
        self.lab.sync_topology_if_outdated()
        return self._cpus

    @cpus.setter
    def cpus(self, value):
        self._set_node_property("cpus", value)
        self._cpus = value

    @property
    def cpu_limit(self):
        self.lab.sync_topology_if_outdated()
        return self._cpu_limit

    @cpu_limit.setter
    def cpu_limit(self, value):
        self._set_node_property("cpu_limit", value)
        self._cpu_limit = value

    @property
    def data_volume(self):
        self.lab.sync_topology_if_outdated()
        return self._data_volume

    @data_volume.setter
    def data_volume(self, value):
        self._set_node_property("data_volume", value)
        self._data_volume = value

    @property
    def boot_disk_size(self):
        self.lab.sync_topology_if_outdated()
        return self._boot_disk_size

    @boot_disk_size.setter
    def boot_disk_size(self, value):
        self._set_node_property("boot_disk_size", value)
        self._boot_disk_size = value

    @property
    def config(self):
        # TODO: auto sync if out of date
        return self._config

    @config.setter
    def config(self, value):
        self._set_node_property("configuration", value)
        self._config = value

    @property
    def image_definition(self):
        self.lab.sync_topology_if_outdated()
        return self._image_definition

    @image_definition.setter
    def image_definition(self, value):
        self.lab.sync_topology_if_outdated()
        self._set_node_property("image_definition", value)
        self._image_definition = value

    @property
    def node_definition(self):
        self.lab.sync_topology_if_outdated()
        return self._node_definition

    @node_definition.setter
    def node_definition(self, value):
        self.lab.sync_topology_if_outdated()
        self._set_node_property("node_definition", value)
        self._image_definition = value

    @property
    def compute_id(self):
        self.lab.sync_topology_if_outdated()
        return self._compute_id

    def _set_node_property(self, key, val):
        _LOGGER.info("Setting node property %s %s: %s", self, key, val)
        node_url = "{}".format(self._base_url)
        response = self.session.patch(url=node_url, json={key: val})
        response.raise_for_status()

    @property
    def lab_base_url(self):
        return self.lab.lab_base_url

    @property
    def _base_url(self):
        return self.lab_base_url + "/nodes/{}".format(self.id)

    @property
    def cpu_usage(self):
        self.lab.sync_statistics_if_outdated()
        return min(self.statistics["cpu_usage"], 100)

    @property
    def disk_read(self):
        self.lab.sync_statistics_if_outdated()
        return round(self.statistics["disk_read"] / 1048576)

    @property
    def disk_write(self):
        self.lab.sync_statistics_if_outdated()
        return round(self.statistics["disk_write"] / 1048576)

    def get_interface_by_label(self, label):
        for iface in self.interfaces():
            if iface.label == label:
                return iface
        raise InterfaceNotFound("{}:{}".format(label, self))

    def get_interface_by_slot(self, slot):
        for iface in self.interfaces():
            if iface.slot == slot:
                return iface
        raise InterfaceNotFound("{}:{}".format(slot, self))

    def get_links_to(self, other_node):
        """
        Returns all links between this node and another.

        :param other_node: the other node
        :type other_node: models.Node
        :returns: a list of links
        :rtype: list[models.Link]
        """
        links = []
        for link in self.links():
            if other_node in link.nodes:
                links.append(link)
        return links

    def get_link_to(self, other_node):
        """
        Returns one link between this node and another.

        :param other_node: the other node
        :type other_node: models.Node
        :returns: a link
        :rtype: models.Link
        """
        for link in self.links():
            if other_node in link.nodes:
                return link

    def wait_until_converged(self, max_iterations=None, wait_time=None):
        _LOGGER.info("Waiting for node %s to converge", self.id)
        max_iter = (
            self.lab.wait_max_iterations if max_iterations is None else max_iterations
        )
        wait_time = self.lab.wait_time if wait_time is None else wait_time
        for index in range(max_iter):
            converged = self.has_converged()
            if converged:
                _LOGGER.info("Node %s has converged", self.id)
                return

            if index % 10 == 0:
                _LOGGER.info(
                    "Node has not converged, attempt %s/%s, waiting...",
                    index,
                    max_iter,
                )
            time.sleep(wait_time)

        msg = "Node %s has not converged, maximum tries %s exceeded" % (
            self.id,
            max_iter,
        )
        _LOGGER.error(msg)
        # after maximum retries are exceeded and node has not converged
        # error must be raised - it makes no sense to just log info
        # and let client fail with something else if wait is explicitly
        # specified
        raise RuntimeError(msg)

    def has_converged(self):
        url = self._base_url + "/check_if_converged"
        response = self.session.get(url)
        response.raise_for_status()
        converged = response.json()
        return converged

    def start(self, wait=False):
        url = self._base_url + "/state/start"
        response = self.session.put(url)
        response.raise_for_status()
        if self.lab.need_to_wait(wait):
            self.wait_until_converged()

    def stop(self, wait=False):
        url = self._base_url + "/state/stop"
        response = self.session.put(url)
        response.raise_for_status()
        if self.lab.need_to_wait(wait):
            self.wait_until_converged()

    def wipe(self, wait=False):
        url = self._base_url + "/wipe_disks"
        response = self.session.put(url)
        response.raise_for_status()
        if self.lab.need_to_wait(wait):
            self.wait_until_converged()

    def extract_configuration(self):
        url = self._base_url + "/extract_configuration"
        response = self.session.put(url)
        response.raise_for_status()

    def console_logs(self, console_id, lines=None):
        query = "?lines=%d" % lines if lines else ""
        url = self._base_url + "/consoles/%d/log%s" % (console_id, query)
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def console_key(self):
        url = self._base_url + "/keys/console"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def vnc_key(self):
        url = self._base_url + "/keys/vnc"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def remove_on_server(self):
        _LOGGER.info("Removing node %s", self)
        url = self._base_url
        response = self.session.delete(url)
        response.raise_for_status()

    def tags(self):
        """Returns the tags set on this node"""
        self.lab.sync_topology_if_outdated()
        return self._tags

    def add_tag(self, tag):
        current = self.tags()
        if tag not in current:
            current.append(tag)
            self._set_node_property("tags", current)

    def remove_tag(self, tag):
        current = self.tags()
        current.remove(tag)
        self._set_node_property("tags", current)

    def run_pyats_command(self, command):
        """Run a pyATS command in exec mode.

        :param command: the command (like "show version")
        :type command: str
        :returns: the output from the device
        :rtype: str
        """
        label = self.label
        return self.lab.pyats.run_command(label, command)

    def run_pyats_config_command(self, command):
        """Run a pyATS command in config mode.

        :param command: the command (like "interface gi0")
        :type command: str
        :returns: the output from the device
        :rtype: str
        """
        label = self.label
        return self.lab.pyats.run_config_command(label, command)

    def sync_layer3_addresses(self):
        """Acquire all L3 addresses from the controller. For this
        to work, the device has to be attached to the external network
        in bridge mode and must run DHCP to acquire an IP address.
        """
        # TODO: can optimise the sync of l3 to only be for the node
        # rather than whole lab
        url = self._base_url + "/layer3_addresses"
        response = self.session.get(url)
        response.raise_for_status()
        result = response.json()
        interfaces = result.get("interfaces", {})
        self.map_l3_addresses_to_interfaces(interfaces)

    def map_l3_addresses_to_interfaces(self, mapping):
        for mac_address, entry in mapping.items():
            ipv4 = entry.get("ip4")
            ipv6 = entry.get("ip6")
            label = entry.get("label")
            iface = self.get_interface_by_label(label)
            if not iface:
                continue
            iface.ip_snooped_info = {
                "mac_address": mac_address,
                "ipv4": ipv4,
                "ipv6": ipv6,
            }

    def update(self, node_data, exclude_configurations):
        if "data" in node_data:
            node_data = node_data["data"]
        self._label = node_data["label"]
        self._x = node_data["x"]
        self._y = node_data["y"]
        self._node_definition = node_data["node_definition"]
        self._image_definition = node_data.get("image_definition", None)
        self._ram = node_data["ram"]
        self._cpus = node_data["cpus"]
        self._cpu_limit = node_data.get("cpu_limit", 100)
        self._data_volume = node_data["data_volume"]
        self._boot_disk_size = node_data["boot_disk_size"]
        self._tags = node_data["tags"]
        self._compute_id = node_data.get("compute_id")
        if not exclude_configurations:
            self._config = node_data.get("configuration")

    def is_active(self):
        active_states = {"STARTED", "QUEUED", "BOOTED"}
        return self.state in active_states

    def is_booted(self):
        return self.state == "BOOTED"
