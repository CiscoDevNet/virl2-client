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

from unittest.mock import MagicMock, Mock

import pytest
import requests

from virl2_client.exceptions import NodeNotFound
from virl2_client.models import Interface, Lab
from virl2_client.virl2_client import Context


def test_topology_creation_and_removal():
    context = Context("http://dontcare", requests_session=Mock())
    username = password = "test"
    lab = Lab("laboratory", 1, context, username, password, auto_sync=0)
    node_a = lab.add_node_local("0", "node A", "nd", "im", "cfg", 0, 0)
    node_b = lab.add_node_local("1", "node B", "nd", "im", "cfg", 1, 1)
    node_c = lab.add_node_local("2", "node C", "nd", "im", "cfg", 2, 2)
    i1 = lab.create_interface_local("0", "iface A", node_a, "slot A")
    i2 = lab.create_interface_local("1", "iface B1", node_b, "slot B1")
    i3 = lab.create_interface_local("2", "iface B2", node_b, "slot B2")
    i4 = lab.create_interface_local("3", "iface C", node_c, "slot C")

    lnk1 = lab.create_link_local(i1, i2, "0")
    lnk2 = lab.create_link_local(i3, i4, "1")

    assert sorted([node_b, node_c, node_a]) == [node_a, node_b, node_c]
    assert sorted([i4, i2, i3, i1]) == [i1, i2, i3, i4]
    assert sorted([lnk2, lnk1]) == [lnk1, lnk2]

    assert set(lab.nodes()) == {node_a, node_b, node_c}
    assert lab.statistics == {"nodes": 3, "links": 2, "interfaces": 4}
    assert node_a.degree() == 1
    assert node_b.degree() == 2
    assert node_c.degree() == 1

    assert node_a.links() == [lnk1]
    assert sorted(node_b.links()) == [lnk1, lnk2]
    assert node_c.links() == [lnk2]

    assert i1.degree() == 1
    assert i2.degree() == 1
    assert i3.degree() == 1
    assert i4.degree() == 1

    assert i1.peer_interfaces() == {i2}
    assert i2.peer_interfaces() == {i1}
    assert i3.peer_interfaces() == {i4}
    assert i4.peer_interfaces() == {i3}

    assert i1.peer_nodes() == {node_b}
    assert i2.peer_nodes() == {node_a}
    assert i3.peer_nodes() == {node_c}
    assert i4.peer_nodes() == {node_b}

    assert lnk1.nodes == (node_a, node_b)
    assert lnk1.interfaces == (i1, i2)
    assert lnk2.nodes == (node_b, node_c)
    assert lnk2.interfaces == (i3, i4)

    lab.remove_link(lnk2)
    assert lab.statistics == {"nodes": 3, "links": 1, "interfaces": 4}

    lab.remove_node(node_b)
    assert lab.statistics == {"nodes": 2, "links": 0, "interfaces": 2}

    lab.remove_interface(i4)
    assert lab.statistics == {"nodes": 2, "links": 0, "interfaces": 1}

    lab.remove_interface(i1)
    assert lab.statistics == {"nodes": 2, "links": 0, "interfaces": 0}

    lab.remove_node(node_a)
    assert lab.statistics == {"nodes": 1, "links": 0, "interfaces": 0}

    lab.remove_node(node_c)
    assert lab.statistics == {"nodes": 0, "links": 0, "interfaces": 0}


def test_need_to_wait1():
    context = Context("http://dontcare", requests_session=Mock())
    username = password = "test"
    lab = Lab("laboratory",
              1,
              context,
              username,
              password,
              auto_sync=0,
              wait=True)
    assert lab.need_to_wait(None) == True
    assert lab.need_to_wait(False) == False
    assert lab.need_to_wait(True) == True


def test_need_to_wait2():
    context = Context("http://dontcare", requests_session=Mock())
    username = password = "test"
    lab = Lab("laboratory",
              1,
              context,
              username,
              password,
              auto_sync=0,
              wait=False)
    assert lab.need_to_wait(None) == False
    assert lab.need_to_wait(False) == False
    assert lab.need_to_wait(True) == True


def test_str_and_repr():
    context = Context("http://dontcare", requests_session=Mock())
    username = password = "test"
    lab = Lab("laboratory",
              1,
              context,
              username,
              password,
              auto_sync=0,
              wait=False)
    assert str(lab) == "Lab: laboratory"
    assert repr(lab).startswith("Lab('laboratory', 1, Context(")


def test_create_node():
    context = Context("http://dontcare", requests_session=MagicMock())
    username = password = "test"
    lab = Lab("laboratory",
              1,
              context,
              username,
              password,
              auto_sync=0,
              wait=False)
    node = lab.create_node("testnode", "server")
    assert node.node_definition == "server"
    assert node.label == "testnode"


def test_create_link(requests_mock):
    requests_mock.post("mock://labs/1/nodes", json={"id": "n0"})
    requests_mock.post("mock://labs/1/interfaces",
                       json={
                           "id": "i0",
                           "label": "eth0",
                           "slot": 0
                       })
    requests_mock.post("mock://labs/1/links",
                       json={
                           "id": "l0",
                           "label": "segment0"
                       })
    session = requests.Session()
    context = Context("mock://", requests_session=session)
    # requests_mock.post("http://dontcare", )
    username = password = "test"
    lab = Lab("laboratory",
              1,
              context,
              username,
              password,
              auto_sync=0,
              wait=False)
    node1 = lab.create_node("testnode", "server")
    node1_i1 = node1.create_interface()
    assert isinstance(node1_i1, Interface)
    node2 = lab.create_node("testnode", "server")
    node2_i1 = node2.create_interface()
    link = lab.create_link(node1_i1, node2_i1)
    assert link.as_dict() == {
        "id": "l0",
        "interface_a": "i0",
        "interface_b": "i0"
    }
    assert link.nodes[0].label == "testnode"
    assert link.nodes[1].label == "testnode"
    assert link.statistics == {
        "readbytes": 0,
        "readpackets": 0,
        "writebytes": 0,
        "writepackets": 0,
    }
    assert link.id == "l0"


def test_sync_stats(requests_mock):
    requests_mock.get("mock://labs/1/simulation_stats",
                      json={
                          "nodes": {},
                          "links": {}
                      })
    session = requests.Session()
    context = Context("mock://", requests_session=session)
    username = password = "test"
    lab = Lab("laboratory",
              1,
              context,
              username,
              password,
              auto_sync=0,
              wait=False)
    lab.sync_statistics()


def test_tags():
    context = Context("http://dontcare", requests_session=Mock())
    username = password = "test"
    lab = Lab("laboratory", 1, context, username, password, auto_sync=0)
    node_a = lab.add_node_local("0", "node A", "nd", "im", "cfg", 0, 0)
    node_b = lab.add_node_local("1", "node B", "nd", "im", "cfg", 0, 0)
    node_c = lab.add_node_local("2", "node C", "nd", "im", "cfg", 0, 0)
    node_d = lab.add_node_local("3", "node D", "nd", "im", "cfg", 0, 0)
    assert len(node_a.tags()) == 0
    node_a.add_tag("Core")
    node_a.add_tag("Europe")
    node_a.add_tag("Test")
    assert len(node_a.tags()) == 3
    node_a.remove_tag("Test")
    assert len(node_a.tags()) == 2

    node_b.add_tag("Core")
    node_c.add_tag("Core")
    node_d.add_tag("Europe")

    core = lab.find_nodes_by_tag("Core")
    assert len(core) == 3

    europe = lab.find_nodes_by_tag("Europe")
    assert len(europe) == 2


def test_find_by_label():

    context = Context("http://dontcare", requests_session=Mock())
    username = password = "test"
    lab = Lab("laboratory", 1, context, username, password, auto_sync=0)

    node_a = lab.add_node_local("n0", "server-a", "nd", "im", "cfg", 0, 0)
    node_b = lab.add_node_local("n1", "server-b", "nd", "im", "cfg", 0, 0)
    node_c = lab.add_node_local("n2", "server-c", "nd", "im", "cfg", 0, 0)
    node_d = lab.add_node_local("n3", "server-d", "nd", "im", "cfg", 0, 0)

    node = lab.get_node_by_label("server-a")
    assert node.id == "n0"

    with pytest.raises(NodeNotFound) as exc:
        node = lab.get_node_by_label("does-not-exist")
        print(exc)
        assert node is None


def test_next_free_interface():
    context = Context("http://dontcare", requests_session=Mock())
    username = password = "test"
    lab = Lab("laboratory", 1, context, username, password, auto_sync=0)
    node_a = lab.add_node_local("0", "node A", "nd", "im", "cfg", 0, 0)
    node_b = lab.add_node_local("1", "node B", "nd", "im", "cfg", 1, 1)

    nf = node_a.next_available_interface()
    assert nf == None

    i1 = lab.create_interface_local("0", "iface 0", node_a, "slot 0")
    nf = node_a.next_available_interface()
    assert i1 == nf

    i2 = lab.create_interface_local("4", "iface 4", node_b, "slot 4")
    lnk1 = lab.create_link_local(i1, i2, "0")

    nf = node_a.next_available_interface()
    assert nf == None


def test_connect_two_nodes(requests_mock):
    requests_mock.post("mock://labs/1/nodes", json={"id": "n0"})
    requests_mock.post("mock://labs/1/interfaces",
                       json={
                           "id": "i0",
                           "label": "eth0",
                           "slot": 0
                       })
    requests_mock.post("mock://labs/1/links",
                       json={
                           "id": "l0",
                           "label": "segment0"
                       })
    session = requests.Session()
    context = Context("mock://", requests_session=session)
    # requests_mock.post("http://dontcare", )
    username = password = "test"
    lab = Lab("laboratory",
              1,
              context,
              username,
              password,
              auto_sync=0,
              wait=False)
    node1 = lab.create_node("testnode", "server")
    node2 = lab.create_node("testnode", "server")
    link = lab.connect_two_nodes(node1, node2)
    assert link.as_dict() == {
        "id": "l0",
        "interface_a": "i0",
        "interface_b": "i0"
    }
    assert link.nodes[0].label == "testnode"
    assert link.nodes[1].label == "testnode"
    assert link.statistics == {
        "readbytes": 0,
        "readpackets": 0,
        "writebytes": 0,
        "writepackets": 0,
    }
    assert link.id == "l0"
