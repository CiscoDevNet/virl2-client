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

from unittest.mock import MagicMock, Mock

import pytest

from virl2_client.exceptions import NodeNotFound
from virl2_client.models import Interface, Lab
from virl2_client.models.authentication import make_session

RESOURCE_POOL_MANAGER = Mock()


def test_topology_creation_and_removal():
    session = MagicMock()
    username = password = "test"
    lab = Lab(
        "laboratory",
        "1",
        session,
        username,
        password,
        auto_sync=0,
        resource_pool_manager=RESOURCE_POOL_MANAGER,
    )
    node_a = lab._create_node_local("0", "node A", "nd")
    node_b = lab._create_node_local("1", "node B", "nd")
    node_c = lab._create_node_local("2", "node C", "nd")
    i1 = lab._create_interface_local("0", "iface A", node_a, 0)
    i2 = lab._create_interface_local("1", "iface B1", node_b, 1)
    i3 = lab._create_interface_local("2", "iface B2", node_b, 2)
    i4 = lab._create_interface_local("3", "iface C", node_c, 3)

    lnk1 = lab._create_link_local(i1, i2, "0")
    lnk2 = lab._create_link_local(i3, i4, "1")

    assert set(lab.nodes()) == {node_a, node_b, node_c}
    assert lab.statistics == {
        "annotations": 0,
        "nodes": 3,
        "links": 2,
        "interfaces": 4,
        "smart_annotations": 0,
    }
    assert node_a.degree() == 1
    assert node_b.degree() == 2
    assert node_c.degree() == 1

    assert node_a.links() == [lnk1]
    assert node_c.links() == [lnk2]

    assert i1.connected is True
    assert i2.connected is True
    assert i3.connected is True
    assert i4.connected is True

    assert i1.peer_interface is i2
    assert i2.peer_interface is i1
    assert i3.peer_interface is i4
    assert i4.peer_interface is i3

    assert i1.peer_node is node_b
    assert i2.peer_node is node_a
    assert i3.peer_node is node_c
    assert i4.peer_node is node_b

    assert lnk1.nodes == (node_a, node_b)
    assert lnk1.interfaces == (i1, i2)
    assert lnk2.nodes == (node_b, node_c)
    assert lnk2.interfaces == (i3, i4)

    lab.remove_link(lnk2)
    assert lab.statistics == {
        "annotations": 0,
        "nodes": 3,
        "links": 1,
        "interfaces": 4,
        "smart_annotations": 0,
    }

    lab.remove_node(node_b)
    assert lab.statistics == {
        "annotations": 0,
        "nodes": 2,
        "links": 0,
        "interfaces": 2,
        "smart_annotations": 0,
    }

    lab.remove_interface(i4)
    assert lab.statistics == {
        "annotations": 0,
        "nodes": 2,
        "links": 0,
        "interfaces": 1,
        "smart_annotations": 0,
    }

    lab.remove_interface(i1)
    assert lab.statistics == {
        "annotations": 0,
        "nodes": 2,
        "links": 0,
        "interfaces": 0,
        "smart_annotations": 0,
    }

    lab.remove_node(node_a)
    assert lab.statistics == {
        "annotations": 0,
        "nodes": 1,
        "links": 0,
        "interfaces": 0,
        "smart_annotations": 0,
    }

    lab.remove_node(node_c)
    assert lab.statistics == {
        "annotations": 0,
        "nodes": 0,
        "links": 0,
        "interfaces": 0,
        "smart_annotations": 0,
    }


def test_need_to_wait1():
    session = MagicMock()
    username = password = "test"
    lab = Lab(
        "laboratory",
        "1",
        session,
        username,
        password,
        auto_sync=0,
        wait=True,
        resource_pool_manager=RESOURCE_POOL_MANAGER,
    )
    assert lab.need_to_wait(None) is True
    assert lab.need_to_wait(False) is False
    assert lab.need_to_wait(True) is True


def test_need_to_wait2():
    session = MagicMock()
    username = password = "test"
    lab = Lab(
        "laboratory",
        "1",
        session,
        username,
        password,
        auto_sync=0,
        wait=False,
        resource_pool_manager=RESOURCE_POOL_MANAGER,
    )
    assert lab.need_to_wait(None) is False
    assert lab.need_to_wait(False) is False
    assert lab.need_to_wait(True) is True


def test_str_and_repr():
    session = make_session("http://dontcare")
    username = password = "test"
    lab = Lab(
        "laboratory",
        "1",
        session,
        username,
        password,
        auto_sync=0,
        wait=False,
        resource_pool_manager=RESOURCE_POOL_MANAGER,
    )
    assert str(lab) == "Lab: laboratory"
    assert repr(lab) == "Lab('1', 'laboratory', '/')"


def test_create_node():
    session = MagicMock()
    username = password = "test"
    lab = Lab(
        "laboratory",
        "1",
        session,
        username,
        password,
        auto_sync=0,
        wait=False,
        resource_pool_manager=RESOURCE_POOL_MANAGER,
    )
    node = lab.create_node("testnode", "server")
    assert node.node_definition == "server"
    assert node.label == "testnode"
    assert node.compute_id is None  # None until we start the node.


@pytest.mark.parametrize("connect_two_nodes", [True, False])
def test_create_link(respx_mock, connect_two_nodes):
    respx_mock.post("mock://mock/labs/1/nodes").respond(json={"id": "n0"})
    respx_mock.post("mock://mock/labs/1/interfaces").respond(
        json={"id": "i0", "label": "eth0", "slot": 0}
    )
    respx_mock.post("mock://mock/labs/1/links").respond(
        json={"id": "l0", "label": "segment0"}
    )
    session = make_session("mock://mock")
    session.lock = MagicMock()
    username = password = "test"
    lab = Lab(
        "laboratory",
        "1",
        session,
        username,
        password,
        auto_sync=0,
        wait=False,
        resource_pool_manager=RESOURCE_POOL_MANAGER,
    )
    node1 = lab.create_node("testnode", "server")
    node2 = lab.create_node("testnode", "server")
    if connect_two_nodes:
        link = lab.connect_two_nodes(node1, node2)
    else:
        node1_i1 = node1.create_interface()
        assert isinstance(node1_i1, Interface)
        node2_i1 = node2.create_interface()
        link = lab.create_link(node1_i1, node2_i1)

    assert link.as_dict() == {"id": "l0", "interface_a": "i0", "interface_b": "i0"}
    assert link.nodes[0].label == "testnode"
    assert link.nodes[1].label == "testnode"
    assert link.statistics == {
        "readbytes": 0,
        "readpackets": 0,
        "writebytes": 0,
        "writepackets": 0,
    }
    assert link.id == "l0"
    respx_mock.assert_all_called()


def test_sync_stats(respx_mock):
    respx_mock.get("mock://mock/labs/1/simulation_stats").respond(
        json={"nodes": {}, "links": {}}
    )
    session = make_session("mock://mock")
    session.lock = MagicMock()
    username = password = "test"
    lab = Lab(
        "laboratory",
        "1",
        session,
        username,
        password,
        auto_sync=0,
        wait=False,
        resource_pool_manager=RESOURCE_POOL_MANAGER,
    )
    lab.sync_statistics()
    respx_mock.assert_all_called()


def test_tags():
    session = MagicMock()
    username = password = "test"
    lab = Lab(
        "laboratory",
        "1",
        session,
        username,
        password,
        auto_sync=0,
        resource_pool_manager=RESOURCE_POOL_MANAGER,
    )
    lab.get_smart_annotation_by_tag = MagicMock()
    node_a = lab._create_node_local("0", "node A", "nd")
    node_b = lab._create_node_local("1", "node B", "nd")
    node_c = lab._create_node_local("2", "node C", "nd")
    node_d = lab._create_node_local("3", "node D", "nd")
    assert len(node_a.tags()) == 0
    node_a.add_tag("Core")
    node_a.add_tag("Europe")
    node_a.add_tag("Test")
    assert len(node_a.tags()) == 3
    node_a.add_tag("Europe")
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
    session = MagicMock()
    username = password = "test"
    lab = Lab(
        "laboratory",
        "1",
        session,
        username,
        password,
        auto_sync=0,
        resource_pool_manager=RESOURCE_POOL_MANAGER,
    )

    lab._create_node_local("n0", "server-a", "nd")
    lab._create_node_local("n1", "server-b", "nd")
    lab._create_node_local("n2", "server-c", "nd")
    lab._create_node_local("n3", "server-d", "nd")

    node = lab.get_node_by_label("server-a")
    assert node.id == "n0"

    with pytest.raises(NodeNotFound):
        node = lab.get_node_by_label("does-not-exist")
        assert node is None


def test_next_free_interface():
    session = MagicMock()
    username = password = "test"
    lab = Lab(
        "laboratory",
        "1",
        session,
        username,
        password,
        auto_sync=0,
        resource_pool_manager=RESOURCE_POOL_MANAGER,
    )
    node_a = lab._create_node_local("0", "node A", "nd")
    node_b = lab._create_node_local("1", "node B", "nd")

    nf = node_a.next_available_interface()
    assert nf is None

    i1 = lab._create_interface_local("0", "iface 0", node_a, 0)
    nf = node_a.next_available_interface()
    assert i1 == nf

    i2 = lab._create_interface_local("4", "iface 4", node_b, 1)
    lab._create_link_local(i1, i2, "0")

    nf = node_a.next_available_interface()
    assert nf is None


def test_join_existing_lab(client_library):
    lab = client_library.join_existing_lab("444a78d1-575c-4746-8469-696e580f17b6")
    assert lab.title == "IOSv Feature Tests"
    assert lab.statistics == {
        "annotations": 0,
        "nodes": 7,
        "links": 8,
        "interfaces": 24,
        "smart_annotations": 0,
    }


def test_all_labs(client_library):
    all_labs = client_library.all_labs()
    assert len(all_labs) == 4
    iosv_labs = client_library.find_labs_by_title("IOSv Feature Tests")
    assert len(iosv_labs) == 1
    lab: Lab = iosv_labs[0]
    node = lab.get_node_by_label("csr1000v-0")
    assert node.compute_id == "99c887f5-052e-4864-a583-49fa7c4b68a9"


def test_sync_interfaces_operational(respx_mock):
    """Test Lab.sync_interfaces_operational() uses new bulk endpoint."""
    respx_mock.get("mock://mock/labs/1/interfaces").respond(
        json=[{"id": "iface1", "operational": {"mac_address": "aa:bb:cc:dd:ee:ff"}}]
    )
    session = make_session("mock://mock")
    session.lock = MagicMock()
    lab = Lab(
        "test",
        "1",
        session,
        "user",
        "pass",
        auto_sync=0,
        resource_pool_manager=RESOURCE_POOL_MANAGER,
    )
    lab._interfaces = {"iface1": MagicMock()}

    lab.sync_interfaces_operational()

    respx_mock.assert_all_called()
    assert lab._interfaces["iface1"]._operational == {
        "mac_address": "aa:bb:cc:dd:ee:ff"
    }


def test_lab_clear_discovered_addresses(respx_mock):
    """Test Lab.clear_discovered_addresses() calls backend API."""
    respx_mock.delete("mock://mock/labs/1/layer3_addresses").respond(status_code=204)
    session = make_session("mock://mock")
    session.lock = MagicMock()
    lab = Lab(
        "test",
        "1",
        session,
        "user",
        "pass",
        auto_sync=False,
        resource_pool_manager=RESOURCE_POOL_MANAGER,
    )

    lab.clear_discovered_addresses()

    respx_mock.assert_all_called()


def test_node_clear_discovered_addresses(respx_mock):
    """Test Node.clear_discovered_addresses() calls backend API."""
    respx_mock.delete("mock://mock/labs/1/nodes/n1/layer3_addresses").respond(
        status_code=204
    )
    session = make_session("mock://mock")
    session.lock = MagicMock()
    lab = Lab(
        "test",
        "1",
        session,
        "user",
        "pass",
        auto_sync=False,
        resource_pool_manager=RESOURCE_POOL_MANAGER,
    )
    from virl2_client.models.node import Node

    node = Node(lab, "n1", "test", "iosv")

    node.clear_discovered_addresses()

    respx_mock.assert_all_called()
