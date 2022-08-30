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

import json
import logging
import warnings
import time
from typing import Dict

from .node import Node
from .interface import Interface
from .link import Link
from ..exceptions import (
    LabNotFound,
    LinkNotFound,
    NodeNotFound,
    ElementAlreadyExists,
    InterfaceNotFound,
)
from .cl_pyats import ClPyats

_LOGGER = logging.getLogger(__name__)


class Lab:
    def __init__(
        self,
        title,
        lab_id,
        context,
        username,
        password,
        auto_sync=True,
        auto_sync_interval=1.0,
        wait=True,
        wait_max_iterations=500,
        wait_time=5,
        hostname=None,
    ):
        """
        A VIRL2 lab network topology. Contains nodes, links and interfaces.

        :param title: Name / title of the lab
        :type title: str
        :param lab_id: A lab ID
        :type lab_id: str
        :param context: The context of the ClientLibrary that holds the connection data
            to the server
        :type context: Context
        :param username: Username of the user to authenticate
        :type username: str
        :param password: Password of the user to authenticate
        :type password: str
        :param auto_sync: Should local changes sync to the server automatically
        :type auto_sync: bool
        :param auto_sync_interval: Interval to auto sync in seconds
        :type auto_sync_interval: float
        :param wait: Wait for convergence on backend
        :type wait: bool
        :param wait_max_iterations: Maximum number of tries or calls for convergence
        :type wait_max_iterations: int
        :param wait_time: Time to sleep between calls for convergence on backend
        :type wait_time: int
        :param hostname: Force hostname/ip and port for pyATS console terminal server
        :type hostname: str
        """

        self.username = username
        self.password = password

        self._title = title
        self._description = ""
        self._notes = ""
        self._lab_id = lab_id
        self._context = context
        self._owner = username
        self._nodes: Dict[str, Node] = {}
        """
        Dictionary containing all nodes in the lab.
        It maps node identifier to `models.Node`
        """
        self._links: Dict[str, Link] = {}
        """
        Dictionary containing all links in the lab.
        It maps link identifier to `models.Link`
        """
        self._interfaces: Dict[str, Interface] = {}
        """
        Dictionary containing all interfaces in the lab.
        It maps interface identifier to `models.Interface`
        """
        self.events = []
        self.pyats = ClPyats(self, hostname)
        self.auto_sync = auto_sync
        self.auto_sync_interval = auto_sync_interval

        self._last_sync_statistics_time = 0
        self._last_sync_state_time = 0
        self._last_sync_l3_address_time = 0
        self._last_sync_topology_time = 0

        self._initialized = False

        self.wait_for_convergence = wait
        self.wait_max_iterations = wait_max_iterations
        self.wait_time = wait_time

    def __len__(self):
        return len(self._nodes)

    def __str__(self):
        return "Lab: {}".format(self._title)

    def __repr__(self):
        return "{}({!r}, {!r}, {!r}, {!r}, {!r}, {!r})".format(
            self.__class__.__name__,
            self._title,
            self._lab_id,
            self._context,
            self.auto_sync,
            self.auto_sync_interval,
            self.wait_for_convergence,
        )

    def need_to_wait(self, local_wait):
        if local_wait is None:
            return self.wait_for_convergence
        if not isinstance(local_wait, bool):
            raise ValueError
        return local_wait

    def sync_statistics_if_outdated(self):
        timestamp = time.time()
        if (
            self.auto_sync
            and timestamp - self._last_sync_statistics_time > self.auto_sync_interval
        ):
            self.sync_statistics()

    def sync_states_if_outdated(self):
        timestamp = time.time()
        if (
            self.auto_sync
            and timestamp - self._last_sync_state_time > self.auto_sync_interval
        ):
            self.sync_states()

    def sync_l3_addresses_if_outdated(self):
        timestamp = time.time()
        if (
            self.auto_sync
            and timestamp - self._last_sync_l3_address_time > self.auto_sync_interval
        ):
            self.sync_layer3_addresses()

    def sync_topology_if_outdated(self):
        timestamp = time.time()
        if (
            self.auto_sync
            and timestamp - self._last_sync_topology_time > self.auto_sync_interval
        ):
            self._sync_topology(exclude_configurations=True)

    @property
    def id(self):
        """
        Returns the ID of the lab (a 6 digit hex string).

        :returns: The Lab ID
        :rtype: str
        """

        return self._lab_id

    @property
    def title(self):
        """
        Returns the title of the lab.

        :returns: The lab name
        :rtype: str
        """
        self.sync_topology_if_outdated()
        return self._title

    @title.setter
    def title(self, value):
        """
        Set the title of the lab to value.

        :param value: The new lab title
        :type value: str
        """
        url = self.lab_base_url
        response = self.session.patch(url, json={"title": value})
        response.raise_for_status()
        self._title = value

    @property
    def notes(self):
        """
        Returns the notes of the lab.

        :returns: The lab name
        :rtype: str
        """
        self.sync_topology_if_outdated()
        return self._notes

    @notes.setter
    def notes(self, value):
        """
        Set the notes of the lab to value.

        :param value:
        :type value: str
        """
        url = self.lab_base_url
        response = self.session.patch(url, json={"notes": value})
        response.raise_for_status()
        self._notes = value

    @property
    def description(self):
        """
        Returns the description of the lab.

        :returns: The lab name
        :rtype: str
        """
        self.sync_topology_if_outdated()
        return self._description

    @description.setter
    def description(self, value):
        """
        Set the description of the lab to value.

        :param value:
        :type value: str
        """
        url = self.lab_base_url
        response = self.session.patch(url, json={"description": value})
        response.raise_for_status()
        self._description = value

    @property
    def session(self):
        """
        Returns the Requests session from the given context.

        :returns: A Session
        :rtype: Requests.Session
        """
        return self._context.session

    @property
    def owner(self):
        """
        Returns the owner of the lab.

        :returns: A username
        :rtype: str
        """
        self.sync_topology_if_outdated()
        return self._owner

    def nodes(self):
        """
        Returns the list of nodes in the lab.

        :returns: A list of Node objects
        :rtype: List[Node]
        """
        self.sync_topology_if_outdated()
        return list(self._nodes.values())

    def links(self):
        """
        Returns the list of links in the lab.

        :returns: A list of Link objects
        :rtype: List[Link]
        """
        self.sync_topology_if_outdated()
        return list(self._links.values())

    def interfaces(self):
        """
        Returns the list of interfaces in the lab.

        :returns: A list of Interface objects
        :rtype: List[Interface]
        """
        self.sync_topology_if_outdated()
        return list(self._interfaces.values())

    @property
    def lab_base_url(self):
        return self._context.base_url + "labs/{}".format(self._lab_id)

    @property
    def statistics(self):
        """
        Returns some statistics about the lab.

        :returns: A dictionary with stats of the lab
        :rtype: dict
        """
        return {
            "nodes": len(self._nodes),
            "links": len(self._links),
            "interfaces": len(self._interfaces),
        }

    def get_node_by_id(self, node_id):
        """
        Returns the node identified by the ID.

        :param node_id: ID of the node to be returned
        :type node_id: str
        :returns: A Node object
        :rtype: models.Node
        :raises NodeNotFound: If node not found
        """
        self.sync_topology_if_outdated()
        try:
            return self._nodes[node_id]
        except KeyError:
            raise NodeNotFound(node_id)

    def get_node_by_label(self, label):
        """
        Returns the node identified by the label.

        :param label: label of the node to be returned
        :type label: str
        :returns: A Node object
        :rtype: models.Node
        :raises NodeNotFound: If node not found
        """
        self.sync_topology_if_outdated()
        for node in self._nodes.values():
            if node.label == label:
                return node
        raise NodeNotFound(label)

    def get_interface_by_id(self, interface_id):
        """
        Returns the interface identified by the ID.

        :param interface_id: ID of the interface to be returned
        :type interface_id: str
        :returns: An Interface object
        :rtype: models.Interface
        :raises InterfaceNotFound: If interface not found
        """
        self.sync_topology_if_outdated()
        try:
            return self._interfaces[interface_id]
        except KeyError:
            raise InterfaceNotFound(interface_id)

    def get_link_by_id(self, link_id):
        """
        Returns the link identified by the ID.

        :param link_id: ID of the interface to be returned
        :type link_id: str
        :returns: A Link object
        :rtype: models.Link
        :raises LinkNotFound: If interface not found
        """
        self.sync_topology_if_outdated()
        try:
            return self._links[link_id]
        except KeyError:
            raise LinkNotFound(link_id)

    @staticmethod
    def get_link_by_nodes(node1, node2):
        """
        DEPRECATED

        Returns ONE of the links identified by two node objects.

        Deprecated. Use `Node.get_link_to` to get one link
        or `Node.get_links_to` to get all links.

        :param node1: the first node
        :type node1: models.Node
        :param node2: the second node
        :type node2: models.Node
        :returns: one of links between the nodes
        :rtype: models.Link
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
    def get_link_by_interfaces(iface1, iface2):
        """
        DEPRECATED

        Returns the link identified by two interface objects.

        Deprecated. Use `Interface.get_link_to` to get link.

        :param iface1: the first interface
        :type iface1: models.Interface
        :param iface2: the second interface
        :type iface2: models.Interface
        :returns: the link between the interfaces
        :rtype: models.Link
        :raises LinkNotFound: If no such link exists
        """
        warnings.warn(
            "Deprecated, use Interface.get_link_to instead.", DeprecationWarning
        )
        link = iface1.link
        if iface2 in link.interfaces:
            return link
        raise LinkNotFound

    def find_nodes_by_tag(self, tag):
        """
        Returns the nodes identified by the given tag.

        :param tag: tag of the nodes to be returned
        :type tag: str
        :returns: a list of nodes
        :rtype: List[Node]
        """
        self.sync_topology_if_outdated()
        return [node for node in self.nodes() if tag in node.tags()]

    def create_node(
        self,
        label,
        node_definition,
        x=0,
        y=0,
        wait=None,
        populate_interfaces=False,
        **kwargs,
    ):
        """
        Creates a node in the lab with the given parameters.

        :param label: Label
        :type label: str
        :param node_definition: Node definition to use
        :type label: str
        :param x: x coordinate
        :type x: int
        :param y: y coordinate
        :type y: int
        :param wait: Wait for convergence (if left at default,
            the lab wait property takes precedence)
        :type wait: bool
        :param populate_interfaces: automatically create pre-defined number
            of interfaces on node creation
        :returns: a Node object
        :rtype: models.Node
        """
        # TODO: warn locally if label in use already?
        url = self.lab_base_url + "/nodes"
        if populate_interfaces:
            url += "?populate_interfaces=true"
        kwargs["label"] = label
        kwargs["node_definition"] = node_definition
        kwargs["x"] = x
        kwargs["y"] = y
        response = self.session.post(url, json=kwargs)
        result = response.json()
        response.raise_for_status()
        node_id = result["id"]
        config = ""

        # if add node to an empty lab, then consider it "initialized" for sync purposes
        if not self._initialized:
            self._initialized = True

        # fetch default image def
        image_definition = None

        if self.need_to_wait(wait):
            self.wait_until_lab_converged()

        node = self.add_node_local(
            node_id, label, node_definition, image_definition, config, x, y
        )
        return node

    def add_node_local(
        self,
        node_id,
        label,
        node_definition,
        image_definition,
        config,
        x,
        y,
        ram=0,
        cpus=0,
        cpu_limit=100,
        data_volume=0,
        boot_disk_size=0,
        tags=None,
    ):
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
            config,
            x,
            y,
            ram,
            cpus,
            cpu_limit,
            data_volume,
            boot_disk_size,
            tags,
        )
        self._nodes[node.id] = node
        return node

    def remove_node(self, node, wait=None):
        """
        Removes a node from the lab.

        :param node: the node
        :type node: Node
        :param wait: Wait for convergence (if left at default,
            the lab wait property takes precedence)
        :type wait: bool
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

    def remove_nodes(self, wait=None):
        """
        Remove all nodes from the lab.

        :param wait: Wait for convergence (if left at default,
            the lab wait property takes precedence)
        :type wait: bool
        """
        # TODO: see if this is used - in testing?
        for node in list(self._nodes.values()):
            self.remove_node(node, wait=False)

        if self.need_to_wait(wait):
            self.wait_until_lab_converged()
        _LOGGER.debug("all nodes removed from lab %s", self._lab_id)

    def remove_link(self, link, wait=None):
        """
        Removes a link from the lab.

        :param link: the link
        :type link: Link
        :param wait: Wait for convergence (if left at default,
            the lab wait property takes precedence)
        :type wait: bool
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

    def remove_interface(self, iface, wait=None):
        """
        Removes an interface from the lab.

        :param iface: the interface
        :type iface: Interface
        :param wait: Wait for convergence (if left at default,
            the lab wait property takes precedence)
        :type wait: bool
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

    def create_link(self, i1, i2, wait=None):
        """
        Creates a link between two interfaces

        :param i1: the first interface object
        :type i1: models.Interface
        :param i2: the second interface object
        :type i2: models.Interface
        :param wait: Wait for convergence (if left at default,
            the lab wait property takes precedence)
        :type wait: bool
        :returns: the created link
        :rtype: models.Link
        """
        url = self.lab_base_url + "/links"
        data = {
            "src_int": i1.id,
            "dst_int": i2.id,
        }
        response = self.session.post(url, json=data)
        result = response.json()
        link_id = result["id"]

        if self.need_to_wait(wait):
            self.wait_until_lab_converged()

        link = self.create_link_local(i1, i2, link_id)
        return link

    def connect_two_nodes(self, node1, node2):
        """
        Convenience method to connect two nodes within a lab.

        :param node1: the first node object
        :type node1: models.Node
        :param node2: the second node object
        :type node2: models.Node
        :returns: the created link
        :rtype: models.Link
        """
        iface1 = node1.next_available_interface() or node1.create_interface()
        iface2 = node2.next_available_interface() or node2.create_interface()
        return self.create_link(iface1, iface2)

    def create_link_local(self, i1, i2, link_id):
        """Helper function to create a link in the client library."""
        link = Link(self, link_id, i1, i2)
        self._links[link_id] = link
        return link

    def create_interface(self, node, slot=None, wait=None):
        """
        Create an interface in the specified slot or, if no slot
        is given, in the next available slot.

        :param node: The node on which the interface is created
        :type node: models.Node
        :param slot: (optional)
        :type slot: int
        :param wait: Wait for convergence (if left at default,
            the lab wait property takes precedence)
        :type wait: bool
        :returns: The newly created interface
        :rtype: models.Interface
        """
        url = self.lab_base_url + "/interfaces"
        payload = {"node": node.id}
        if slot is not None:
            payload["slot"] = slot
        response = self.session.post(url, json=payload)
        response.raise_for_status()
        result = response.json()
        if isinstance(result, dict):
            # in case API returned just one interface, pack it into the list:
            result = [result]

        if self.need_to_wait(wait):
            self.wait_until_lab_converged()

        # TODO: need to import the topology then
        desired_interface = None
        for iface in result:
            lab_interface = self.create_interface_local(
                iface_id=iface["id"],
                label=iface["label"],
                node=node,
                slot=iface["slot"],
            )
            if slot == iface["slot"] or slot is None:
                desired_interface = lab_interface

        return desired_interface

    def create_interface_local(
        self, iface_id, label, node, slot, iface_type="physical"
    ):
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

    def sync_statistics(self):
        """Retrieve the simulation statistic data from the back end server."""
        url = self.lab_base_url + "/simulation_stats"
        response = self.session.get(url)
        response.raise_for_status()
        states = response.json()
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

    def sync_states(self):
        """
        Sync all the states of the various elements with the back end server.
        """
        url = self.lab_base_url + "/lab_element_state"
        response = self.session.get(url)
        response.raise_for_status()
        states = response.json()

        for node_id, node_state in states["nodes"].items():
            self._nodes[node_id]._state = node_state

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

    def wait_until_lab_converged(self, max_iterations=None, wait_time=None):
        """Wait until lab converge."""
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

    def has_converged(self):
        url = self.lab_base_url + "/check_if_converged"
        response = self.session.get(url)
        response.raise_for_status()
        converged = response.json()
        return converged

    def start(self, wait=None):
        """
        Start all the nodes and links in the lab.

        :param wait: Wait for convergence (if left at default,
            the lab wait property takes precedence)
        :type wait: bool
        """
        url = self.lab_base_url + "/start"
        response = self.session.put(url)
        response.raise_for_status()
        if self.need_to_wait(wait):
            self.wait_until_lab_converged()
        _LOGGER.debug("started lab: %s", self._lab_id)

    def state(self):
        """
        Returns the state of the lab.

        :returns: The state as text
        :rtype: str
        """
        url = self.lab_base_url + "/state"
        response = self.session.get(url)
        response.raise_for_status()
        _LOGGER.debug("lab state: %s -> %s", self._lab_id, response.text)
        return response.json()

    def is_active(self):
        """
        Returns whether the lab is started.

        :returns: Whether the lab is started
        :rtype: bool
        """
        return self.state() == "STARTED"

    def details(self):
        """
        Returns the lab details (including state) of the lab.

        :returns: The detailed lab state
        :rtype: dict
        """
        url = self.lab_base_url
        response = self.session.get(url)
        response.raise_for_status()
        _LOGGER.debug("lab state: %s -> %s", self._lab_id, response.text)
        return response.json()

    def stop(self, wait=None):
        """
        Stops all the nodes and links in the lab.

        :param wait: Wait for convergence (if left at default,
            the lab wait property takes precedence)
        :type wait: bool
        """
        url = self.lab_base_url + "/stop"
        response = self.session.put(url)
        response.raise_for_status()
        if self.need_to_wait(wait):
            self.wait_until_lab_converged()
        _LOGGER.debug("stopped lab: %s", self._lab_id)

    def wipe(self, wait=None):
        """
        Wipe all the nodes and links in the lab.

        :param wait: Wait for convergence (if left at default,
            the lab wait property takes precedence)
        :type wait: bool
        """
        url = self.lab_base_url + "/wipe"
        response = self.session.put(url)
        response.raise_for_status()
        if self.need_to_wait(wait):
            self.wait_until_lab_converged()
        _LOGGER.debug("wiped lab: %s", self._lab_id)

    def remove(self):
        """
        Removes the lab from the server. The lab has to
        be stopped and wiped for this to work.

        Use carefully, it removes current lab::

            lab.remove()

        """
        # TODO: mark as disconnected
        url = self.lab_base_url
        response = self.session.delete(url)
        response.raise_for_status()
        _LOGGER.debug("removed lab: %s", response.text)

    def sync_events(self):
        # TODO: return a boolean if events have changed since last run
        url = self.lab_base_url + "/events"
        response = self.session.get(url)
        response.raise_for_status()
        result = response.json()
        self.events = result

    def build_configurations(self):
        """
        Build basic configurations for all nodes in the lab which
        do not already have a configuration and also do support
        configuration building.
        """

        url = self._context.base_url + "build_configurations?lab_id=" + self._lab_id
        self.session.get(url)
        # sync to get the updated configs
        self.sync_topology_if_outdated()

    def sync(
        self,
        topology_only=True,
        with_node_configurations=None,
        exclude_configurations=False,
    ):
        """
        Synchronize current lab applying the changes that
        were done in UI or in another ClientLibrary session::

            lab.sync()

        :param topology_only: do not sync statistics and IP addresses
        :type topology_only: bool
        :param with_node_configurations: DEPRECATED, does the opposite of
            what is expected: disables syncing node configuration when True
        :type with_node_configurations: bool
        :param exclude_configurations: disable syncing node configuration
        :type exclude_configurations: bool
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

    def _sync_topology(self, exclude_configurations=False):
        """Helper function to sync topologies from the backend server."""
        # TODO: check what happens if call twice
        url = self._context.base_url + "labs/{}".format(self._lab_id) + "/topology"
        params = {"exclude_configurations": exclude_configurations}
        result = self.session.get(url, params=params)
        if not result.ok:
            try:
                # Get the error message from the API's JSON error object.
                resp_dict = json.loads(result.text)
                error_msg = resp_dict["description"]
            except (ValueError, TypeError, KeyError):
                # result.text was empty, not a JSON object, or not the expected
                # JSON schema. Use the raw result text.
                error_msg = result.text
            raise LabNotFound("Error syncing lab: {}".format(error_msg))
            # TODO: get the error message from response/headers also?
        topology = result.json()
        if self._initialized:
            self.update_lab(topology, exclude_configurations)
        else:
            self.import_lab(topology)
            self._initialized = True
        self._last_sync_topology_time = time.time()

    def import_lab(self, topology):
        self._import_lab(topology)

        self._handle_import_nodes(topology)
        self._handle_import_interfaces(topology)
        self._handle_import_links(topology)

    def _import_lab(self, topology):
        """Replaces lab properties. Will raise KeyError if any property is missing."""
        lab_dict = topology.get("lab")
        if lab_dict is None:
            warnings.warn(
                "Labs created in older CML releases (schema version 0.0.5 or lower) "
                "are deprecated.  Use labs with schema version 0.1.0 instead.",
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

    def _handle_import_nodes(self, topology):
        for node in topology["nodes"]:
            node_id = node["id"]
            if node_id in self._nodes:
                raise ElementAlreadyExists("Node already exists")
            self._import_node(node_id, node)

            if "interfaces" not in node:
                continue

            for iface in node["interfaces"]:
                iface_id = iface["id"]
                if iface_id in self._interfaces:
                    raise ElementAlreadyExists("Interface already exists")
                self._import_interface(iface_id, node_id, iface)

    def _handle_import_interfaces(self, topology):
        if "interfaces" in topology:
            for iface in topology["interfaces"]:
                iface_id = iface["id"]
                node_id = iface["node"]
                if iface_id in self._interfaces:
                    raise ElementAlreadyExists("Interface already exists")
                self._import_interface(iface_id, node_id, iface)

    def _handle_import_links(self, topology):
        for link in topology["links"]:
            link_id = link["id"]
            if link_id in self._links:
                raise ElementAlreadyExists("Link already exists")
            iface_a_id = link["interface_a"]
            iface_b_id = link["interface_b"]
            self._import_link(link_id, iface_b_id, iface_a_id)

    def _import_link(self, link_id, iface_b_id, iface_a_id):
        iface_a = self._interfaces[iface_a_id]
        iface_b = self._interfaces[iface_b_id]
        return self.create_link_local(iface_a, iface_b, link_id)

    def _import_interface(self, iface_id, node_id, iface_data):
        if "data" in iface_data:
            iface_data = iface_data["data"]
        label = iface_data["label"]
        slot = iface_data.get("slot")
        iface_type = iface_data["type"]
        node = self._nodes[node_id]
        return self.create_interface_local(iface_id, label, node, slot, iface_type)

    def _import_node(self, node_id, node_data):
        if "data" in node_data:
            node_data = node_data["data"]
        node = self.add_node_local(
            node_id,
            node_data["label"],
            node_data["node_definition"],
            node_data.get("image_definition", None),
            node_data.get("configuration", ""),
            node_data["x"],
            node_data["y"],
        )
        node.update(node_data, "configuration" not in node_data)
        return node

    def update_lab(self, topology, exclude_configurations):
        self._import_lab(topology)

        # add in order: node -> interface -> link
        # remove in reverse, eg link -> interface -> node
        existing_node_keys = set(self._nodes.keys())
        existing_link_keys = set(self._links.keys())
        existing_interface_keys = set(self._interfaces.keys())

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

    def _remove_elements(self, removed_nodes, removed_links, removed_interfaces):
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

    def _add_elements(self, topology, new_nodes, new_links, new_interfaces):
        for node in topology["nodes"]:
            node_id = node["id"]
            if node_id in new_nodes:
                node = self._import_node(node_id, node)
                _LOGGER.info("Added node %s", node)

            if "interfaces" in topology:
                continue

            for interface in node["interfaces"]:
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
            link = self._import_link(link_id, iface_b_id, iface_a_id)
            _LOGGER.info("Added link %s", link)

    def _update_elements(self, topology, kept_nodes, exclude_configurations):
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
    def _find_link_in_topology(link_id, topology):
        for link in topology["links"]:
            if link["id"] == link_id:
                return link
        # if cannot find, is an internal structure error
        return

    # @staticmethod
    # def _find_interface_in_topology(interface_id, topology):
    #     for node in topology["nodes"]:
    #         for interface in node["interfaces"]:
    #             if interface["id"] == interface_id:
    #                 return interface
    #     # if cannot find, is an internal structure error
    #     return

    @staticmethod
    def _find_node_in_topology(node_id, topology):
        for node in topology["nodes"]:
            if node["id"] == node_id:
                return node
        # if cannot find, is an internal structure error
        return

    def get_pyats_testbed(self, hostname=None):
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
        :type hostname: str
        :returns: The pyATS testbed for the lab in YAML format
        :rtype: str
        """
        url = self._context.base_url + "labs/{}".format(self._lab_id) + "/pyats_testbed"
        params = {}
        if hostname is not None:
            params["hostname"] = hostname
        result = self.session.get(url, params=params)
        return result.text

    def sync_pyats(self):
        self.pyats.sync_testbed(self.username, self.password)

    def sync_layer3_addresses(self):
        """Syncs all layer 3 IP addresses from the backend server."""
        url = self.lab_base_url + "/layer3_addresses"
        response = self.session.get(url)
        response.raise_for_status()
        result = response.json()
        for node_id, node_data in result.items():
            node = self.get_node_by_id(node_id)
            mapping = node_data.get("interfaces", {})
            node.map_l3_addresses_to_interfaces(mapping)
        self._last_sync_l3_address_time = time.time()

    def cleanup_pyats_connections(self):
        """Closes and cleans up connection that pyATS might still hold."""
        self.pyats.cleanup()

    def download(self):
        """
        Download the lab from the server in YAML format.

        :returns: The lab in YAML format
        :rtype: str
        """
        url = self.lab_base_url + "/download"
        response = self.session.get(url)
        response.raise_for_status()
        return response.text

    @property
    def groups(self):
        """
        Returns the groups this lab is associated with.

        :return: associated groups
        :rtype: List[Dict[str, str]]
        """
        url = self.lab_base_url + "/groups"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def update_lab_groups(self, group_list):
        """
        Modifies lab / group association

        :param group_list: list of objects consisting of group id and permission
        :rtype: group_list: List[Dict[str, str]]
        :return: updated objects consisting of group id and permission
        :rtype: List[Dict[str, str]]
        """
        url = self.lab_base_url + "/groups"
        response = self.session.put(url, json=group_list)
        response.raise_for_status()
        return response.json()
