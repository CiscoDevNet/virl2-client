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
import warnings
from functools import total_ordering
from typing import TYPE_CHECKING, Any, Optional

from ..exceptions import InterfaceNotFound

if TYPE_CHECKING:
    import httpx

    from .interface import Interface
    from .lab import Lab
    from .link import Link

_LOGGER = logging.getLogger(__name__)

CONFIG_WARNING = 'The property "config" is deprecated in favor of "configuration"'


@total_ordering
class Node:
    def __init__(
        self,
        lab: Lab,
        nid: str,
        label: str,
        node_definition: str,
        image_definition: Optional[str],
        configuration: Optional[str],
        x: int,
        y: int,
        ram: Optional[int],
        cpus: Optional[int],
        cpu_limit: Optional[int],
        data_volume: Optional[int],
        boot_disk_size: Optional[int],
        hide_links: bool,
        tags: list[str],
        resource_pool: Optional[str],
    ) -> None:
        """
        A VIRL2 Node object. Typically, a virtual machine representing a router,
        switch or server.

        :param lab: the Lab this node belongs to
        :param nid: the Node ID
        :param label: node label
        :param node_definition: The node definition of this node
        :param image_definition: The image definition of this node
        :param configuration: The initial configuration of this node
        :param x: X coordinate on topology canvas
        :param y: Y coordinate on topology canvas
        :param ram: memory of node in MiB (if applicable)
        :param cpus: Amount of CPUs in this node (if applicable)
        :param cpu_limit: CPU limit (default at 100%)
        :param data_volume: Size in GiB of 2nd HDD (if > 0)
        :param boot_disk_size: Size in GiB of boot disk (will expand to this size)
        :param hide_links: Whether node's links should be hidden in UI visualization
        :param tags: List of tags
        :param resource_pool: A resource pool ID if the node is in a resource pool
        """
        self.lab = lab
        self.id = nid
        self._label = label
        self._node_definition = node_definition
        self._x = x
        self._y = y
        self._state: Optional[str] = None
        self._session: httpx.Client = lab.session
        self._image_definition = image_definition
        self._ram = ram
        self._configuration = configuration
        self._cpus = cpus
        self._cpu_limit = cpu_limit
        self._data_volume = data_volume
        self._boot_disk_size = boot_disk_size
        self._hide_links = hide_links
        self._tags = tags
        self._compute_id: Optional[str] = None
        self._resource_pool = resource_pool

        self.statistics: dict[str, int | float] = {
            "cpu_usage": 0,
            "disk_read": 0,
            "disk_write": 0,
        }

    def __str__(self):
        return "Node: {}".format(self._label)

    def __repr__(self):
        return (
            "{}({!r}, {!r}, {!r}, {!r}, {!r}, {!r}, {!r}, "
            "{!r}, {!r}, {!r}, {!r}, {!r}, {!r}, {!r}, {!r})".format(
                self.__class__.__name__,
                str(self.lab),
                self.id,
                self._label,
                self._node_definition,
                self._image_definition,
                self._configuration,
                self._x,
                self._y,
                self._ram,
                self._cpus,
                self._cpu_limit,
                self._data_volume,
                self._boot_disk_size,
                self._hide_links,
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

    @property
    def state(self) -> Optional[str]:
        self.lab.sync_states_if_outdated()
        if self._state is None:
            url = self._base_url + "/state"
            self._state = self._session.get(url).json()["state"]
        return self._state

    @state.setter
    def state(self, value: Optional[str]) -> None:
        self._state = value

    def interfaces(self) -> list[Interface]:
        self.lab.sync_topology_if_outdated()
        return [iface for iface in self.lab.interfaces() if iface.node is self]

    def physical_interfaces(self) -> list[Interface]:
        self.lab.sync_topology_if_outdated()
        return [iface for iface in self.interfaces() if iface.physical]

    def create_interface(
        self, slot: Optional[int] = None, wait: bool = False
    ) -> Interface:
        """
        Create an interface in the specified slot or, if no slot is given, in the
        next available slot.

        :param slot: (optional)
        :param wait: Wait for the creation
        :returns: The newly created interface
        :rtype: models.Interface
        """
        return self.lab.create_interface(self, slot, wait=wait)

    def next_available_interface(self) -> Optional[Interface]:
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

    def peer_interfaces(self) -> list[Interface]:
        peer_ifaces = []
        for iface in self.interfaces():
            peer_iface = iface.peer_interface
            if peer_iface is not None and peer_iface not in peer_ifaces:
                peer_ifaces.append(peer_iface)
        return peer_ifaces

    def peer_nodes(self) -> list[Node]:
        return list({iface.node for iface in self.peer_interfaces()})

    def links(self) -> list[Link]:
        return list(
            {link for iface in self.interfaces() if (link := iface.link) is not None}
        )

    def degree(self) -> int:
        self.lab.sync_topology_if_outdated()
        return len(self.links())

    @property
    def label(self) -> str:
        self.lab.sync_topology_if_outdated()
        return self._label

    @label.setter
    def label(self, value: str) -> None:
        self._set_node_property("label", value)
        self._label = value

    @property
    def x(self) -> int:
        self.lab.sync_topology_if_outdated()
        return self._x

    @x.setter
    def x(self, value: int) -> None:
        self._set_node_property("x", value)
        self._x = value

    @property
    def y(self) -> int:
        self.lab.sync_topology_if_outdated()
        return self._y

    @y.setter
    def y(self, value: int) -> None:
        self._set_node_property("y", value)
        self._y = value

    @property
    def ram(self) -> int:
        self.lab.sync_topology_if_outdated()
        return self._ram

    @ram.setter
    def ram(self, value: int) -> None:
        self._set_node_property("ram", value)
        self._ram = value

    @property
    def cpus(self) -> int:
        self.lab.sync_topology_if_outdated()
        return self._cpus

    @cpus.setter
    def cpus(self, value: int) -> None:
        self._set_node_property("cpus", value)
        self._cpus = value

    @property
    def cpu_limit(self) -> int:
        self.lab.sync_topology_if_outdated()
        return self._cpu_limit

    @cpu_limit.setter
    def cpu_limit(self, value: int) -> None:
        self._set_node_property("cpu_limit", value)
        self._cpu_limit = value

    @property
    def data_volume(self) -> int:
        self.lab.sync_topology_if_outdated()
        return self._data_volume

    @data_volume.setter
    def data_volume(self, value: int) -> None:
        self._set_node_property("data_volume", value)
        self._data_volume = value

    @property
    def hide_links(self) -> bool:
        self.lab.sync_topology_if_outdated()
        return self._hide_links

    @hide_links.setter
    def hide_links(self, value: bool) -> None:
        self._set_node_property("hide_links", value)
        self._hide_links = value

    @property
    def boot_disk_size(self) -> int:
        self.lab.sync_topology_if_outdated()
        return self._boot_disk_size

    @boot_disk_size.setter
    def boot_disk_size(self, value: int) -> None:
        self._set_node_property("boot_disk_size", value)
        self._boot_disk_size = value

    @property
    def configuration(self) -> Optional[str]:
        # TODO: auto sync if out of date
        return self._configuration

    @configuration.setter
    def configuration(self, value) -> None:
        self._set_node_property("configuration", value)
        self._configuration = value

    @property
    def config(self) -> Optional[str]:
        warnings.warn(CONFIG_WARNING, DeprecationWarning)
        return self.configuration

    @config.setter
    def config(self, value: str) -> None:
        warnings.warn(CONFIG_WARNING, DeprecationWarning)
        self.configuration = value

    @property
    def image_definition(self) -> Optional[str]:
        self.lab.sync_topology_if_outdated()
        return self._image_definition

    @image_definition.setter
    def image_definition(self, value: str) -> None:
        self.lab.sync_topology_if_outdated()
        self._set_node_property("image_definition", value)
        self._image_definition = value

    @property
    def node_definition(self) -> str:
        self.lab.sync_topology_if_outdated()
        return self._node_definition

    @property
    def compute_id(self):
        self.lab.sync_operational_if_outdated()
        return self._compute_id

    @property
    def resource_pool(self) -> str:
        self.lab.sync_operational_if_outdated()
        return self._resource_pool

    @property
    def lab_base_url(self) -> str:
        return self.lab.lab_base_url

    @property
    def _base_url(self) -> str:
        return self.lab_base_url + "/nodes/{}".format(self.id)

    @property
    def cpu_usage(self) -> int | float:
        self.lab.sync_statistics_if_outdated()
        return min(self.statistics["cpu_usage"], 100)

    @property
    def disk_read(self) -> int:
        self.lab.sync_statistics_if_outdated()
        return round(self.statistics["disk_read"] / 1048576)

    @property
    def disk_write(self) -> int:
        self.lab.sync_statistics_if_outdated()
        return round(self.statistics["disk_write"] / 1048576)

    def get_interface_by_label(self, label: str) -> Interface:
        for iface in self.interfaces():
            if iface.label == label:
                return iface
        raise InterfaceNotFound("{}:{}".format(label, self))

    def get_interface_by_slot(self, slot: int) -> Interface:
        for iface in self.interfaces():
            if iface.slot == slot:
                return iface
        raise InterfaceNotFound("{}:{}".format(slot, self))

    def get_links_to(self, other_node: Node) -> list[Link]:
        """
        Returns all links between this node and another.

        :param other_node: the other node
        :returns: a list of links
        """
        links = []
        for link in self.links():
            if other_node in link.nodes:
                links.append(link)
        return links

    def get_link_to(self, other_node: Node) -> Optional[Link]:
        """
        Returns one link between this node and another.

        :param other_node: the other node
        :returns: a link, if one exists
        """
        for link in self.links():
            if other_node in link.nodes:
                return link
        return None

    def wait_until_converged(
        self, max_iterations: Optional[int] = None, wait_time: Optional[int] = None
    ) -> None:
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

    def has_converged(self) -> bool:
        url = self._base_url + "/check_if_converged"
        return self._session.get(url).json()

    def start(self, wait=False) -> None:
        url = self._base_url + "/state/start"
        self._session.put(url)
        if self.lab.need_to_wait(wait):
            self.wait_until_converged()

    def stop(self, wait=False) -> None:
        url = self._base_url + "/state/stop"
        self._session.put(url)
        if self.lab.need_to_wait(wait):
            self.wait_until_converged()

    def wipe(self, wait=False) -> None:
        url = self._base_url + "/wipe_disks"
        self._session.put(url)
        if self.lab.need_to_wait(wait):
            self.wait_until_converged()

    def extract_configuration(self) -> None:
        url = self._base_url + "/extract_configuration"
        self._session.put(url)

    def console_logs(self, console_id: int, lines: Optional[int] = None) -> dict:
        query = "?lines=%d" % lines if lines else ""
        url = self._base_url + "/consoles/%d/log%s" % (console_id, query)
        return self._session.get(url).json()

    def console_key(self) -> str:
        url = self._base_url + "/keys/console"
        return self._session.get(url).json()

    def vnc_key(self) -> str:
        url = self._base_url + "/keys/vnc"
        return self._session.get(url).json()

    def remove_on_server(self) -> None:
        _LOGGER.info("Removing node %s", self)
        url = self._base_url
        self._session.delete(url)

    def tags(self) -> list[str]:
        """Returns the tags set on this node"""
        self.lab.sync_topology_if_outdated()
        return self._tags

    def add_tag(self, tag: str) -> None:
        current = self.tags()
        if tag not in current:
            current.append(tag)
            self._set_node_property("tags", current)

    def remove_tag(self, tag: str) -> None:
        current = self.tags()
        current.remove(tag)
        self._set_node_property("tags", current)

    def run_pyats_command(self, command: str) -> str:
        """Run a pyATS command in exec mode.

        :param command: the command (like "show version")
        :returns: the output from the device
        """
        label = self.label
        return self.lab.pyats.run_command(label, command)

    def run_pyats_config_command(self, command: str) -> str:
        """Run a pyATS command in config mode.

        :param command: the command (like "interface gi0")
        :returns: the output from the device
        """
        label = self.label
        return self.lab.pyats.run_config_command(label, command)

    def sync_layer3_addresses(self) -> None:
        """Acquire all L3 addresses from the controller. For this
        to work, the device has to be attached to the external network
        in bridge mode and must run DHCP to acquire an IP address.
        """
        # TODO: can optimise the sync of l3 to only be for the node
        # rather than whole lab
        url = self._base_url + "/layer3_addresses"
        result = self._session.get(url).json()
        interfaces = result.get("interfaces", {})
        self.map_l3_addresses_to_interfaces(interfaces)

    def sync_operational(self, response: dict[str, Any] = None):
        if response is None:
            url = self._base_url + "?operational=true"
            response = self._session.get(url).json()
        operational = response.get("operational", {})
        self._compute_id = operational.get("compute_id")
        self._resource_pool = operational.get("resource_pool")

    def map_l3_addresses_to_interfaces(
        self, mapping: dict[str, dict[str, str]]
    ) -> None:
        for mac_address, entry in mapping.items():
            label = entry.get("label")
            if not label:
                continue
            ipv4 = entry.get("ip4")
            ipv6 = entry.get("ip6")
            iface = self.get_interface_by_label(label)
            if not iface:
                continue
            iface.ip_snooped_info = {
                "mac_address": mac_address,
                "ipv4": ipv4,
                "ipv6": ipv6,
            }

    def update(
        self,
        node_data: dict[str, Any],
        exclude_configurations: bool,
        push_to_server: bool = False,
    ) -> None:
        if push_to_server:
            self._set_node_properties(node_data)
        if "data" in node_data:
            node_data = node_data["data"]

        for key, value in node_data.items():
            if key == "configuration" and exclude_configurations:
                continue
            if key == "operational":
                self.sync_operational(node_data)
                continue
            setattr(self, f"_{key}", value)

    def is_active(self) -> bool:
        active_states = {"STARTED", "QUEUED", "BOOTED"}
        return self.state in active_states

    def is_booted(self) -> bool:
        return self.state == "BOOTED"

    def _set_node_property(self, key: str, val: Any) -> None:
        _LOGGER.debug("Setting node property %s %s: %s", self, key, val)
        self._set_node_properties({key: val})

    def _set_node_properties(self, node_data: dict[str, Any]) -> None:
        self._session.patch(url=self._base_url, json=node_data)
