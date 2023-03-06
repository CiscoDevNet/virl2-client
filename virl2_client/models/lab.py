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
from typing import TYPE_CHECKING, Any, Iterable, Optional

from httpx import HTTPStatusError

from ..exceptions import (
    ElementAlreadyExists,
    InterfaceNotFound,
    LabNotFound,
    LinkNotFound,
    NodeNotFound,
    VirlException,
)
from .cl_pyats import ClPyats
from .interface import Interface
from .link import Link
from .node import Node

if TYPE_CHECKING:
    import httpx

    from .resource_pools import ResourcePool, ResourcePoolManagement


_LOGGER = logging.getLogger(__name__)


class Lab:
    def __init__(
        self,
        title: Optional[str],
        lab_id: str,
        session: httpx.Client,
        username: str,
        password: str,
        auto_sync=True,
        auto_sync_interval=1.0,
        wait=True,
        wait_max_iterations=500,
        wait_time=5,
        hostname: Optional[str] = None,
        resource_pool_manager: Optional[ResourcePoolManagement] = None,
    ) -> None:
        """
        A VIRL2 lab network topology. Contains nodes, links and interfaces.

        :param title: Name / title of the lab
        :param lab_id: A lab ID
        :param session: httpx Client session
        :param username: Username of the user to authenticate
        :param password: Password of the user to authenticate
        :param auto_sync: Should local changes sync to the server automatically
        :param auto_sync_interval: Interval to auto sync in seconds
        :param wait: Wait for convergence on backend
        :param wait_max_iterations: Maximum number of tries or calls for convergence
        :param wait_time: Time to sleep between calls for convergence on backend
        :param hostname: Force hostname/ip and port for pyATS console terminal server
        :param resource_pool_manager: a ResourcePoolManagement object
            shared with parent ClientLibrary
        """

        self.username = username
        self.password = password

        self._title = title
        self._description = ""
        self._notes = ""
        self._lab_id = lab_id
        self._session = session
        self._owner = username
        self._nodes: dict[str, Node] = {}
        """
        Dictionary containing all nodes in the lab.
        It maps node identifier to `models.Node`
        """
        self._links: dict[str, Link] = {}
        """
        Dictionary containing all links in the lab.
        It maps link identifier to `models.Link`
        """
        self._interfaces: dict[str, Interface] = {}
        """
        Dictionary containing all interfaces in the lab.
        It maps interface identifier to `models.Interface`
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

    def __len__(self):
        return len(self._nodes)

    def __str__(self):
        return "Lab: {}".format(self._title)

    def __repr__(self):
        return "{}({!r}, {!r}, {!r}, {!r}, {!r}, {!r})".format(
            self.__class__.__name__,
            self._title,
            self._lab_id,
            self._session.base_url.path,
            self.auto_sync,
            self.auto_sync_interval,
            self.wait_for_convergence,
        )

    def need_to_wait(self, local_wait: Optional[bool]) -> bool:
        if local_wait is None:
            return self.wait_for_convergence
        if not isinstance(local_wait, bool):
            raise ValueError
        return local_wait

    def sync_statistics_if_outdated(self) -> None:
        timestamp = time.time()
        if (
            self.auto_sync
            and timestamp - self._last_sync_statistics_time > self.auto_sync_interval
        ):
            self.sync_statistics()

    def sync_states_if_outdated(self) -> None:
        timestamp = time.time()
        if (
            self.auto_sync
            and timestamp - self._last_sync_state_time > self.auto_sync_interval
        ):
            self.sync_states()

    def sync_l3_addresses_if_outdated(self) -> None:
        timestamp = time.time()
        if (
            self.auto_sync
            and timestamp - self._last_sync_l3_address_time > self.auto_sync_interval
        ):
            self.sync_layer3_addresses()

    def sync_topology_if_outdated(self) -> None:
        timestamp = time.time()
        if (
            self.auto_sync
            and timestamp - self._last_sync_topology_time > self.auto_sync_interval
        ):
            self._sync_topology(exclude_configurations=True)

    def sync_operational_if_outdated(self) -> None:
        timestamp = time.time()
        if (
            self.auto_sync
            and timestamp - self._last_sync_operational_time > self.auto_sync_interval
        ):
            self.sync_operational()

    @property
    def id(self) -> str:
        """
        Returns the ID of the lab (a 6 digit hex string).

        :returns: The Lab ID
        """

        return self._lab_id

    @property
    def title(self) -> Optional[str]:
        """
        Returns the title of the lab.

        :returns: The lab name
        """
        self.sync_topology_if_outdated()
        return self._title

    @title.setter
    def title(self, value: str) -> None:
        """
        Set the title of the lab.

        :param value: The new lab title
        """
        url = self.lab_base_url
        self._session.patch(url, json={"title": value})
        self._title = value

    @property
    def notes(self) -> str:
        """
        Returns the notes of the lab.

        :returns: The lab name
        """
        self.sync_topology_if_outdated()
        return self._notes

    @notes.setter
    def notes(self, value: str) -> None:
        """
        Set the notes of the lab.

        :param value: The new lab notes
        """
        url = self.lab_base_url
        self._session.patch(url, json={"notes": value})
        self._notes = value

    @property
    def description(self) -> str:
        """
        Returns the description of the lab.

        :returns: The lab name
        """
        self.sync_topology_if_outdated()
        return self._description

    @description.setter
    def description(self, value: str) -> None:
        """
        Set the description of the lab.

        :param value: The new lab description
        """
        url = self.lab_base_url
        self._session.patch(url, json={"description": value})
        self._description = value

    @property
    def session(self) -> httpx.Client:
        """
        Returns the API client session object.

        :returns: The session object
        """
        return self._session

    @property
    def owner(self) -> str:
        """
        Returns the owner of the lab.

        :returns: A username
        """
        self.sync_topology_if_outdated()
        return self._owner

    @property
    def resource_pools(self) -> list[ResourcePool]:
        self.sync_operational_if_outdated()
        return self._resource_pools

    def nodes(self) -> list[Node]:
        """
        Returns the list of nodes in the lab.

        :returns: A list of Node objects
        """
        self.sync_topology_if_outdated()
        return list(self._nodes.values())

    def links(self) -> list[Link]:
        """
        Returns the list of links in the lab.

        :returns: A list of Link objects
        """
        self.sync_topology_if_outdated()
        return list(self._links.values())

    def interfaces(self) -> list[Interface]:
        """
        Returns the list of interfaces in the lab.

        :returns: A list of Interface objects
        """
        self.sync_topology_if_outdated()
        return list(self._interfaces.values())

    @property
    def lab_base_url(self) -> str:
        return "labs/{}".format(self._lab_id)

    @property
    def statistics(self) -> dict:
        """
        Returns some statistics about the lab.

        :returns: A dictionary with stats of the lab
        """
        return {
            "nodes": len(self._nodes),
            "links": len(self._links),
            "interfaces": len(self._interfaces),
        }

    def get_node_by_id(self, node_id: str) -> Node:
        """
        Returns the node identified by the ID.

        :param node_id: ID of the node to be returned
        :returns: A Node object
        :raises NodeNotFound: If node not found
        """
        self.sync_topology_if_outdated()
        try:
            return self._nodes[node_id]
        except KeyError:
            raise NodeNotFound(node_id)

    def get_node_by_label(self, label: str) -> Node:
        """
        Returns the node identified by the label.

        :param label: label of the node to be returned
        :returns: A Node object
        :raises NodeNotFound: If node not found
        """
        self.sync_topology_if_outdated()
        for node in self._nodes.values():
            if node.label == label:
                return node
        raise NodeNotFound(label)

    def get_interface_by_id(self, interface_id: str) -> Interface:
        """
        Returns the interface identified by the ID.

        :param interface_id: ID of the interface to be returned
        :returns: An Interface object
        :raises InterfaceNotFound: If interface not found
        """
        self.sync_topology_if_outdated()
        try:
            return self._interfaces[interface_id]
        except KeyError:
            raise InterfaceNotFound(interface_id)

    def get_link_by_id(self, link_id: str) -> Link:
        """
        Returns the link identified by the ID.

        :param link_id: ID of the interface to be returned
        :returns: A Link object
        :raises LinkNotFound: If interface not found
        """
        self.sync_topology_if_outdated()
        try:
            return self._links[link_id]
        except KeyError:
            raise LinkNotFound(link_id)

    @staticmethod
    def get_link_by_nodes(node1: Node, node2: Node) -> Link:
        """
        DEPRECATED

        Returns ONE of the links identified by two node objects.

        Deprecated. Use `Node.get_link_to` to get one link
        or `Node.get_links_to` to get all links.

        :param node1: the first node
        :param node2: the second node
        :returns: one of links between the nodes
        :raises LinkNotFound: If no such link exists
        """
        warnings.warn(
            "Deprecated, use Node.get_link_to or Node.get_links_to instead.",
            DeprecationWarning,
        )
        if not (links := node1.get_links_to(node2)):
            raise LinkNotFound
        return links[0]

    @staticmethod
    def get_link_by_interfaces(iface1: Interface, iface2: Interface) -> Optional[Link]:
        """
        DEPRECATED

        Returns the link identified by two interface objects.

        Deprecated. Use `Interface.get_link_to` to get link.

        :param iface1: the first interface
        :param iface2: the second interface
        :returns: the link between the interfaces
        :raises LinkNotFound: If no such link exists
        """
        warnings.warn(
            "Deprecated, use Interface.get_link_to instead.", DeprecationWarning
        )
        if (link := iface1.link) is not None and iface2 in link.interfaces:
            return link
        raise LinkNotFound

    def find_nodes_by_tag(self, tag: str) -> list[Node]:
        """
        Returns the nodes identified by the given tag.

        :param tag: tag of the nodes to be returned
        :returns: a list of nodes
        """
        self.sync_topology_if_outdated()
        return [node for node in self.nodes() if tag in node.tags()]

    def create_node(
        self,
        label: str,
        node_definition: str,
        x: int = 0,
        y: int = 0,
        wait: Optional[bool] = None,
        populate_interfaces: bool = False,
        **kwargs,
    ) -> Node:
        """
        Creates a node in the lab with the given parameters.

        :param label: Label
        :param node_definition: Node definition to use
        :param x: x coordinate
        :param y: y coordinate
        :param wait: Wait for convergence (if left at default,
            the lab wait property takes precedence)
        :param populate_interfaces: automatically create pre-defined number
            of interfaces on node creation
        :returns: a Node object
        """
        # TODO: warn locally if label in use already?
        url = self.lab_base_url + "/nodes"
        if populate_interfaces:
            url += "?populate_interfaces=true"
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
        node = self.add_node_local(node_id, **kwargs)
        return node

    def add_node_local(
        self,
        node_id: str,
        label: str,
        node_definition: str,
        image_definition: Optional[str],
        configuration: Optional[str],
        x: int,
        y: int,
        ram: Optional[int] = None,
        cpus: Optional[int] = None,
        cpu_limit: Optional[int] = None,
        data_volume: Optional[int] = None,
        boot_disk_size: Optional[int] = None,
        hide_links: bool = False,
        tags: Optional[list] = None,
        compute_id: Optional[str] = None,
        resource_pool: Optional[ResourcePool] = None,
    ) -> Node:
        """Helper function to add a node to the client library."""
        if tags is None:
            # TODO: see if can deprecate now tags set automatically
            # on server at creation
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
        )
        if compute_id is not None:
            node._compute_id = compute_id
        self._nodes[node.id] = node
        return node

    def remove_node(self, node: Node, wait: Optional[bool] = None) -> None:
        """
        Removes a node from the lab.

        :param node: the node
        :param wait: Wait for convergence (if left at default,
            the lab wait property takes precedence)
        """
        node.remove_on_server()
        for iface in node.interfaces():
            if iface.link is not None:
                try:
                    del self._links[iface.link.id]
                except KeyError:
                    # element may already have been deleted on server,
                    # and removed locally due to auto-sync
                    pass
            try:
                del self._interfaces[iface.id]
            except KeyError:
                # element may already have been deleted on server,
                # and removed locally due to auto-sync
                pass
        try:
            del self._nodes[node.id]
        except KeyError:
            # element may already have been deleted on server,
            # and removed locally due to auto-sync
            pass

        if self.need_to_wait(wait):
            self.wait_until_lab_converged()
        _LOGGER.debug("%s node removed from lab %s", node.id, self._lab_id)

    def remove_nodes(self, wait: Optional[bool] = None) -> None:
        """
        Remove all nodes from the lab.

        :param wait: Wait for convergence (if left at default,
            the lab wait property takes precedence)
        """
        # TODO: see if this is used - in testing?
        for node in list(self._nodes.values()):
            self.remove_node(node, wait=False)

        if self.need_to_wait(wait):
            self.wait_until_lab_converged()
        _LOGGER.debug("all nodes removed from lab %s", self._lab_id)

    def remove_link(self, link: Link, wait: Optional[bool] = None) -> None:
        """
        Removes a link from the lab.

        :param link: the link
        :param wait: Wait for convergence (if left at default,
            the lab wait property takes precedence)
        """
        link.remove_on_server()
        try:
            del self._links[link.id]
        except KeyError:
            # element may already have been deleted on server,
            # and removed locally due to auto-sync
            pass

        if self.need_to_wait(wait):
            self.wait_until_lab_converged()
        _LOGGER.debug("link %s removed from lab %s", link.id, self._lab_id)

    def remove_interface(self, iface: Interface, wait: Optional[bool] = None) -> None:
        """
        Removes an interface from the lab.

        :param iface: the interface
        :param wait: Wait for convergence (if left at default,
            the lab wait property takes precedence)
        """
        iface.remove_on_server()
        if iface.link is not None:
            try:
                del self._links[iface.link.id]
            except KeyError:
                # element may already have been deleted on server, and removed
                # locally due to auto-sync
                pass
        try:
            del self._interfaces[iface.id]
        except KeyError:
            # element may already have been deleted on server, and removed
            # locally due to auto-sync
            pass

        if self.need_to_wait(wait):
            self.wait_until_lab_converged()
        _LOGGER.debug("interface %s removed from lab %s", iface.id, self._lab_id)

    def create_link(
        self, i1: Interface, i2: Interface, wait: Optional[bool] = None
    ) -> Link:
        """
        Creates a link between two interfaces

        :param i1: the first interface object
        :param i2: the second interface object
        :param wait: Wait for convergence (if left at default,
            the lab wait property takes precedence)
        :returns: the created link
        """
        url = self.lab_base_url + "/links"
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

        link = self.create_link_local(i1, i2, link_id, label)
        return link

    def connect_two_nodes(self, node1: Node, node2: Node) -> Link:
        """
        Convenience method to connect two nodes within a lab.

        :param node1: the first node object
        :param node2: the second node object
        :returns: the created link
        """
        iface1 = node1.next_available_interface() or node1.create_interface()
        iface2 = node2.next_available_interface() or node2.create_interface()
        return self.create_link(iface1, iface2)

    def create_link_local(
        self, i1: Interface, i2: Interface, link_id: str, label: Optional[str] = None
    ) -> Link:
        """Helper function to create a link in the client library."""
        link = Link(self, link_id, i1, i2, label)
        self._links[link_id] = link
        return link

    def create_interface(
        self, node: Node, slot: Optional[int] = None, wait: Optional[bool] = None
    ) -> Interface:
        """
        Create an interface in the next available slot, or, if a slot is specified,
        in all available slots up to and including the specified slot.

        :param node: The node on which the interface is created
        :param slot: (optional)
        :param wait: Wait for convergence (if left at default,
            the lab wait property takes precedence)
        :returns: The newly created interface
        """
        url = self.lab_base_url + "/interfaces"
        payload: dict[str, str | int] = {"node": node.id}
        if slot is not None:
            payload["slot"] = slot
        result = self._session.post(url, json=payload).json()
        if isinstance(result, dict):
            # in case API returned just one interface, pack it into the list:
            result = [result]

        if self.need_to_wait(wait):
            self.wait_until_lab_converged()

        # TODO: need to import the topology then
        desired_interface: Optional[Interface] = None
        for iface in result:
            lab_interface = self.create_interface_local(
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

    def create_interface_local(
        self,
        iface_id: str,
        label: str,
        node: Node,
        slot: Optional[int],
        iface_type: str = "physical",
    ) -> Interface:
        """Helper function to create an interface in the client library."""
        if iface_id not in self._interfaces:
            iface = Interface(iface_id, node, label, slot, iface_type)
            self._interfaces[iface_id] = iface
        else:  # update the interface if it already exists:
            self._interfaces[iface_id].node = node
            self._interfaces[iface_id].label = label
            self._interfaces[iface_id].slot = slot
            self._interfaces[iface_id].type = iface_type
        return self._interfaces[iface_id]

    @staticmethod
    def _get_element_from_data(data: dict, element: str) -> int:
        try:
            return int(data[element])
        except (TypeError, KeyError):
            return 0

    def sync_statistics(self) -> None:
        """Retrieve the simulation statistic data from the back end server."""
        url = self.lab_base_url + "/simulation_stats"
        states: dict[str, dict[str, dict]] = self._session.get(url).json()
        node_statistics = states.get("nodes", {})
        link_statistics = states.get("links", {})
        for node_id, node_data in node_statistics.items():
            # TODO: standardise so if shutdown, then these are set to 0 on
            # server side
            disk_read = self._get_element_from_data(node_data, "block0_rd_bytes")
            disk_write = self._get_element_from_data(node_data, "block0_wr_bytes")

            self._nodes[node_id].statistics = {
                "cpu_usage": float(node_data.get("cpu_usage", 0)),
                "disk_read": disk_read,
                "disk_write": disk_write,
            }

        for link_id, link_data in link_statistics.items():
            # TODO: standardise so if shutdown, then these are set to 0 on
            # server side
            readbytes = self._get_element_from_data(link_data, "readbytes")
            readpackets = self._get_element_from_data(link_data, "readpackets")
            writebytes = self._get_element_from_data(link_data, "writebytes")
            writepackets = self._get_element_from_data(link_data, "writepackets")

            link = self._links[link_id]
            link.statistics = {
                "readbytes": readbytes,
                "readpackets": readpackets,
                "writebytes": writebytes,
                "writepackets": writepackets,
            }

            iface_a = link.interface_a
            iface_a.statistics = {
                "readbytes": readbytes,
                "readpackets": readpackets,
                "writebytes": writebytes,
                "writepackets": writepackets,
            }
            # reverse for other interface
            iface_b = link.interface_b
            iface_b.statistics = {
                "readbytes": writebytes,
                "readpackets": writepackets,
                "writebytes": readbytes,
                "writepackets": readpackets,
            }

        self._last_sync_statistics_time = time.time()

    def sync_states(self) -> None:
        """
        Sync all the states of the various elements with the back end server.
        """
        url = self.lab_base_url + "/lab_element_state"
        states: dict[str, dict[str, str]] = self._session.get(url).json()
        for node_id, node_state in states["nodes"].items():
            self._nodes[node_id].state = node_state

        for interface_id, interface_state in states["interfaces"].items():
            try:
                iface = self._interfaces[interface_id]
            except KeyError:
                # TODO: handle loopbacks created server-side
                # check how the UI handles these created today
                # - extra call after node created?
                pass
            else:
                iface._state = interface_state

        for link_id, link_state in states["links"].items():
            self._links[link_id]._state = link_state

        self._last_sync_state_time = time.time()

    def wait_until_lab_converged(
        self, max_iterations: Optional[int] = None, wait_time: Optional[int] = None
    ) -> None:
        """Wait until lab converges."""
        max_iter = (
            self.wait_max_iterations if max_iterations is None else max_iterations
        )
        wait_time = self.wait_time if wait_time is None else wait_time
        _LOGGER.info("Waiting for lab %s to converge", self._lab_id)
        for index in range(max_iter):
            converged = self.has_converged()
            if converged:
                _LOGGER.info("Lab %s has booted", self._lab_id)
                return

            if index % 10 == 0:
                _LOGGER.info(
                    "Lab has not converged, attempt %s/%s, waiting...",
                    index,
                    max_iter,
                )
            time.sleep(wait_time)

        msg = "Lab %s has not converged, maximum tries %s exceeded" % (
            self.id,
            max_iter,
        )
        _LOGGER.error(msg)
        # after maximum retries are exceeded and lab has not converged
        # error must be raised - it makes no sense to just log info
        # and let client fail with something else if wait is explicitly
        # specified
        raise RuntimeError(msg)

    def has_converged(self) -> bool:
        url = self.lab_base_url + "/check_if_converged"
        converged = self._session.get(url).json()
        return converged

    def start(self, wait: Optional[bool] = None) -> None:
        """
        Start all the nodes and links in the lab.

        :param wait: Wait for convergence (if left at default,
            the lab wait property takes precedence)
        :type wait: bool
        """
        url = self.lab_base_url + "/start"
        self._session.put(url)
        if self.need_to_wait(wait):
            self.wait_until_lab_converged()
        _LOGGER.debug("started lab: %s", self._lab_id)

    def state(self) -> str:
        """
        Returns the state of the lab.

        :returns: The state as text
        """
        url = self.lab_base_url + "/state"
        response = self._session.get(url)
        _LOGGER.debug("lab state: %s -> %s", self._lab_id, response.text)
        return response.json()

    def is_active(self) -> bool:
        """
        Returns whether the lab is started.

        :returns: Whether the lab is started
        """
        return self.state() == "STARTED"

    def details(self) -> dict[str, str | list | int]:
        """
        Returns the lab details (including state) of the lab.

        :returns: The detailed lab state
        """
        url = self.lab_base_url
        response = self._session.get(url)
        _LOGGER.debug("lab state: %s -> %s", self._lab_id, response.text)
        return response.json()

    def stop(self, wait: Optional[bool] = None) -> None:
        """
        Stops all the nodes and links in the lab.

        :param wait: Wait for convergence (if left at default,
            the lab wait property takes precedence)
        """
        url = self.lab_base_url + "/stop"
        self._session.put(url)
        if self.need_to_wait(wait):
            self.wait_until_lab_converged()
        _LOGGER.debug("stopped lab: %s", self._lab_id)

    def wipe(self, wait: Optional[bool] = None) -> None:
        """
        Wipe all the nodes and links in the lab.

        :param wait: Wait for convergence (if left at default,
            the lab wait property takes precedence)
        """
        url = self.lab_base_url + "/wipe"
        self._session.put(url)
        if self.need_to_wait(wait):
            self.wait_until_lab_converged()
        _LOGGER.debug("wiped lab: %s", self._lab_id)

    def remove(self) -> None:
        """
        Removes the lab from the server. The lab has to
        be stopped and wiped for this to work.

        Use carefully, it removes current lab::

            lab.remove()

        """
        # TODO: mark as disconnected
        url = self.lab_base_url
        response = self._session.delete(url)
        _LOGGER.debug("removed lab: %s", response.text)

    def sync_events(self) -> None:
        # TODO: return a boolean if events have changed since last run
        url = self.lab_base_url + "/events"
        result = self._session.get(url).json()
        self.events = result

    def build_configurations(self) -> None:
        """
        Build basic configurations for all nodes in the lab which
        do not already have a configuration and also do support
        configuration building.
        """
        url = "build_configurations?lab_id=" + self._lab_id
        self._session.get(url)
        # sync to get the updated configs
        self.sync_topology_if_outdated()

    def sync(
        self,
        topology_only=True,
        with_node_configurations: Optional[bool] = None,
        exclude_configurations=False,
    ) -> None:
        """
        Synchronize current lab applying the changes that
        were done in UI or in another ClientLibrary session::

            lab.sync()

        :param topology_only: do not sync statistics and IP addresses
        :param with_node_configurations: DEPRECATED, does the opposite of
            what is expected: disables syncing node configuration when True
        :param exclude_configurations: disable syncing node configuration
        """

        if with_node_configurations is not None:
            warnings.warn(
                'The argument "with_node_configurations" is deprecated, as it does '
                "the opposite of what is expected. Use exclude_configurations instead.",
                DeprecationWarning,
            )
            exclude_configurations = with_node_configurations

        self._sync_topology(exclude_configurations)

        if not topology_only:
            self.sync_statistics()
            self.sync_layer3_addresses()
            self.sync_operational()

    def _sync_topology(self, exclude_configurations=False) -> None:
        """Helper function to sync topologies from the backend server."""
        # TODO: check what happens if call twice
        url = self.lab_base_url + "/topology"
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
            raise LabNotFound("Error syncing lab: {}".format(error_msg))
            # TODO: get the error message from response/headers also?
        topology = result.json()
        if self._initialized:
            self.update_lab(topology, exclude_configurations)
        else:
            self.import_lab(topology)
            self._initialized = True
        self._last_sync_topology_time = time.time()

    def import_lab(self, topology: dict) -> None:
        self._import_lab(topology)

        self._handle_import_nodes(topology)
        self._handle_import_interfaces(topology)
        self._handle_import_links(topology)

    def _import_lab(self, topology: dict[str, Any]) -> None:
        """Replaces lab properties. Will raise KeyError if any property is missing."""
        lab_dict = topology.get("lab")
        if lab_dict is None:
            warnings.warn(
                "Labs created in older CML releases (schema version 0.0.5 or lower) "
                "are deprecated. Use labs with schema version 0.1.0 or higher instead.",
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

    def _handle_import_nodes(self, topology: dict) -> None:
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

    def _handle_import_interfaces(self, topology: dict) -> None:
        if "interfaces" in topology:
            for iface in topology["interfaces"]:
                iface_id = iface["id"]
                node_id = iface["node"]
                if iface_id in self._interfaces:
                    raise ElementAlreadyExists("Interface already exists")
                self._import_interface(iface_id, node_id, iface)

    def _handle_import_links(self, topology: dict) -> None:
        for link in topology["links"]:
            link_id = link["id"]
            if link_id in self._links:
                raise ElementAlreadyExists("Link already exists")
            iface_a_id = link["interface_a"]
            iface_b_id = link["interface_b"]
            label = link.get("label")
            self._import_link(link_id, iface_b_id, iface_a_id, label)

    def _import_link(
        self,
        link_id: str,
        iface_b_id: str,
        iface_a_id: str,
        label: Optional[str] = None,
    ) -> Link:
        iface_a = self._interfaces[iface_a_id]
        iface_b = self._interfaces[iface_b_id]
        return self.create_link_local(iface_a, iface_b, link_id, label)

    def _import_interface(
        self, iface_id: str, node_id: str, iface_data: dict
    ) -> Interface:
        if "data" in iface_data:
            iface_data = iface_data["data"]
        label = iface_data["label"]
        slot = iface_data.get("slot")
        iface_type = iface_data["type"]
        node = self._nodes[node_id]
        return self.create_interface_local(iface_id, label, node, slot, iface_type)

    def _import_node(self, node_id: str, node_data: dict) -> Node:
        if "data" in node_data:
            node_data = node_data["data"]
        node_data.pop("id", None)
        node_data.pop("state", None)
        for key in ("image_definition", "configuration"):
            if key not in node_data:
                node_data[key] = None
        return self.add_node_local(node_id, **node_data)

    def update_lab(self, topology: dict, exclude_configurations: bool) -> None:
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

    def _remove_elements(
        self,
        removed_nodes: Iterable[str],
        removed_links: Iterable[str],
        removed_interfaces: Iterable[str],
    ) -> None:
        for link_id in removed_links:
            link = self._links[link_id]
            _LOGGER.info("Removed link %s", link)
            del self._links[link_id]

        for interface_id in removed_interfaces:
            interface = self._interfaces[interface_id]
            _LOGGER.info("Removed interface %s", interface)
            del self._interfaces[interface_id]

        for node_id in removed_nodes:
            node = self._nodes[node_id]
            _LOGGER.info("Removed node %s", node)
            del self._nodes[node_id]

    def _add_elements(
        self,
        topology: dict,
        new_nodes: Iterable[str],
        new_links: Iterable[str],
        new_interfaces: Iterable[str],
    ) -> None:
        for node in topology["nodes"]:
            node_id = node["id"]
            interfaces = node.pop("interfaces", [])
            if node_id in new_nodes:
                node = self._import_node(node_id, node)
                _LOGGER.info("Added node %s", node)

            if not interfaces:
                continue

            for interface in interfaces:
                interface_id = interface["id"]
                if interface_id in new_interfaces:
                    interface = self._import_interface(interface_id, node_id, interface)
                    _LOGGER.info("Added interface %s", interface)

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
            _LOGGER.info("Added link %s", link)

    def _update_elements(
        self, topology: dict, kept_nodes: Iterable[str], exclude_configurations: bool
    ) -> None:
        for node_id in kept_nodes:
            node = self._find_node_in_topology(node_id, topology)
            lab_node = self._nodes[node_id]
            lab_node.update(node, exclude_configurations)

        # For now, can't update interface data server-side, this will change with tags
        # for interface_id in kept_interfaces:
        #     interface_data = self._find_interface_in_topology(interface_id, topology)

        # For now, can't update link data server-side, this will change with tags
        # for link_id in kept_links:
        #     link_data = self._find_link_in_topology(link_id, topology)

    @staticmethod
    def _find_link_in_topology(link_id: str, topology: dict) -> dict:
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
        for node in topology["nodes"]:
            if node["id"] == node_id:
                return node
        # if it cannot be found, it is an internal structure error
        raise NodeNotFound

    def get_pyats_testbed(self, hostname: Optional[str] = None) -> str:
        """
        Return lab's pyATS YAML testbed. Example usage::

            from pyats.topology import loader

            lab = client_library.join_existing_lab("lab_1")
            testbed_yaml = lab.get_pyats_testbed()

            testbed = loader.load(io.StringIO(testbed_yaml))

            # wait for lab to be ready
            lab.wait_until_lab_converged()

            aetest.main(testbed=testbed)

        :param hostname: Force hostname/ip and port for console terminal server
        :returns: The pyATS testbed for the lab in YAML format
        """
        url = self.lab_base_url + "/pyats_testbed"
        params = {}
        if hostname is not None:
            params["hostname"] = hostname
        result = self._session.get(url, params=params)
        return result.text

    def sync_pyats(self) -> None:
        self.pyats.sync_testbed(self.username, self.password)

    def sync_layer3_addresses(self) -> None:
        """Syncs all layer 3 IP addresses from the backend server."""
        url = self.lab_base_url + "/layer3_addresses"
        result: dict[str, dict] = self._session.get(url).json()
        for node_id, node_data in result.items():
            node = self.get_node_by_id(node_id)
            mapping = node_data.get("interfaces", {})
            node.map_l3_addresses_to_interfaces(mapping)
        self._last_sync_l3_address_time = time.time()

    def cleanup_pyats_connections(self) -> None:
        """Closes and cleans up connection that pyATS might still hold."""
        self.pyats.cleanup()

    def download(self) -> str:
        """
        Download the lab from the server in YAML format.

        :returns: The lab in YAML format
        """
        url = self.lab_base_url + "/download"
        return self._session.get(url).text

    @property
    def groups(self) -> list[dict[str, str]]:
        """
        Returns the groups this lab is associated with.

        :return: associated groups
        """
        url = self.lab_base_url + "/groups"
        return self._session.get(url).json()

    def update_lab_groups(
        self, group_list: list[dict[str, str]]
    ) -> list[dict[str, str]]:
        """
        Modifies lab / group association

        :param group_list: list of objects consisting of group id and permission
        :return: updated objects consisting of group id and permission
        """
        url = self.lab_base_url + "/groups"
        return self._session.put(url, json=group_list).json()

    def sync_operational(self) -> None:
        url = self.lab_base_url + "/resource_pools"
        response = self._session.get(url).json()
        res_pools = self._resource_pool_manager.get_resource_pools_by_ids(response)
        self._resource_pools = list(res_pools.values())
        self._last_sync_operational_time = time.time()

        for node in self._nodes.values():
            node.sync_operational()
