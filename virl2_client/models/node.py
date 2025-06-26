#
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
from copy import deepcopy
from typing import TYPE_CHECKING, Any

from ..exceptions import InterfaceNotFound, SmartAnnotationNotFound
from ..utils import _deprecated_argument, check_stale, get_url_from_template, locked
from ..utils import property_s as property

if TYPE_CHECKING:
    import httpx

    from .interface import Interface
    from .lab import Lab
    from .link import Link
    from .smart_annotation import SmartAnnotation

_LOGGER = logging.getLogger(__name__)


class Node:
    _URL_TEMPLATES = {
        "node": "{lab}/nodes/{id}?{CONFIG_MODE}",
        "state": "{lab}/nodes/{id}/state",
        "check_if_converged": "{lab}/nodes/{id}/check_if_converged",
        "start": "{lab}/nodes/{id}/state/start",
        "stop": "{lab}/nodes/{id}/state/stop",
        "wipe_disks": "{lab}/nodes/{id}/wipe_disks",
        "clone_image": "{lab}/nodes/{id}/clone_image",
        "extract_configuration": "{lab}/nodes/{id}/extract_configuration",
        "console_log": "{lab}/nodes/{id}/consoles/{console_id}/log",
        "console_log_lines": "{lab}/nodes/{id}/consoles/{console_id}/log?lines={lines}",
        "console_key": "{lab}/nodes/{id}/keys/console",
        "vnc_key": "{lab}/nodes/{id}/keys/vnc",
        "layer3_addresses": "{lab}/nodes/{id}/layer3_addresses",
        "operational": "{lab}/nodes/{id}?operational=true&exclude_configurations=true",
        "inteface_operational": "{lab}/nodes/{id}/interfaces?data=true&operational=true",
    }

    def __init__(
        self, lab: Lab, nid: str, label: str, node_definition: str, **kwargs
    ) -> None:
        """
        A VIRL2 node object representing a virtual machine that serves
        as a router, switch, or server.

        :param lab: The Lab instance to which this node belongs.
        :param nid: The ID of the node.
        :param label: The label of the node.
        :param node_definition: The definition of this node.
        :param kwargs: Optional parameters. See below.

        :Keyword Arguments:
            - image_definition: The definition of the image used by this node.
            - configuration: The initial configuration of this node.
            - x: The X coordinate of the node on the topology canvas.
            - y: The Y coordinate of the node on the topology canvas.
            - ram: The memory of the node in MiB (if applicable).
            - cpus: The number of CPUs in this node (if applicable).
            - cpu_limit: The CPU limit of the node (default is 100%).
            - data_volume: The size in GiB of the second HDD (if > 0).
            - boot_disk_size: The size in GiB of the boot disk
                (will expand to this size).
            - hide_links: A flag indicating whether the node's links should be hidden
                in UI visualization.
            - tags: A list of tags associated with the node.
            - resource_pool: The ID of the resource pool if the node is part
                of a resource pool.
            - pinned_compute_id: The ID of the compute this node is pinned to.
                The node will not run on any other compute.
        """
        self._lab: Lab = lab
        self._id: str = nid
        self._label: str = label
        self._node_definition: str = node_definition

        self._image_definition: str | None = kwargs.get("image_definition")
        configuration: list[dict[str, str]] | str | None = kwargs.get("configuration")
        if isinstance(configuration, str):
            configuration = [{"name": "Main", "content": configuration}]
        self._configuration: list[dict[str, str]] | None = configuration
        self._x: int = kwargs.get("x", 0)
        self._y: int = kwargs.get("y", 0)
        self._ram: int | None = kwargs.get("ram")
        self._cpus: int | None = kwargs.get("cpus")
        self._cpu_limit: int | None = kwargs.get("cpu_limit")
        self._data_volume: int | None = kwargs.get("data_volume")
        self._boot_disk_size: int | None = kwargs.get("boot_disk_size")
        self._hide_links: bool = kwargs.get("hide_links", False)
        self._tags: list[str] = kwargs.get("tags", [])
        self._resource_pool: str | None = kwargs.get("resource_pool")
        self._parameters: dict = kwargs.get("parameters", {})
        self._pinned_compute_id: str | None = kwargs.get("pinned_compute_id")

        self._state: str | None = None
        self._session: httpx.Client = lab._session
        self._compute_id: str | None = kwargs.get("compute_id")
        self._stale = False
        self._last_sync_l3_address_time = 0.0
        self._last_sync_interface_operational_time = 0.0

        self.statistics: dict[str, int | float] = {
            "cpu_usage": 0,
            "disk_read": 0,
            "disk_write": 0,
        }

    def __str__(self):
        return f"Node: {self._label}{' (STALE)' if self._stale else ''}"

    def __repr__(self):
        return (
            f"{self.__class__.__name__}("
            f"{str(self._lab)!r}, "
            f"{self._id!r}, "
            f"{self._label!r}, "
            f"{self._node_definition!r})"
        )

    def __eq__(self, other):
        if not isinstance(other, Node):
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
        """Return the lab of the node."""
        return self._lab

    @check_stale
    @locked
    def sync_l3_addresses_if_outdated(self) -> None:
        timestamp = time.time()
        if (
            self._lab.auto_sync
            and timestamp - self._last_sync_l3_address_time
            > self._lab.auto_sync_interval
        ):
            self.sync_layer3_addresses()

    @check_stale
    @locked
    def sync_interface_operational_if_outdated(self) -> None:
        timestamp = time.time()
        if (
            self._lab.auto_sync
            and timestamp - self._last_sync_interface_operational_time
            > self._lab.auto_sync_interval
        ):
            self.sync_interface_operational()

    @property
    @locked
    def state(self) -> str | None:
        """Return the state of the node."""
        self._lab.sync_states_if_outdated()
        if self._state is None:
            url = self._url_for("state")
            self._state = self._session.get(url).json()["state"]
        return self._state

    @check_stale
    @locked
    def interfaces(self) -> list[Interface]:
        """Return a list of interfaces on the node."""
        self._lab.sync_topology_if_outdated()
        return [iface for iface in self._lab.interfaces() if iface.node is self]

    @locked
    def physical_interfaces(self) -> list[Interface]:
        """Return a list of physical interfaces on the node."""
        self._lab.sync_topology_if_outdated()
        return [iface for iface in self.interfaces() if iface.physical]

    @check_stale
    @locked
    def create_interface(
        self, slot: int | None = None, wait: bool = False
    ) -> Interface:
        """
        Create an interface in the specified slot or, if no slot is given, in the
        next available slot.

        :param slot: The slot in which the interface will be created.
        :param wait: Wait for the creation to complete.
        :returns: The newly created interface.
        """
        return self._lab.create_interface(self, slot, wait=wait)

    @locked
    def next_available_interface(self, index: int = 0) -> Interface | None:
        """
        Return the next available physical interface on this node.

        Note: On XR 9000v, the first two physical interfaces are marked
        as "do not use"... Only the third physical interface can be used
        to connect to other nodes!

        :param index: An optional starting interface index (default: 0).
        :returns: An available physical interface or None if all existing
            ones are connected.
        """
        for _, iface in enumerate(self.interfaces(), index):
            if not iface.connected and iface.physical:
                return iface
        return None

    @locked
    def peer_interfaces(self) -> list[Interface]:
        """Return a list of interfaces connected to this node."""
        peer_ifaces = []
        for iface in self.interfaces():
            peer_iface = iface.peer_interface
            if peer_iface is not None and peer_iface not in peer_ifaces:
                peer_ifaces.append(peer_iface)
        return peer_ifaces

    @locked
    def peer_nodes(self) -> list[Node]:
        """Return a list of nodes connected to this node."""
        return list({iface.node for iface in self.peer_interfaces()})

    @locked
    def links(self) -> list[Link]:
        """Return a list of links connected to this node."""
        return list(
            {link for iface in self.interfaces() if (link := iface.link) is not None}
        )

    @locked
    def degree(self) -> int:
        """Return the degree of the node."""
        self._lab.sync_topology_if_outdated()
        return len(self.links())

    @property
    def id(self) -> str:
        """Return the ID of the node."""
        return self._id

    @property
    def label(self) -> str:
        """Return the label of the node."""
        self._lab.sync_topology_if_outdated()
        return self._label

    @label.setter
    @locked
    def label(self, value: str) -> None:
        """Set the label of the node to the given value."""
        self._set_node_property("label", value)
        self._label = value

    @property
    def x(self) -> int:
        """Return the X coordinate of the node."""
        self._lab.sync_topology_if_outdated()
        return self._x

    @x.setter
    @locked
    def x(self, value: int) -> None:
        """Set the X coordinate of the node to the given value."""
        self._set_node_property("x", value)
        self._x = value

    @property
    def y(self) -> int:
        """Return the Y coordinate of the node."""
        self._lab.sync_topology_if_outdated()
        return self._y

    @y.setter
    @locked
    def y(self, value: int) -> None:
        """Set the Y coordinate of the node to the given value."""
        self._set_node_property("y", value)
        self._y = value

    @property
    def ram(self) -> int:
        """Return the RAM size of the node in bytes."""
        self._lab.sync_topology_if_outdated()
        return self._ram

    @ram.setter
    @locked
    def ram(self, value: int) -> None:
        """Set the RAM size of the node to the given value in bytes."""
        self._set_node_property("ram", value)
        self._ram = value

    @property
    def cpus(self) -> int:
        """Return the number of CPUs assigned to the node."""
        self._lab.sync_topology_if_outdated()
        return self._cpus

    @cpus.setter
    @locked
    def cpus(self, value: int) -> None:
        """Set the number of CPUs assigned to the node."""
        self._set_node_property("cpus", value)
        self._cpus = value

    @property
    def cpu_limit(self) -> int:
        """Return the CPU limit of the node."""
        self._lab.sync_topology_if_outdated()
        return self._cpu_limit

    @cpu_limit.setter
    @locked
    def cpu_limit(self, value: int) -> None:
        """Set the CPU limit of the node."""
        self._set_node_property("cpu_limit", value)
        self._cpu_limit = value

    @property
    def data_volume(self) -> int:
        """Return the size (in GiB) of the second HDD."""
        self._lab.sync_topology_if_outdated()
        return self._data_volume

    @data_volume.setter
    @locked
    def data_volume(self, value: int) -> None:
        """Set the size (in GiB) of the second HDD."""
        self._set_node_property("data_volume", value)
        self._data_volume = value

    @property
    def hide_links(self) -> bool:
        """
        Return a flag indicating whether the node's links should be hidden
        in UI visualization.
        """
        self._lab.sync_topology_if_outdated()
        return self._hide_links

    @hide_links.setter
    def hide_links(self, value: bool) -> None:
        """
        Set the flag indicating whether the node's links should be hidden
        in UI visualization.
        """
        self._set_node_property("hide_links", value)
        self._hide_links = value

    @property
    def boot_disk_size(self) -> int:
        """Return the size of the boot disk in GiB."""
        self._lab.sync_topology_if_outdated()
        return self._boot_disk_size

    @boot_disk_size.setter
    @locked
    def boot_disk_size(self, value: int) -> None:
        """Set the size of the boot disk in GiB (will expand to this size)."""
        self._set_node_property("boot_disk_size", value)
        self._boot_disk_size = value

    @property
    def configuration(self) -> str | None:
        """Return the contents of the main configuration file."""
        self._lab.sync_topology_if_outdated(exclude_configurations=False)
        return self._configuration[0].get("content") if self._configuration else None

    @configuration.setter
    def configuration(self, value: str | list | dict | None) -> None:
        """Set the configuration."""
        self._set_node_property("configuration", value)
        self._set_configuration(value)

    def _set_configuration(self, value: str | list | dict | None) -> None:
        """
        Set the content of:
         - the main configuration file if passed a string,
         - one configuration file if passed a dictionary in the format of
        `{"name": "filename.txt", "content": "<file content>"}`,
         - or multiple configuration files if passed a list of above dictionaries.
        Can also use "Main" in place of the filename of the main configuration file.

        :param value: The configuration data in one of three formats.
        """
        if self._configuration is None:
            self._configuration = []
        if isinstance(value, str):
            if self._configuration:
                self._configuration[0]["content"] = value
            else:
                self._configuration.append({"name": "Main", "content": value})
            return
        if not value:
            self._configuration = []
            return
        new_configs = value if isinstance(value, list) else [value]
        current_configs = {
            config["name"]: idx for idx, config in enumerate(self._configuration)
        }
        for config in new_configs:
            if config["name"] in current_configs:
                self._configuration[current_configs[config["name"]]] = config
            else:
                self._configuration.append(config)

    @property
    def configuration_files(self) -> list[dict[str, str]] | None:
        """
        Return all configuration files, in a list in the following format:
        `[{"name": "filename.txt", "content": "<file content>"}]`
        """
        self._lab.sync_topology_if_outdated(exclude_configurations=False)
        return deepcopy(self._configuration)

    @property
    def config(self) -> str | None:
        """
        DEPRECATED: Use `.configuration` instead.
        (Reason: consistency with API)

        Return the initial configuration of this node.
        """
        warnings.warn(
            "'Node.config' is deprecated. Use '.configuration' instead.",
        )
        return self.configuration

    @config.setter
    @locked
    def config(self, value: str) -> None:
        """
        DEPRECATED: Use `.configuration` instead.
        (Reason: consistency with API)

        Set the initial configuration of this node.
        """
        warnings.warn(
            "'Node.config' is deprecated. Use '.configuration' instead.",
        )
        self.configuration = value

    @property
    def parameters(self) -> dict:
        """Return node parameters."""
        self._lab.sync_topology_if_outdated()
        return self._parameters

    def update_parameters(self, new_params: dict) -> None:
        """
        Update node parameters.
        If parameter doesn't exist it will be created. Existing nodes will be updated.
        To delete parameter set its value to None.
        """
        self._session.patch(self._url_for("node"), json={"parameters": new_params})
        self._parameters.update(new_params)
        for key, value in new_params.items():
            if value is None:
                self._parameters.pop(key, None)

    @property
    def image_definition(self) -> str | None:
        """Return the definition of the image used by this node."""
        self._lab.sync_topology_if_outdated()
        return self._image_definition

    @image_definition.setter
    @locked
    def image_definition(self, value: str) -> None:
        """Set the definition of the image used by this node."""
        self._set_node_property("image_definition", value)
        self._image_definition = value

    @property
    def node_definition(self) -> str:
        """Return the definition of this node."""
        self._lab.sync_topology_if_outdated()
        return self._node_definition

    @property
    def compute_id(self):
        """Return the ID of the compute this node is assigned to."""
        self._lab.sync_operational_if_outdated()
        return self._compute_id

    @property
    def resource_pool(self) -> str:
        """Return the ID of the resource pool if the node is part of a resource pool."""
        self._lab.sync_operational_if_outdated()
        return self._resource_pool

    @property
    def pinned_compute_id(self) -> str | None:
        """Return the ID of the compute this node is pinned to."""
        self._lab.sync_operational_if_outdated()
        return self._pinned_compute_id

    @pinned_compute_id.setter
    def pinned_compute_id(self, value) -> None:
        """Set the ID of the compute this node should be pinned to."""
        self._set_node_property("pinned_compute_id", value)
        self._pinned_compute_id = value

    @property
    def cpu_usage(self) -> int | float:
        """Return the CPU usage of this node."""
        self._lab.sync_statistics_if_outdated()
        return min(self.statistics["cpu_usage"], 100)

    @property
    def disk_read(self) -> int:
        """Return the amount of disk read by this node."""
        self._lab.sync_statistics_if_outdated()
        return round(self.statistics["disk_read"] / 1048576)

    @property
    def disk_write(self) -> int:
        """Return the amount of disk write by this node."""
        self._lab.sync_statistics_if_outdated()
        return round(self.statistics["disk_write"] / 1048576)

    @property
    def smart_annotations(self) -> dict[str, SmartAnnotation]:
        """Return the tags on this node and their corresponding smart annotations."""
        self._lab.sync_topology_if_outdated()
        return {tag: self._lab.get_smart_annotation_by_tag(tag) for tag in self._tags}

    @locked
    def get_interface_by_label(self, label: str) -> Interface:
        """
        Get the interface of the node with the specified label.

        :param label: The label of the interface.
        :returns: The interface with the specified label.
        :raises InterfaceNotFound: If no interface with the specified label is found.
        """
        for iface in self.interfaces():
            if iface.label == label:
                return iface
        raise InterfaceNotFound(label)

    @locked
    def get_interface_by_slot(self, slot: int) -> Interface:
        """
        Get the interface of the node with the specified slot.

        :param slot: The slot number of the interface.
        :returns: The interface with the specified slot.
        :raises InterfaceNotFound: If no interface with the specified slot is found.
        """
        for iface in self.interfaces():
            if iface.slot == slot:
                return iface
        raise InterfaceNotFound(slot)

    def get_links_to(self, other_node: Node) -> list[Link]:
        """
        Return all links between this node and another.

        :param other_node: The other node.
        :returns: A list of links between this node and the other node.
        """
        links = []
        for link in self.links():
            if other_node in link.nodes:
                links.append(link)
        return links

    def get_link_to(self, other_node: Node) -> Link | None:
        """
        Return one link between this node and another.

        :param other_node: The other node.
        :returns: A link between this node and the other node, if one exists.
        """
        for link in self.links():
            if other_node in link.nodes:
                return link
        return None

    @check_stale
    def wait_until_converged(
        self, max_iterations: int | None = None, wait_time: int | None = None
    ) -> None:
        """
        Wait until the node has converged.

        :param max_iterations: The maximum number of iterations to wait for convergence.
        :param wait_time: The time to wait between iterations.
        :raises RuntimeError: If the node does not converge within the specified number
            of iterations.
        """
        _LOGGER.info(f"Waiting for node {self.id} to converge.")
        max_iter = (
            self._lab.wait_max_iterations if max_iterations is None else max_iterations
        )
        wait_time = self._lab.wait_time if wait_time is None else wait_time
        for index in range(max_iter):
            converged = self.has_converged()
            if converged:
                _LOGGER.info(f"Node {self.id} has converged.")
                return

            if index % 10 == 0:
                _LOGGER.info(
                    f"Node has not converged, attempt {index}/{max_iter}, waiting..."
                )
            time.sleep(wait_time)

        msg = f"Node {self.id} has not converged, maximum tries {max_iter} exceeded."
        _LOGGER.error(msg)
        # after maximum retries are exceeded and node has not converged
        # error must be raised - it makes no sense to just log info
        # and let client fail with something else if wait is explicitly
        # specified
        raise RuntimeError(msg)

    @check_stale
    def has_converged(self) -> bool:
        """
        Check if the node has converged.

        :returns: True if the node has converged, False otherwise.
        """
        url = self._url_for("check_if_converged")
        return self._session.get(url).json()

    @check_stale
    def start(self, wait=False) -> None:
        """
        Start the node.

        :param wait: Whether to wait until the node has converged.
        """
        url = self._url_for("start")
        self._session.put(url)
        if self._lab.need_to_wait(wait):
            self.wait_until_converged()

    @check_stale
    def stop(self, wait=False) -> None:
        """
        Stop the node.

        :param wait: Whether to wait until the node has converged.
        """
        url = self._url_for("stop")
        self._session.put(url)
        if self._lab.need_to_wait(wait):
            self.wait_until_converged()

    @check_stale
    def wipe(self, wait=False) -> None:
        """
        Wipe the node's disks.

        :param wait: Whether to wait until the node has converged.
        """
        url = self._url_for("wipe_disks")
        self._session.put(url)
        if self._lab.need_to_wait(wait):
            self.wait_until_converged()

    @check_stale
    def clone_image(self) -> dict:
        """
        Clone the node's disks into a new Image definition.
        """
        url = self._url_for("clone_image")
        return self._session.put(url).json()

    @check_stale
    def extract_configuration(self) -> None:
        """Update the configuration from the running node."""
        url = self._url_for("extract_configuration")
        self._session.put(url)

    @check_stale
    def console_logs(self, console_id: int, lines: int | None = None) -> dict:
        """
        Get the console logs of the node.

        :param console_id: The ID of the console.
        :param lines: Limit the number of lines to retrieve.
        :returns: A dictionary containing the console logs.
        """
        if lines:
            url = self._url_for("console_log_lines", console_id=console_id, lines=lines)
        else:
            url = self._url_for("console_log", console_id=console_id)
        return self._session.get(url).json()

    @check_stale
    def console_key(self) -> str:
        """
        Get the console key of the node.

        :returns: The console key.
        """
        url = self._url_for("console_key")
        return self._session.get(url).json()

    @check_stale
    def vnc_key(self) -> str:
        """
        Get the VNC key of the node.

        :returns: The VNC key.
        """
        url = self._url_for("vnc_key")
        return self._session.get(url).json()

    def remove(self) -> None:
        """Remove the node from the system."""
        self._lab.remove_node(self)

    @check_stale
    def _remove_on_server(self) -> None:
        """Helper function to remove the node from the server."""
        _LOGGER.info(f"Removing node {self}")
        url = self._url_for("node")
        self._session.delete(url)

    def remove_on_server(self) -> None:
        """
        DEPRECATED: Use `.remove()` instead.
        (Reason: was never meant to be public, removing only on server is not useful)

        Remove the node on the server.
        """
        warnings.warn(
            "'Node.remove_on_server()' is deprecated. Use '.remove()' instead.",
        )
        # To not change behavior of scripts, this will still remove on server only.
        self._remove_on_server()

    @check_stale
    def tags(self) -> list[str]:
        """
        Get the tags set on this node.

        :returns: A list of tags.
        """
        self._lab.sync_topology_if_outdated()
        return self._tags

    @locked
    def add_tag(self, tag: str) -> None:
        """
        Add a tag to this node.

        :param tag: The tag to add.
        """
        current = self.tags()
        if tag not in current:
            current.append(tag)
            self._set_node_property("tags", current)
        try:
            self._lab.get_smart_annotation_by_tag(tag)
        except SmartAnnotationNotFound:
            # Smart annotations will be automatically created serverside for the new
            # tags, so we force a sync to retrieve them
            self._lab._sync_topology(exclude_configurations=True)

    @locked
    def remove_tag(self, tag: str) -> None:
        """
        Remove a tag from this node.

        :param tag: The tag to remove.
        """
        self._remove_tag_on_server(tag)

        for node in self._lab._nodes.values():
            if tag in node._tags:
                # Tag still exists, smart annotation was not removed
                return

        # Smart annotations for tags removed from all nodes will be automatically
        # removed serverside, so we remove them locally as well
        try:
            annotation = self._lab.get_smart_annotation_by_tag(tag)
        except SmartAnnotationNotFound:
            # get_smart_annotation_by_tag probably happened to sync and removed the
            # annotation already
            return
        self._lab._remove_smart_annotation_local(annotation)

    def _remove_tag_on_server(self, tag) -> None:
        """Helper function to remove the tag from the node on the server."""
        current = self.tags()
        current.remove(tag)
        self._set_node_property("tags", current)

    def run_pyats_command(self, command: str, **pyats_params: Any) -> str:
        """
        Run a pyATS command in exec mode on the node.

        :param command: The command to run (e.g. "show version").
        :param pyats_params: Custom command dialog parameters for PyATS
        :returns: The output from the device.
        """
        label = self.label
        return self._lab.pyats.run_command(label, command, **pyats_params)

    def run_pyats_config_command(self, command: str, **pyats_params: Any) -> str:
        """
        Run a pyATS command in config mode on the node.

        :param command: The command to run (e.g. "interface gi0").
        :param pyats_params: Custom command dialog parameters for PyATS
        :returns: The output from the device.
        """
        label = self.label
        return self._lab.pyats.run_config_command(label, command, **pyats_params)

    @check_stale
    @locked
    def sync_layer3_addresses(self) -> None:
        """
        Acquire all layer 3 addresses from the controller.

        For this to work, the device has to be attached to the external network
        in bridge mode and must run DHCP to acquire an IP address.
        """
        url = self._url_for("layer3_addresses")
        result = self._session.get(url).json()
        interfaces = result.get("interfaces", {})
        self.map_l3_addresses_to_interfaces(interfaces)

    @check_stale
    @locked
    def map_l3_addresses_to_interfaces(
        self, mapping: dict[str, dict[str, str]]
    ) -> None:
        """
        Map layer 3 addresses to interfaces.

        :param mapping: A dictionary mapping MAC addresses to interface information.
        """
        for mac_address, entry in mapping.items():
            if not (label := entry.get("label")):
                continue
            try:
                iface = self.get_interface_by_label(label)
            except InterfaceNotFound:
                continue
            ipv4 = entry.get("ip4")
            ipv6 = entry.get("ip6")
            iface._ip_snooped_info = {
                "mac_address": mac_address,
                "ipv4": ipv4,
                "ipv6": ipv6,
            }
        self._last_sync_l3_address_time = time.time()

    @check_stale
    @locked
    def sync_operational(
        self, response: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Synchronize the operational state of the node.

        :param response: If the operational data was fetched from the server elsewhere,
            it can be passed here to save an API call. Will be fetched automatically
            otherwise.
        """
        if response is None:
            url = self._url_for("operational")
            response = self._session.get(url).json()
        if response is None:
            return {}
        self._pinned_compute_id = response.get("pinned_compute_id")
        operational = response.get("operational", {})
        self._compute_id = operational.get("compute_id")
        self._resource_pool = operational.get("resource_pool")
        return operational

    @check_stale
    @locked
    def sync_interface_operational(self):
        """Synchronize the operational state of the node's interfaces."""
        url = self._url_for("inteface_operational")
        response = self._session.get(url).json()
        self._lab.sync_topology_if_outdated()
        for interface_data in response:
            interface = self._lab._interfaces[interface_data["id"]]
            operational = interface_data.get("operational", {})
            interface._deployed_mac_address = operational.get("mac_address")
        self._last_sync_interface_operational_time = time.time()

    def update(
        self,
        node_data: dict[str, Any],
        exclude_configurations: bool,
        push_to_server=None,
    ) -> None:
        """
        Update the node with the provided data.

        :param node_data: The data to update the node with.
        :param exclude_configurations: Whether to exclude configuration updates.
        :param push_to_server: DEPRECATED: Was only used by internal methods
            and should otherwise always be True.
        """
        _deprecated_argument(self.update, push_to_server, "push_to_server")
        self._update(node_data, exclude_configurations, push_to_server=True)

    @check_stale
    @locked
    def _update(
        self,
        node_data: dict[str, Any],
        exclude_configurations: bool,
        push_to_server: bool = True,
    ) -> None:
        """
        Update the node with the provided data.

        :param node_data: The data to update the node with.
        :param exclude_configurations: Whether to exclude configuration updates.
        :param push_to_server: Whether to push the changes to the server.
        """
        if push_to_server:
            self._set_node_properties(node_data)
        if "data" in node_data:
            node_data = node_data["data"]

        for key, value in node_data.items():
            if key == "configuration":
                if not exclude_configurations:
                    self._set_configuration(value)
                continue
            if key == "operational":
                self.sync_operational(node_data)
                continue
            setattr(self, f"_{key}", value)

    def is_active(self) -> bool:
        """
        Check if the node is in an active state.

        :returns: True if the node is in an active state, False otherwise.
        """
        active_states = {"STARTED", "QUEUED", "BOOTED"}
        return self.state in active_states

    def is_booted(self) -> bool:
        """
        Check if the node is booted.

        :returns: True if the node is booted, False otherwise.
        """
        return self.state == "BOOTED"

    def _set_node_property(self, key: str, val: Any) -> None:
        """
        Set a property of the node.

        :param key: The key of the property to set.
        :param val: The value to set.
        """
        _LOGGER.debug(f"Setting node property {self} {key}: {val}")
        self._set_node_properties({key: val})

    @check_stale
    def _set_node_properties(self, node_data: dict[str, Any]) -> None:
        """
        Set multiple properties of the node.

        :param node_data: A dictionary containing the properties to set.
        """
        url = self._url_for("node")
        self._session.patch(url, json=node_data)
