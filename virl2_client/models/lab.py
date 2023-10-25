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

import json
import logging
import time
import warnings
from typing import TYPE_CHECKING, Any, Iterable

from httpx import HTTPStatusError

from ..exceptions import (
    ElementAlreadyExists,
    InterfaceNotFound,
    LabNotFound,
    LinkNotFound,
    NodeNotFound,
    VirlException,
)
from ..utils import check_stale, get_url_from_template, locked
from ..utils import property_s as property
from .cl_pyats import ClPyats
from .interface import Interface
from .link import Link
from .node import Node

if TYPE_CHECKING:
    import httpx

    from .resource_pools import ResourcePool, ResourcePoolManagement


_LOGGER = logging.getLogger(__name__)


class Lab:
    _URL_TEMPLATES = {
        "lab": "labs/{lab_id}",
        "nodes": "labs/{lab_id}/nodes",
        "nodes_populated": "labs/{lab_id}/nodes?populate_interfaces=true",
        "links": "labs/{lab_id}/links",
        "interfaces": "labs/{lab_id}/interfaces",
        "simulation_stats": "labs/{lab_id}/simulation_stats",
        "lab_element_state": "labs/{lab_id}/lab_element_state",
        "check_if_converged": "labs/{lab_id}/check_if_converged",
        "start": "labs/{lab_id}/start",
        "stop": "labs/{lab_id}/stop",
        "state": "labs/{lab_id}/state",
        "wipe": "labs/{lab_id}/wipe",
        "events": "labs/{lab_id}/events",
        "build_configurations": "build_configurations?lab_id={lab_id}",
        "topology": "labs/{lab_id}/topology",
        "pyats_testbed": "labs/{lab_id}/pyats_testbed",
        "layer3_addresses": "labs/{lab_id}/layer3_addresses",
        "download": "labs/{lab_id}/download",
        "groups": "labs/{lab_id}/groups",
        "connector_mappings": "labs/{lab_id}/connector_mappings",
        "resource_pools": "labs/{lab_id}/resource_pools",
    }

    def __init__(
        self,
        title: str | None,
        lab_id: str,
        session: httpx.Client,
        username: str,
        password: str,
        auto_sync: bool = True,
        auto_sync_interval: float = 1.0,
        wait: bool = True,
        wait_max_iterations: int = 500,
        wait_time: int = 5,
        hostname: str | None = None,
        resource_pool_manager: ResourcePoolManagement | None = None,
    ) -> None:
        """
        A VIRL2 lab network topology.

        :param title: Name or title of the lab.
        :param lab_id: Lab ID.
        :param session: The httpx-based HTTP client for this session with the server.
        :param username: Username of the user to authenticate.
        :param password: Password of the user to authenticate.
        :param auto_sync: A flag indicating whether local changes should be
            automatically synced to the server.
        :param auto_sync_interval: Interval in seconds for automatic syncing.
        :param wait: A flag indicating whether to wait for convergence on the backend.
        :param wait_max_iterations: Maximum number of iterations for convergence.
        :param wait_time: Time in seconds to sleep between convergence calls
            on the backend.
        :param hostname: Hostname/IP and port for pyATS console terminal server.
        :param resource_pool_manager: ResourcePoolManagement object shared
            with parent ClientLibrary.
        :raises VirlException: If the lab object is created without
            a resource pool manager.
        """

        self.username = username
        self.password = password

        self._title = title
        self._description = ""
        self._notes = ""
        self._id = lab_id
        self._session = session
        self._owner = username
        self._state = None
        self._nodes: dict[str, Node] = {}
        """
        Dictionary containing all nodes in the lab.
        It maps node identifier to `models.Node`.
        """
        self._links: dict[str, Link] = {}
        """
        Dictionary containing all links in the lab.
        It maps link identifier to `models.Link`.
        """
        self._interfaces: dict[str, Interface] = {}
        """
        Dictionary containing all interfaces in the lab.
        It maps interface identifier to `models.Interface`.
        """
        self.events: list = []
        self.pyats = ClPyats(self, hostname)
        self.auto_sync = auto_sync
        self.auto_sync_interval = auto_sync_interval

        self._last_sync_statistics_time = 0.0
        self._last_sync_state_time = 0.0
        self._last_sync_l3_address_time = 0.0
        self._last_sync_topology_time = 0.0
        self._last_sync_operational_time = 0.0

        self._initialized = False

        self.wait_for_convergence = wait
        self.wait_max_iterations = wait_max_iterations
        self.wait_time = wait_time

        if resource_pool_manager is None:
            raise VirlException(
                f"Lab object for lab {title or lab_id} cannot be created "
                "because it is missing a resource pool manager."
            )
        self._resource_pool_manager = resource_pool_manager
        self._resource_pools = []
        self._stale = False
        self._synced_configs = True

    def __len__(self):
        return len(self._nodes)

    def __str__(self):
        return f"Lab: {self._title}{' (STALE)' if self._stale else ''}"

    def __repr__(self):
        return "{}({!r}, {!r}, {!r}, {!r}, {!r}, {!r})".format(
            self.__class__.__name__,
            self._title,
            self._id,
            self._session.base_url.path,
            self.auto_sync,
            self.auto_sync_interval,
            self.wait_for_convergence,
        )

    def _url_for(self, endpoint, **kwargs):
        """
        Generate the URL for a given API endpoint.

        :param endpoint: The desired endpoint.
        :param **kwargs: Keyword arguments used to format the URL.
        :returns: The formatted URL.
        """
        kwargs["lab_id"] = self._id
        return get_url_from_template(endpoint, self._URL_TEMPLATES, kwargs)

    def need_to_wait(self, local_wait: bool | None) -> bool:
        """
        Check if waiting is required.

        If `local_wait` is `None`, return the value of `wait_for_convergence`.
        If `local_wait` is not a boolean, raise a `ValueError`.

        :param local_wait: Local wait flag.
        :returns: True if waiting is required, False otherwise.
        :raises ValueError: If `local_wait` is not a boolean.
        """
        if local_wait is None:
            return self.wait_for_convergence
        if not isinstance(local_wait, bool):
            raise ValueError
        return local_wait

    @check_stale
    @locked
    def sync_statistics_if_outdated(self) -> None:
        """Sync statistics if they are outdated."""
        timestamp = time.time()
        if (
            self.auto_sync
            and timestamp - self._last_sync_statistics_time > self.auto_sync_interval
        ):
            self.sync_statistics()

    @check_stale
    @locked
    def sync_states_if_outdated(self) -> None:
        """Sync states if they are outdated."""
        timestamp = time.time()
        if (
            self.auto_sync
            and timestamp - self._last_sync_state_time > self.auto_sync_interval
        ):
            self.sync_states()

    @check_stale
    @locked
    def sync_l3_addresses_if_outdated(self) -> None:
        """Sync L3 addresses if they are outdated."""
        timestamp = time.time()
        if (
            self.auto_sync
            and timestamp - self._last_sync_l3_address_time > self.auto_sync_interval
        ):
            self.sync_layer3_addresses()

    @check_stale
    @locked
    def sync_topology_if_outdated(self, exclude_configurations=True) -> None:
        """Sync the topology if it is outdated."""
        timestamp = time.time()
        if not (exclude_configurations or self._synced_configs):
            self._sync_topology(exclude_configurations=False)
        elif (
            self.auto_sync
            and timestamp - self._last_sync_topology_time > self.auto_sync_interval
        ):
            self._sync_topology(exclude_configurations=exclude_configurations)
            self._synced_configs = not exclude_configurations

    @check_stale
    @locked
    def sync_operational_if_outdated(self) -> None:
        """Sync the operational data if it is outdated."""
        timestamp = time.time()
        if (
            self.auto_sync
            and timestamp - self._last_sync_operational_time > self.auto_sync_interval
        ):
            self.sync_operational()

    @property
    def id(self) -> str:
        """Return the ID of the lab (a 6 digit hex string)."""
        return self._id

    @property
    def title(self) -> str | None:
        """Return the title of the lab."""
        self.sync_topology_if_outdated()
        return self._title

    @title.setter
    def title(self, value: str) -> None:
        """Set the title of the lab."""
        self._set_property("title", value)

    @property
    def notes(self) -> str:
        """Return the notes of the lab."""
        self.sync_topology_if_outdated()
        return self._notes

    @notes.setter
    def notes(self, value: str) -> None:
        """Set the notes of the lab."""
        self._set_property("notes", value)

    @property
    def description(self) -> str:
        """Return the description of the lab."""
        self.sync_topology_if_outdated()
        return self._description

    @description.setter
    def description(self, value: str) -> None:
        """Set the description of the lab."""
        self._set_property("description", value)

    @check_stale
    @locked
    def _set_property(self, prop: str, value: Any):
        """
        Set the value of a lab property both locally and on the server.

        :param prop: The name of the property.
        :param value: The new value of the property.
        """
        url = self._url_for("lab")
        self._session.patch(url, json={prop: value})
        setattr(self, f"_{prop}", value)

    @property
    def owner(self) -> str:
        """Return the owner of the lab."""
        self.sync_topology_if_outdated()
        return self._owner

    @property
    def resource_pools(self) -> list[ResourcePool]:
        """Return the list of resource pools this lab's nodes belong to."""
        self.sync_operational_if_outdated()
        return self._resource_pools

    def nodes(self) -> list[Node]:
        """
        Return the list of nodes in the lab.

        :returns: A list of Node objects.
        """
        self.sync_topology_if_outdated()
        return list(self._nodes.values())

    def links(self) -> list[Link]:
        """
        Return the list of links in the lab.

        :returns: A list of Link objects.
        """
        self.sync_topology_if_outdated()
        return list(self._links.values())

    def interfaces(self) -> list[Interface]:
        """
        Return the list of interfaces in the lab.

        :returns: A list of Interface objects.
        """
        self.sync_topology_if_outdated()
        return list(self._interfaces.values())

    @property
    @locked
    def statistics(self) -> dict:
        """
        Return lab statistics.

        :returns: A dictionary with stats of the lab.
        """
        return {
            "nodes": len(self._nodes),
            "links": len(self._links),
            "interfaces": len(self._interfaces),
        }

    def get_node_by_id(self, node_id: str) -> Node:
        """
        Return the node identified by the ID.

        :param node_id: ID of the node to be returned.
        :returns: A Node object.
        :raises NodeNotFound: If the node is not found.
        """
        self.sync_topology_if_outdated()
        try:
            return self._nodes[node_id]
        except KeyError:
            raise NodeNotFound(node_id)

    def get_node_by_label(self, label: str) -> Node:
        """
        Return the node identified by the label.

        :param label: Label of the node to be returned.
        :returns: A Node object.
        :raises NodeNotFound: If the node is not found.
        """
        self.sync_topology_if_outdated()
        for node in self._nodes.values():
            if node.label == label:
                return node
        raise NodeNotFound(label)

    def get_interface_by_id(self, interface_id: str) -> Interface:
        """
        Return the interface identified by the ID.

        :param interface_id: ID of the interface to be returned.
        :returns: An Interface object.
        :raises InterfaceNotFound: If the interface is not found.
        """
        self.sync_topology_if_outdated()
        try:
            return self._interfaces[interface_id]
        except KeyError:
            raise InterfaceNotFound(interface_id)

    def get_link_by_id(self, link_id: str) -> Link:
        """
        Return the link identified by the ID.

        :param link_id: ID of the link to be returned.
        :returns: A Link object.
        :raises LinkNotFound: If the link is not found.
        """
        self.sync_topology_if_outdated()
        try:
            return self._links[link_id]
        except KeyError:
            raise LinkNotFound(link_id)

    @staticmethod
    def get_link_by_nodes(node1: Node, node2: Node) -> Link:
        """
        DEPRECATED: Use `Node.get_link_to()` to get one link
        or `Node.get_links_to()` to get all links.
        (Reason: redundancy)

        Return ONE of the links identified by two node objects.

        :param node1: The first node.
        :param node2: The second node.
        :returns: One of links between the nodes.
        :raises LinkNotFound: If no such link exists.
        """
        warnings.warn(
            "'Lab.get_link_by_nodes()' is deprecated. "
            "Use 'Node.get_link_to()' or 'Node.get_links_to()' instead.",
            DeprecationWarning,
        )
        if not (links := node1.get_links_to(node2)):
            raise LinkNotFound
        return links[0]

    @staticmethod
    def get_link_by_interfaces(iface1: Interface, iface2: Interface) -> Link | None:
        """
        DEPRECATED: Use `Interface.get_link_to()` instead.
        (Reason: redundancy)

        Return the link identified by two interface objects.

        :param iface1: The first interface.
        :param iface2: The second interface.
        :returns: The link between the interfaces.
        :raises LinkNotFound: If no such link exists.
        """
        warnings.warn(
            "'Lab.get_link_by_interfaces()' is deprecated. "
            "Use 'Interface.get_link_to()' instead.",
            DeprecationWarning,
        )
        if (link := iface1.link) is not None and iface2 in link.interfaces:
            return link
        raise LinkNotFound

    def find_nodes_by_tag(self, tag: str) -> list[Node]:
        """
        Return the nodes identified by the given tag.

        :param tag: The tag by which to search.
        :returns: A list of nodes.
        """
        self.sync_topology_if_outdated()
        return [node for node in self.nodes() if tag in node.tags()]

    @check_stale
    @locked
    def create_node(
        self,
        label: str,
        node_definition: str,
        x: int = 0,
        y: int = 0,
        wait: bool | None = None,
        populate_interfaces: bool = False,
        **kwargs,
    ) -> Node:
        """
        Create a node in the lab with the given parameters.

        :param label: Label.
        :param node_definition: Node definition.
        :param x: The X coordinate.
        :param y: The Y coordinate.
        :param wait: A flag indicating whether to wait for convergence.
            If left at the default value, the lab's wait property is used instead.
        :param populate_interfaces: Automatically create a pre-defined number
            of interfaces on node creation.
        :returns: A Node object.
        """
        try:
            self.get_node_by_label(label)
            _LOGGER.warning(f"Node with label {label} already exists.")
        except NodeNotFound:
            pass

        if populate_interfaces:
            url = self._url_for("nodes_populated")
        else:
            url = self._url_for("nodes")

        kwargs["label"] = label
        kwargs["node_definition"] = node_definition
        kwargs["x"] = x
        kwargs["y"] = y
        result: dict[str, str] = self._session.post(url, json=kwargs).json()
        node_id: str = result["id"]

        # if add node to an empty lab, then consider it "initialized" for sync purposes
        if not self._initialized:
            self._initialized = True

        if self.need_to_wait(wait):
            self.wait_until_lab_converged()

        for key in ("image_definition", "configuration"):
            if key not in kwargs:
                kwargs[key] = None

        if "compute_id" in kwargs:
            kwargs.pop("compute_id")
        kwargs["resource_pool"] = None
        node = self._create_node_local(node_id, **kwargs)
        return node

    def add_node_local(self, *args, **kwargs):
        """
        DEPRECATED: Use `.create_node()` instead.
        (Reason: only creates a node in the client, which is not useful;
        if really needed, use `._create_node_local()`)

        Creates a node in the client, but not on the server.
        """
        warnings.warn(
            "'Lab.add_node_local' is deprecated. You probably want .create_node "
            "instead. (If you really want to create a node locally only, "
            "use '._create_node_local()'.)",
            DeprecationWarning,
        )
        return self._create_node_local(*args, **kwargs)

    @locked
    def _create_node_local(
        self,
        node_id: str,
        label: str,
        node_definition: str,
        image_definition: str | None,
        configuration: list[dict[str, str]] | str | None,
        x: int,
        y: int,
        ram: int | None = None,
        cpus: int | None = None,
        cpu_limit: int | None = None,
        data_volume: int | None = None,
        boot_disk_size: int | None = None,
        hide_links: bool = False,
        tags: list | None = None,
        compute_id: str | None = None,
        resource_pool: ResourcePool | None = None,
        parameters: dict = {},
        locked_compute_id: str | None = None,
    ) -> Node:
        """Helper function to add a node to the client library."""
        if tags is None:
            tags = []

        node = Node(
            self,
            node_id,
            label,
            node_definition,
            image_definition,
            configuration,
            x,
            y,
            ram,
            cpus,
            cpu_limit,
            data_volume,
            boot_disk_size,
            hide_links,
            tags,
            resource_pool,
            parameters,
            locked_compute_id,
        )
        if compute_id is not None:
            node._compute_id = compute_id
        self._nodes[node.id] = node
        return node

    @check_stale
    @locked
    def remove_node(self, node: Node | str, wait: bool | None = None) -> None:
        """
        Remove a node from the lab.

        If you have a node object, you can also simply do::

            node.remove()


        :param node: The node object or ID.
        :param wait: A flag indicating whether to wait for convergence.
            If left at the default value, the lab's wait property is used instead.
        """
        if isinstance(node, str):
            node = self.get_node_by_id(node)
        node._remove_on_server()
        self._remove_node_local(node)

        if self.need_to_wait(wait):
            self.wait_until_lab_converged()
        _LOGGER.debug(f"{node._id} node removed from lab {self._id}")

    @locked
    def _remove_node_local(self, node: Node) -> None:
        """Helper function to remove a node from the client library."""
        for iface in tuple(self._interfaces.values()):
            if iface._node is node:
                self._remove_interface_local(iface)
        try:
            del self._nodes[node._id]
            node._stale = True
        except KeyError:
            # element may already have been deleted on server,
            # and removed locally due to auto-sync
            pass

    @locked
    def remove_nodes(self, wait: bool | None = None) -> None:
        """
        Remove all nodes from the lab.

        :param wait: A flag indicating whether to wait for convergence.
            If left at the default value, the lab's wait property is used instead.
        """
        # Use case - user was assigned one lab, wants to reset work;
        # can't delete lab, so removing all nodes is the only option
        for node in list(self._nodes.values()):
            self.remove_node(node, wait=False)

        if self.need_to_wait(wait):
            self.wait_until_lab_converged()
        _LOGGER.debug(f"all nodes removed from lab {self._id}")

    @check_stale
    @locked
    def remove_link(self, link: Link | str, wait: bool | None = None) -> None:
        """
        Remove a link from the lab.

        If you have a link object, you can also simply do::

            link.remove()

        :param link: The link object or ID.
        :param wait: A flag indicating whether to wait for convergence.
            If left at the default value, the lab's wait property is used instead.
        """
        if isinstance(link, str):
            link = self.get_link_by_id(link)
        link._remove_on_server()
        self._remove_link_local(link)

        if self.need_to_wait(wait):
            self.wait_until_lab_converged()
        _LOGGER.debug(f"link {link._id} removed from lab {self._id}")

    @locked
    def _remove_link_local(self, link: Link) -> None:
        """Helper function to remove a link from the client library."""
        try:
            del self._links[link._id]
            link._stale = True
        except KeyError:
            # element may already have been deleted on server,
            # and removed locally due to auto-sync
            pass

    @check_stale
    @locked
    def remove_interface(
        self, iface: Interface | str, wait: bool | None = None
    ) -> None:
        """
        Remove an interface from the lab.

        If you have an interface object, you can also simply do::

            interface.remove()

        :param iface: The interface object or ID.
        :param wait: A flag indicating whether to wait for convergence.
            If left at the default value, the lab's wait property is used instead.
        """
        if isinstance(iface, str):
            iface = self.get_interface_by_id(iface)
        iface._remove_on_server()

        self._remove_interface_local(iface)

        if self.need_to_wait(wait):
            self.wait_until_lab_converged()
        _LOGGER.debug(f"interface {iface._id} removed from lab {self._id}")

    @locked
    def _remove_interface_local(self, iface: Interface) -> None:
        """Helper function to remove an interface from the client library."""
        for link in tuple(self._links.values()):
            if iface in link.interfaces:
                self._remove_link_local(link)
                break
        try:
            del self._interfaces[iface._id]
            iface._stale = True
        except KeyError:
            # element may already have been deleted on server, and removed
            # locally due to auto-sync
            pass

    @check_stale
    @locked
    def create_link(
        self, i1: Interface | str, i2: Interface | str, wait: bool | None = None
    ) -> Link:
        """
        Create a link between two interfaces.

        :param i1: The first interface object or ID.
        :param i2: The second interface object or ID.
        :param wait: A flag indicating whether to wait for convergence.
            If left at the default value, the lab's wait property is used instead.
        :returns: The created link.
        """
        if isinstance(i1, str):
            i1 = self.get_interface_by_id(i1)
        if isinstance(i2, str):
            i2 = self.get_interface_by_id(i2)
        url = self._url_for("links")
        data = {
            "src_int": i1.id,
            "dst_int": i2.id,
        }
        response = self._session.post(url, json=data)
        result = response.json()
        link_id = result["id"]
        label = result.get("label")

        if self.need_to_wait(wait):
            self.wait_until_lab_converged()

        link = self._create_link_local(i1, i2, link_id, label)
        return link

    @check_stale
    @locked
    def _create_link_local(
        self, i1: Interface, i2: Interface, link_id: str, label: str | None = None
    ) -> Link:
        """Helper function to create a link in the client library."""
        link = Link(self, link_id, i1, i2, label)
        self._links[link_id] = link
        return link

    @check_stale
    @locked
    def connect_two_nodes(self, node1: Node, node2: Node) -> Link:
        """
        Connect two nodes within a lab.

        :param node1: The first node object.
        :param node2: The second node object.
        :returns: The created link.
        """
        iface1 = node1.next_available_interface() or node1.create_interface()
        iface2 = node2.next_available_interface() or node2.create_interface()
        return self.create_link(iface1, iface2)

    @check_stale
    @locked
    def create_interface(
        self, node: Node | str, slot: int | None = None, wait: bool | None = None
    ) -> Interface:
        """
        Create an interface in the next available slot, or, if a slot is specified,
        in all available slots up to and including the specified slot.

        :param node: The node on which the interface is created.
        :param slot: The slot number to create the interface in.
        :param wait: A flag indicating whether to wait for convergence.
            If left at the default value, the lab's wait property is used instead.
        :returns: The newly created interface.
        """
        if isinstance(node, str):
            node = self.get_node_by_id(node)
        url = self._url_for("interfaces")
        payload: dict[str, str | int] = {"node": node.id}
        if slot is not None:
            payload["slot"] = slot
        result = self._session.post(url, json=payload).json()
        if isinstance(result, dict):
            # in case API returned just one interface, pack it into a list:
            result = [result]

        if self.need_to_wait(wait):
            self.wait_until_lab_converged()

        desired_interface: Interface | None = None
        for iface in result:
            lab_interface = self._create_interface_local(
                iface_id=iface["id"],
                label=iface["label"],
                node=node,
                slot=iface["slot"],
            )
            if slot == iface["slot"] or slot is None:
                desired_interface = lab_interface

        if desired_interface is None:
            # Shouldn't happen, but type checkers complain about desired_interface
            # possibly being None otherwise
            raise InterfaceNotFound

        return desired_interface

    @check_stale
    @locked
    def _create_interface_local(
        self,
        iface_id: str,
        label: str,
        node: Node,
        slot: int | None,
        iface_type: str = "physical",
    ) -> Interface:
        """Helper function to create an interface in the client library."""
        if iface_id not in self._interfaces:
            iface = Interface(iface_id, node, label, slot, iface_type)
            self._interfaces[iface_id] = iface
        else:  # update the interface if it already exists:
            iface = self._interfaces[iface_id]
            iface._node = node
            iface._label = label
            iface._slot = slot
            iface._type = iface_type
        return iface

    @check_stale
    @locked
    def sync_statistics(self) -> None:
        """Retrieve the simulation statistic data from the back end server."""

        def _get_element_from_data(data: dict, element: str) -> int:
            try:
                return int(data[element])
            except (TypeError, KeyError):
                return 0

        url = self._url_for("simulation_stats")
        states: dict[str, dict[str, dict]] = self._session.get(url).json()
        node_statistics = states.get("nodes", {})
        link_statistics = states.get("links", {})
        for node_id, node_data in node_statistics.items():
            disk_read = _get_element_from_data(node_data, "block0_rd_bytes")
            disk_write = _get_element_from_data(node_data, "block0_wr_bytes")

            self._nodes[node_id].statistics = {
                "cpu_usage": float(node_data.get("cpu_usage", 0)),
                "disk_read": disk_read,
                "disk_write": disk_write,
            }

        for link_id, link_data in link_statistics.items():
            readbytes = _get_element_from_data(link_data, "readbytes")
            readpackets = _get_element_from_data(link_data, "readpackets")
            writebytes = _get_element_from_data(link_data, "writebytes")
            writepackets = _get_element_from_data(link_data, "writepackets")

            link = self._links[link_id]
            link.statistics = {
                "readbytes": readbytes,
                "readpackets": readpackets,
                "writebytes": writebytes,
                "writepackets": writepackets,
            }

            link.interface_a.statistics = link.statistics

            # reverse for other interface
            link.interface_b.statistics = {
                "readbytes": writebytes,
                "readpackets": writepackets,
                "writebytes": readbytes,
                "writepackets": readpackets,
            }

        self._last_sync_statistics_time = time.time()

    @check_stale
    @locked
    def sync_states(self) -> None:
        """Sync all the states of the various elements with the backend server."""
        url = self._url_for("lab_element_state")
        states: dict[str, dict[str, str]] = self._session.get(url).json()
        for node_id, node_state in states["nodes"].items():
            self._nodes[node_id]._state = node_state
        ifaces = self._interfaces.copy()
        for interface_id, interface_state in states["interfaces"].items():
            try:
                iface = ifaces.pop(interface_id)
            except KeyError:
                pass
            else:
                iface._state = interface_state
        for stale_iface in ifaces:
            ifaces[stale_iface]._stale = True
        for link_id, link_state in states["links"].items():
            self._links[link_id]._state = link_state

        self._last_sync_state_time = time.time()

    @check_stale
    def wait_until_lab_converged(
        self, max_iterations: int | None = None, wait_time: int | None = None
    ) -> None:
        """
        Wait until the lab converges.

        :param max_iterations: The maximum number of iterations to wait.
        :param wait_time: The time to wait between iterations.
        """
        max_iter = (
            self.wait_max_iterations if max_iterations is None else max_iterations
        )
        wait_time = self.wait_time if wait_time is None else wait_time
        _LOGGER.info(f"Waiting for lab {self._id} to converge.")
        for index in range(max_iter):
            converged = self.has_converged()
            if converged:
                _LOGGER.info(f"Lab {self._id} has booted.")
                return

            if index % 10 == 0:
                _LOGGER.info(
                    f"Lab has not converged, attempt {index}/{max_iter}, waiting..."
                )
            time.sleep(wait_time)

        msg = f"Lab {self.id} has not converged, maximum tries {max_iter} exceeded."
        _LOGGER.error(msg)
        # After maximum retries are exceeded and lab has not converged,
        # an error must be raised - it makes no sense to just log info
        # and let the client fail with something else if wait is explicitly
        # specified.
        raise RuntimeError(msg)

    @check_stale
    def has_converged(self) -> bool:
        """
        Check whether the lab has converged.

        :returns: True if the lab has converged, False otherwise.
        """
        url = self._url_for("check_if_converged")
        converged = self._session.get(url).json()
        return converged

    @check_stale
    def start(self, wait: bool | None = None) -> None:
        """
        Start all the nodes and links in the lab.

        :param wait: A flag indicating whether to wait for convergence.
            If left at the default value, the lab's wait property is used instead.
        """
        url = self._url_for("start")
        self._session.put(url)
        if self.need_to_wait(wait):
            self.wait_until_lab_converged()
        _LOGGER.debug(f"Started lab: {self._id}")

    @check_stale
    def stop(self, wait: bool | None = None) -> None:
        """
        Stop all the nodes and links in the lab.

        :param wait: A flag indicating whether to wait for convergence.
            If left at the default value, the lab's wait property is used instead.
        """
        url = self._url_for("stop")
        self._session.put(url)
        if self.need_to_wait(wait):
            self.wait_until_lab_converged()
        _LOGGER.debug(f"Stopped lab: {self._id}")

    @check_stale
    def state(self) -> str:
        """
        Return the state of the lab.

        :returns: The state as text.
        """
        if self._state is None or getattr(self._session, "lock", None) is None:
            # no lock == event listening not enabled
            url = self._url_for("state")
            response = self._session.get(url)
            self._state = response.json()

        _LOGGER.debug(f"lab state: {self._id} -> {self._state}")
        return self._state

    def is_active(self) -> bool:
        """
        Check if the lab is active.

        :return: True if the lab is active, False otherwise
        """
        return self.state() == "STARTED"

    @check_stale
    def details(self) -> dict[str, str | list | int]:
        """
        Retrieve the details of the lab, including its state.

        :return: A dictionary containing the detailed lab state
        """
        url = self._url_for("lab")
        response = self._session.get(url)
        _LOGGER.debug(f"lab state: {self._id} -> {response.text}")
        return response.json()

    @check_stale
    def wipe(self, wait: bool | None = None) -> None:
        """
        Wipe all the nodes and links in the lab.

        :param wait: A flag indicating whether to wait for convergence.
            If left at the default value, the lab's wait property is used instead.
        """
        url = self._url_for("wipe")
        self._session.put(url)
        if self.need_to_wait(wait):
            self.wait_until_lab_converged()
        _LOGGER.debug(f"wiped lab: {self._id}")

    def remove(self) -> None:
        """Remove the lab from the server. The lab must be stopped and wiped first."""
        url = self._url_for("lab")
        response = self._session.delete(url)
        _LOGGER.debug(f"Removed lab: {response.text}")
        self._stale = True

    @check_stale
    @locked
    def sync_events(self) -> bool:
        """
        Synchronize the events in the lab.

        :returns: True if the events have changed, False otherwise
        """
        url = self._url_for("events")
        result = self._session.get(url).json()
        changed = self.events != result
        self.events = result
        return changed

    @check_stale
    def build_configurations(self) -> None:
        """
        Build basic configurations for all nodes in the lab that do not
        already have a configuration and support configuration building.
        """
        url = self._url_for("build_configurations")
        self._session.get(url)
        # sync to get the updated configs
        self.sync_topology_if_outdated()

    @check_stale
    @locked
    def sync(
        self,
        topology_only=True,
        with_node_configurations: bool | None = None,
        exclude_configurations=False,
    ) -> None:
        """
        Synchronize the current lab, locally applying changes made to the server.

        :param topology_only: Only sync the topology without statistics and IP
            addresses.
        :param with_node_configurations: DEPRECATED: does the opposite of what
            is expected. Use exclude_configurations instead.
        :param exclude_configurations: Whether to exclude configurations
            from synchronization.
        """
        if with_node_configurations is not None:
            warnings.warn(
                "Lab.sync(): The argument 'with_node_configurations' is deprecated, "
                "as it does the opposite of what is expected. "
                "Use exclude_configurations instead.",
                DeprecationWarning,
            )
            exclude_configurations = with_node_configurations

        self._sync_topology(exclude_configurations)

        if not topology_only:
            self.sync_statistics()
            self.sync_layer3_addresses()
            self.sync_operational()

    @locked
    def _sync_topology(self, exclude_configurations=False) -> None:
        """Helper function to sync topologies from the backend server."""
        url = self._url_for("topology")
        params = {"exclude_configurations": exclude_configurations}
        try:
            result = self._session.get(url, params=params)
        except HTTPStatusError as exc:
            error_msg = exc.response.text
            try:
                # Get the error message from the API's JSON error object.
                error_msg = json.loads(error_msg)["description"]
            except (ValueError, TypeError, KeyError):
                # response.text was empty, not a JSON object, or not the expected
                # JSON schema. Use the raw result text.
                pass
            if (
                exc.response.status_code == 404
                and f"Lab not found: {self._id}" in exc.response.text
            ):
                self._stale = True
            raise LabNotFound(f"Error syncing lab: {error_msg}")

        topology = result.json()

        if self._initialized:
            self.update_lab(topology, exclude_configurations)
        else:
            self.import_lab(topology)
            self._initialized = True

        self._last_sync_topology_time = time.time()

    @locked
    def import_lab(self, topology: dict) -> None:
        """
        Import a lab from a given topology.

        :param topology: The topology to import.
        """
        self._import_lab(topology)
        self._handle_import_nodes(topology)
        self._handle_import_interfaces(topology)
        self._handle_import_links(topology)

    @locked
    def _import_lab(self, topology: dict) -> None:
        """
        Replace lab properties with the given topology.

        :param topology: The topology to import.
        :raises KeyError: If any property is missing in the topology.
        """
        lab_dict = topology.get("lab")

        if lab_dict is None:
            warnings.warn(
                "Labs created in older CML releases (schema version 0.0.5 or lower) "
                "are deprecated. Use labs with schema version 0.1.0 or higher.",
                DeprecationWarning,
            )
            self._title = topology["lab_title"]
            self._description = topology["lab_description"]
            self._notes = topology["lab_notes"]
            self._owner = topology.get("lab_owner", self.username)
        else:
            self._title = lab_dict["title"]
            self._description = lab_dict["description"]
            self._notes = lab_dict["notes"]
            self._owner = lab_dict.get("owner", self.username)

    @locked
    def _handle_import_nodes(self, topology: dict) -> None:
        """
        Handle the import of nodes from the given topology.

        :param topology: The topology to import nodes from.
        """
        for node in topology["nodes"]:
            node_id = node["id"]

            if node_id in self._nodes:
                raise ElementAlreadyExists("Node already exists")

            interfaces = node.pop("interfaces", [])
            self._import_node(node_id, node)

            if not interfaces:
                continue

            for iface in interfaces:
                iface_id = iface["id"]

                if iface_id in self._interfaces:
                    raise ElementAlreadyExists("Interface already exists")

                self._import_interface(iface_id, node_id, iface)

    @locked
    def _handle_import_interfaces(self, topology: dict) -> None:
        """
        Handle the import of interfaces from the given topology.

        :param topology: The topology to import interfaces from.
        """
        if "interfaces" in topology:
            for iface in topology["interfaces"]:
                iface_id = iface["id"]
                node_id = iface["node"]

                if iface_id in self._interfaces:
                    raise ElementAlreadyExists("Interface already exists")

                self._import_interface(iface_id, node_id, iface)

    @locked
    def _handle_import_links(self, topology: dict) -> None:
        """
        Handle the import of links from the given topology.

        :param topology: The topology to import links from.
        """
        for link in topology["links"]:
            link_id = link["id"]

            if link_id in self._links:
                raise ElementAlreadyExists("Link already exists")

            iface_a_id = link["interface_a"]
            iface_b_id = link["interface_b"]
            label = link.get("label")

            self._import_link(link_id, iface_b_id, iface_a_id, label)

    @locked
    def _import_link(
        self,
        link_id: str,
        iface_b_id: str,
        iface_a_id: str,
        label: str | None = None,
    ) -> Link:
        """
        Import a link with the given parameters.

        :param link_id: The ID of the link.
        :param iface_b_id: The ID of the second interface.
        :param iface_a_id: The ID of the first interface.
        :param label: The label of the link.
        :returns: The imported Link object.
        """
        iface_a = self._interfaces[iface_a_id]
        iface_b = self._interfaces[iface_b_id]
        return self._create_link_local(iface_a, iface_b, link_id, label)

    @locked
    def _import_interface(
        self, iface_id: str, node_id: str, iface_data: dict
    ) -> Interface:
        """
        Import an interface with the given parameters.

        :param iface_id: The ID of the interface.
        :param node_id: The ID of the node the interface belongs to.
        :param iface_data: The data of the interface.
        :returns: The imported Interface object.
        """
        if "data" in iface_data:
            iface_data = iface_data["data"]

        label = iface_data["label"]
        slot = iface_data.get("slot")
        iface_type = iface_data["type"]
        node = self._nodes[node_id]
        return self._create_interface_local(iface_id, label, node, slot, iface_type)

    @locked
    def _import_node(self, node_id: str, node_data: dict) -> Node:
        """
        Import a node with the given parameters.

        :param node_id: The ID of the node.
        :param node_data: The data of the node.
        :returns: The imported Node object.
        """
        if "data" in node_data:
            node_data = node_data["data"]

        node_data.pop("id", None)
        state = node_data.pop("state", None)
        node_data.pop("lab_id", None)
        node_data.pop("boot_progress", None)

        for key in ("image_definition", "configuration"):
            if key not in node_data:
                node_data[key] = None

        node = self._create_node_local(node_id, **node_data)
        node._state = state
        return node

    @locked
    def update_lab(self, topology: dict, exclude_configurations: bool) -> None:
        """
        Update the lab with the given topology.

        :param topology: The updated topology.
        :param exclude_configurations: Whether to exclude configurations from updating.
        """
        self._import_lab(topology)

        # add in order: node -> interface -> link
        # remove in reverse, eg link -> interface -> node
        existing_node_keys = set(self._nodes)
        existing_link_keys = set(self._links)
        existing_interface_keys = set(self._interfaces)

        update_node_keys = set(node["id"] for node in topology["nodes"])
        update_link_keys = set(links["id"] for links in topology["links"])

        if "interfaces" in topology:
            update_interface_keys = set(iface["id"] for iface in topology["interfaces"])
        else:
            update_interface_keys = set(
                interface["id"]
                for node in topology["nodes"]
                for interface in node["interfaces"]
            )

        # removed elements
        removed_nodes = existing_node_keys - update_node_keys
        removed_links = existing_link_keys - update_link_keys
        removed_interfaces = existing_interface_keys - update_interface_keys

        self._remove_elements(removed_nodes, removed_links, removed_interfaces)

        # new elements
        new_nodes = update_node_keys - existing_node_keys
        new_links = update_link_keys - existing_link_keys
        new_interfaces = update_interface_keys - existing_interface_keys

        self._add_elements(topology, new_nodes, new_links, new_interfaces)

        # kept elements
        kept_nodes = update_node_keys.intersection(existing_node_keys)
        # kept_links = update_link_keys.intersection(existing_link_keys)
        # kept_interfaces = update_interface_keys.intersection(existing_interface_keys)

        self._update_elements(topology, kept_nodes, exclude_configurations)

    @locked
    def _remove_elements(
        self,
        removed_nodes: Iterable[str],
        removed_links: Iterable[str],
        removed_interfaces: Iterable[str],
    ) -> None:
        """
        Remove elements from the lab.

        :param removed_nodes: Iterable of node IDs to be removed.
        :param removed_links: Iterable of link IDs to be removed.
        :param removed_interfaces: Iterable of interface IDs to be removed.
        """
        for link_id in removed_links:
            link = self._links.pop(link_id)
            _LOGGER.info(f"Removed link {link}")
            link._stale = True

        for interface_id in removed_interfaces:
            interface = self._interfaces.pop(interface_id)
            _LOGGER.info(f"Removed interface {interface}")
            interface._stale = True

        for node_id in removed_nodes:
            node = self._nodes.pop(node_id)
            _LOGGER.info(f"Removed node {node}")
            node._stale = True

    @locked
    def _add_elements(
        self,
        topology: dict,
        new_nodes: Iterable[str],
        new_links: Iterable[str],
        new_interfaces: Iterable[str],
    ) -> None:
        """
        Add elements to the lab.

        :param topology: Dictionary containing the lab topology.
        :param new_nodes: Iterable of node IDs to be added.
        :param new_links: Iterable of link IDs to be added.
        :param new_interfaces: Iterable of interface IDs to be added.
        """
        for node in topology["nodes"]:
            node_id = node["id"]
            interfaces = node.pop("interfaces", [])
            if node_id in new_nodes:
                node = self._import_node(node_id, node)
                _LOGGER.info(f"Added node {node}")

            if not interfaces:
                continue

            for interface in interfaces:
                interface_id = interface["id"]
                if interface_id in new_interfaces:
                    interface = self._import_interface(interface_id, node_id, interface)
                    _LOGGER.info(f"Added interface {interface}")

        if "interfaces" in topology:
            for iface in topology["interfaces"]:
                iface_id = iface["id"]
                if iface_id in new_interfaces:
                    node_id = iface["node"]
                    self._import_interface(iface_id, node_id, iface)

        for link_id in new_links:
            link_data = self._find_link_in_topology(link_id, topology)
            iface_a_id = link_data["interface_a"]
            iface_b_id = link_data["interface_b"]
            label = link_data.get("label")
            link = self._import_link(link_id, iface_b_id, iface_a_id, label)
            _LOGGER.info(f"Added link {link}")

    @locked
    def _update_elements(
        self, topology: dict, kept_nodes: Iterable[str], exclude_configurations: bool
    ) -> None:
        """
        Update elements in the lab.

         :param topology: Dictionary containing the lab topology.
         :param kept_nodes: Iterable of node IDs to be updated.
         :param exclude_configurations: Boolean indicating whether to exclude
            configurations during update.
        """
        for node_id in kept_nodes:
            node = self._find_node_in_topology(node_id, topology)
            lab_node = self._nodes[node_id]
            lab_node.update(node, exclude_configurations, push_to_server=False)

        # For now, can't update interface data server-side, this will change with tags
        # for interface_id in kept_interfaces:
        #     interface_data = self._find_interface_in_topology(interface_id, topology)

        # For now, can't update link data server-side, this will change with tags
        # for link_id in kept_links:
        #     link_data = self._find_link_in_topology(link_id, topology)

    @locked
    def update_lab_properties(self, properties: dict[str, Any]):
        """
        Update lab properties. Will not modify unspecified properties.
        Is not compatible with schema version 0.0.5.

        :param properties: Dictionary containing the updated lab properties.
        """
        self._title = properties.get("title", self._title)
        self._description = properties.get("description", self._description)
        self._notes = properties.get("notes", self._notes)
        self._owner = properties.get("owner", self._owner)

    @staticmethod
    def _find_link_in_topology(link_id: str, topology: dict) -> dict:
        """
        Find a link in the given topology.

        :param link_id: The ID of the link to find.
        :param topology: Dictionary containing the lab topology.
        :returns: The link with the specified ID.
        :raises LinkNotFound: If the link cannot be found in the topology.
        """

        for link in topology["links"]:
            if link["id"] == link_id:
                return link
        # if it cannot be found, it is an internal structure error
        raise LinkNotFound

    # @staticmethod
    # def _find_interface_in_topology(interface_id: str, topology: dict) -> dict:
    #     for node in topology["nodes"]:
    #         for interface in node["interfaces"]:
    #             if interface["id"] == interface_id:
    #                 return interface
    #     # if it cannot be found, it is an internal structure error
    #     raise InterfaceNotFound

    @staticmethod
    def _find_node_in_topology(node_id: str, topology: dict) -> dict:
        """
        Find a node in the given topology.

        :param node_id: The ID of the node to find.
        :param topology: Dictionary containing the lab topology.
        :returns: The node with the specified ID.
        :raises NodeNotFound: If the node cannot be found in the topology.
        """

        for node in topology["nodes"]:
            if node["id"] == node_id:
                return node
        # if it cannot be found, it is an internal structure error
        raise NodeNotFound

    @check_stale
    def get_pyats_testbed(self, hostname: str | None = None) -> str:
        """
        Return lab's pyATS YAML testbed. Example usage::

            from pyats.topology import loader

            lab = client_library.join_existing_lab("lab_1")
            testbed_yaml = lab.get_pyats_testbed()

            testbed = loader.load(io.StringIO(testbed_yaml))

            # wait for lab to be ready
            lab.wait_until_lab_converged()

            aetest.main(testbed=testbed)

        :param hostname: Force hostname/ip and port for console terminal server.
        :returns: The pyATS testbed for the lab in YAML format.
        """
        url = self._url_for("pyats_testbed")
        params = {}
        if hostname is not None:
            params["hostname"] = hostname
        result = self._session.get(url, params=params)
        return result.text

    @check_stale
    def sync_pyats(self) -> None:
        """Sync the pyATS testbed."""
        self.pyats.sync_testbed(self.username, self.password)

    def cleanup_pyats_connections(self) -> None:
        """Close and clean up connection that pyATS might still hold."""
        self.pyats.cleanup()

    @check_stale
    @locked
    def sync_layer3_addresses(self) -> None:
        """Sync all layer 3 IP addresses from the backend server."""
        url = self._url_for("layer3_addresses")
        result: dict[str, dict] = self._session.get(url).json()
        for node_id, node_data in result.items():
            node = self.get_node_by_id(node_id)
            mapping = node_data.get("interfaces", {})
            node.map_l3_addresses_to_interfaces(mapping)
        self._last_sync_l3_address_time = time.time()

    @check_stale
    def download(self) -> str:
        """
        Download the lab from the server in YAML format.

        :returns: The lab in YAML format.
        """
        url = self._url_for("download")
        return self._session.get(url).text

    @property
    def groups(self) -> list[dict[str, str]]:
        """Return the groups this lab is associated with."""
        url = self._url_for("groups")
        return self._session.get(url).json()

    @check_stale
    def update_lab_groups(
        self, group_list: list[dict[str, str]]
    ) -> list[dict[str, str]]:
        """
        Modify lab/group association.

        :param group_list: List of objects consisting of group ID and permission.
        :returns: Updated objects consisting of group ID and permission.
        """
        url = self._url_for("groups")
        return self._session.put(url, json=group_list).json()

    @property
    def connector_mappings(self) -> list[dict[str, Any]]:
        """
        Retrieve lab's external connector mappings.

        Returns a list of mappings; each mapping has a key, which is used
        as the configuration of external connector nodes, and a device name,
        used to uniquely identify the controller host's bridge to use.
        If unset, the mapping is invalid and nodes using it cannot start.
        """
        url = self._url_for("connector_mappings")
        return self._session.get(url).json()

    def update_connector_mappings(
        self, updates: list[dict[str, str]]
    ) -> list[dict[str, str]]:
        """
        Update lab's external connector mappings.

        Accepts a list of mappings, each with a key to add or modify,
        and the associated device name (bridge) of the controller host.
        If no running external connector node uses this key, the device_name
        value may be None to disassociate the bridge from the key; if no node
        uses this key in its configuration, the mapping entry is removed.

        :returns: All connector mappings after updates were applied.
        """
        url = self._url_for("connector_mappings")
        return self._session.patch(url, json=updates).json()

    @check_stale
    @locked
    def sync_operational(self) -> None:
        """Sync the operational status of the lab."""
        url = self._url_for("resource_pools")
        response = self._session.get(url).json()
        res_pools = self._resource_pool_manager.get_resource_pools_by_ids(response)
        self._resource_pools = list(res_pools.values())
        self._last_sync_operational_time = time.time()

        for node in self._nodes.values():
            node.sync_operational()
