#
# This file is part of VIRL 2
# Copyright (c) 2019-2026, Cisco Systems, Inc.
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
"""Interface-focused unit tests for interface operations and properties."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from tests.helpers import RESOURCE_POOL_MANAGER, USER_MANAGEMENT, make_lab
from virl2_client.exceptions import InterfaceNotFound
from virl2_client.models import Interface, Lab, Node
from virl2_client.models.authentication import make_session

if TYPE_CHECKING:
    from respx import MockRouter


def test_create_interface_raises_slot_missing() -> None:
    """Raise InterfaceNotFound when the requested slot is not returned by the API.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    session.post.return_value.json.return_value = [
        {"id": "i0", "label": "eth0", "slot": 0}
    ]
    lab = Lab(
        "test",
        "1",
        session,
        "user",
        "pass",
        auto_sync=False,
        resource_pool_manager=RESOURCE_POOL_MANAGER,
        user_management=USER_MANAGEMENT,
    )
    node = lab._create_node_local("n1", "n1", "iosv")
    with pytest.raises(InterfaceNotFound):
        lab.create_interface(node, slot=1, wait=False)


def test_node_clear_discovered_addresses(respx_mock: MockRouter) -> None:
    """Clear node-level discovered addresses and reset interface snooped data.

    NOTE: LLM-generated test -- verify for correctness.

    :param respx_mock: HTTPX router fixture used to mock API requests.
    """
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
        user_management=USER_MANAGEMENT,
    )
    node = Node(lab, "n1", "test", "iosv")
    interface1 = Interface("if1", node, "eth0", 0)
    interface1._ip_snooped_info = {
        "ipv4": ["192.168.1.1/24", "10.0.0.1/8"],
        "ipv6": [],
        "mac_address": None,
    }
    interface2 = Interface("if2", node, "eth1", 1)
    interface2._ip_snooped_info = {
        "ipv4": ["192.168.2.1/24"],
        "ipv6": [],
        "mac_address": None,
    }
    lab._interfaces = {"if1": interface1, "if2": interface2}
    lab._nodes = {"n1": node}
    node.clear_discovered_addresses()
    assert interface1.discovered_ipv4 is None
    assert interface2.discovered_ipv4 is None
    assert interface1.discovered_ipv6 is None
    assert interface2.discovered_ipv6 is None
    assert interface1.discovered_mac_address is None
    assert interface2.discovered_mac_address is None


def test_interface_property_setters() -> None:
    """mac_address setter, connected, peer_interface, peer_node.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    node = lab._create_node_local("n1", "node1", "iosv")
    interface = lab._create_interface_local("if1", "eth0", node, 0)
    peer = lab._create_interface_local("if2", "eth1", node, 1)
    lab._create_link_local(interface, peer, "l1")
    interface._operational = {"mac_address": "aa:bb"}
    interface._ip_snooped_info = {
        "mac_address": "aa:bb",
        "ipv4": ["1.1.1.1/24"],
        "ipv6": ["::1/128"],
    }

    with patch.object(interface, "_set_interface_property", return_value=None):
        interface.mac_address = "00:11:22:33:44:55"
    assert interface.mac_address == "00:11:22:33:44:55"
    assert interface.connected is True
    assert interface.peer_interface is peer
    assert interface.peer_node is node
    assert interface.discovered_mac_address == "aa:bb"
    assert interface.discovered_ipv4 == ["1.1.1.1/24"]
    assert interface.discovered_ipv6 == ["::1/128"]
    assert interface.deployed_mac_address == "aa:bb"
    assert interface.operational == {"mac_address": "aa:bb"}


def test_interface_statistics() -> None:
    """readbytes, readpackets, writebytes, writepackets.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    node = lab._create_node_local("n1", "node1", "iosv")
    interface = lab._create_interface_local("if1", "eth0", node, 0)
    interface.statistics = {
        "readbytes": 1,
        "readpackets": 2,
        "writebytes": 3,
        "writepackets": 4,
    }
    assert interface.readbytes == 1
    assert interface.readpackets == 2
    assert interface.writebytes == 3
    assert interface.writepackets == 4


def test_interface_discovered_and_state() -> None:
    """discovered/operational props, state.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    node = lab._create_node_local("n1", "node1", "iosv")
    interface = lab._create_interface_local("if1", "eth0", node, 0)
    interface._operational = {"mac_address": "aa:bb"}
    interface._session.get.return_value.json.return_value = {"state": "up"}
    assert interface.state == "up"


def test_interface_as_dict_get_link() -> None:
    """as_dict, get_link_to.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    node = lab._create_node_local("n1", "node1", "iosv")
    interface = lab._create_interface_local("if1", "eth0", node, 0)
    peer = lab._create_interface_local("if2", "eth1", node, 1)
    lab._create_link_local(interface, peer, "l1")
    assert interface.as_dict()["id"] == "if1"
    assert interface.get_link_to(peer) is not None


def test_interface_lifecycle_methods() -> None:
    """bring_up, shutdown, _remove_on_server, remove.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    node = lab._create_node_local("n1", "node1", "iosv")
    interface = lab._create_interface_local("if1", "eth0", node, 0)
    interface.bring_up()
    interface.shutdown()
    interface._remove_on_server()
    interface.remove()


def test_interface_slot_defaults_to_none() -> None:
    """Interface.slot defaults to None when omitted."""
    lab = make_lab()
    node = lab._create_node_local("n1", "node1", "iosv")
    iface = Interface("if1", node, "eth0")
    assert iface._slot is None

    iface_local = lab._create_interface_local("if2", "eth1", node)
    assert iface_local._slot is None


def test_interface_identity() -> None:
    """eq with non-Interface, repr, hash.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    node = lab._create_node_local("n1", "node1", "iosv")
    interface = lab._create_interface_local("if1", "eth0", node, 0)
    assert (interface == object()) is False
    assert "Interface(" in repr(interface)
    assert "Interface:" in str(interface)
    assert hash(interface) == hash(interface.id)


def test_interface_unconnected_state() -> None:
    """peer_interface when unconnected, get_link_to when no link, ip_snooped_info.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    node = lab._create_node_local("n1", "node1", "iosv")
    interface = lab._create_interface_local("if1", "eth0", node, 0)
    other = Interface("if2", node, "eth1", 1)
    assert interface.peer_interface is None
    assert interface.get_link_to(other) is None
    assert interface.ip_snooped_info == {
        "mac_address": None,
        "ipv4": None,
        "ipv6": None,
    }


def test_interface_update_push() -> None:
    """_update with push_to_server calls _set_interface_properties.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    node = lab._create_node_local("n1", "node1", "iosv")
    interface = lab._create_interface_local("if1", "eth0", node, 0)
    with patch.object(interface, "_set_interface_properties") as set_props:
        interface._update({"data": {"label": "ethX"}}, push_to_server=True)
        set_props.assert_called_once()
    assert interface.label == "ethX"


def test_interface_update_preserves_id() -> None:
    """_update must not overwrite interface ID.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    node = lab._create_node_local("n1", "node1", "iosv")
    interface = lab._create_interface_local("if1", "eth0", node, 0)
    interface._update({"id": "changed", "label": "ethX"}, push_to_server=False)
    assert interface.id == "if1"
    assert interface.label == "ethX"


def test_interface_set_prop_patches() -> None:
    """_set_interface_property triggers PATCH.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    node = lab._create_node_local("n1", "node1", "iosv")
    interface = lab._create_interface_local("if1", "eth0", node, 0)
    interface._set_interface_property("mac_address", "aa:bb")
    interface._session.patch.assert_called_with(
        "labs/l1/interfaces/if1", json={"mac_address": "aa:bb"}
    )
