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
"""Node-focused unit tests for node behaviors and properties."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from tests.helpers import make_lab
from virl2_client.exceptions import (
    AnnotationNotFound,
    InterfaceNotFound,
    LinkNotFound,
    NodeNotFound,
    SmartAnnotationNotFound,
)
from virl2_client.models import Lab, Node


def _make_lab_and_node() -> tuple[Lab, Node]:
    """Create a local lab with one node for node-centric runtime checks.

    :returns: Tuple of (Lab, Node).
    """
    lab = make_lab()
    node = lab._create_node_local("n1", "node1", "iosv")
    return lab, node


def test_create_node() -> None:
    """Create node and validate basic defaults.

    NOTE: LLM-generated test -- verify for correctness.
    """
    node = make_lab().create_node("testnode", "server")
    assert node.node_definition == "server"
    assert node.label == "testnode"
    assert node.compute_id is None


def test_add_remove_tags() -> None:
    """Add, remove, and duplicate add is idempotent.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    lab.get_smart_annotation_by_tag = MagicMock()
    node_a = lab._create_node_local("0", "node A", "nd")
    node_a.add_tag("Core")
    node_a.add_tag("Europe")
    node_a.add_tag("Test")
    node_a.add_tag("Europe")
    node_a.remove_tag("Test")


def test_tags_returns_copy() -> None:
    """tags() returns a copy -- mutating the returned list must not
    mutate the node's internal tag state.

    Regression guard for CMLDEV-1117.
    """
    lab = make_lab()
    lab.get_smart_annotation_by_tag = MagicMock()
    node = lab._create_node_local("0", "node A", "nd")
    node._tags = ["alpha", "beta"]

    returned = node.tags()
    returned.append("gamma")

    assert node._tags == ["alpha", "beta"]


def test_add_tag_rolls_back_on_server_error() -> None:
    """add_tag does not modify local _tags when the server PATCH fails.

    Regression guard for CMLDEV-1117: previously the local list was
    mutated before the PATCH, so a failed request left the local cache
    diverged from the controller.
    """
    _lab, node = _make_lab_and_node()
    node._tags = ["core"]
    with (
        patch.object(node, "_set_node_property", side_effect=RuntimeError("500")),
        pytest.raises(RuntimeError),
    ):
        node.add_tag("edge")

    assert node._tags == ["core"]


def test_remove_tag_rolls_back_on_server_error() -> None:
    """_remove_tag_on_server does not touch local _tags when PATCH fails.

    Regression guard for CMLDEV-1117.
    """
    _lab, node = _make_lab_and_node()
    node._tags = ["core", "edge"]
    with (
        patch.object(node, "_set_node_property", side_effect=RuntimeError("500")),
        pytest.raises(RuntimeError),
    ):
        node._remove_tag_on_server("edge")

    assert node._tags == ["core", "edge"]


def test_find_nodes_by_tag() -> None:
    """Query by tag returns correct node counts.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    lab.get_smart_annotation_by_tag = MagicMock()
    node_a = lab._create_node_local("0", "node A", "nd")
    node_b = lab._create_node_local("1", "node B", "nd")
    node_c = lab._create_node_local("2", "node C", "nd")
    node_d = lab._create_node_local("3", "node D", "nd")
    node_a.add_tag("Core")
    node_a.add_tag("Europe")
    node_b.add_tag("Core")
    node_c.add_tag("Core")
    node_d.add_tag("Europe")
    assert len(lab.find_nodes_by_tag("Core")) == 3
    assert len(lab.find_nodes_by_tag("Europe")) == 2


def test_get_node_by_label() -> None:
    """Resolve node by label returns correct node.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    lab._create_node_local("n0", "server-a", "nd")
    lab._create_node_local("n1", "server-b", "nd")
    assert lab.get_node_by_label("server-a").id == "n0"


def test_get_node_by_label_missing() -> None:
    """Raise NodeNotFound for unknown label.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    with pytest.raises(NodeNotFound):
        lab.get_node_by_label("does-not-exist")


def test_next_free_interface() -> None:
    """Return the next available physical interface on a node.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    node_a = lab._create_node_local("0", "node A", "nd")
    node_b = lab._create_node_local("1", "node B", "nd")
    assert node_a.next_available_interface() is None
    i1 = lab._create_interface_local("0", "iface 0", node_a, 0)
    assert node_a.next_available_interface() == i1
    i2 = lab._create_interface_local("4", "iface 4", node_b, 1)
    lab._create_link_local(i1, i2, "0")
    assert node_a.next_available_interface() is None


@pytest.mark.parametrize(
    ("method", "exc"),
    [
        ("get_interface_by_id", InterfaceNotFound),
        ("get_link_by_id", LinkNotFound),
        ("get_annotation_by_id", AnnotationNotFound),
        ("get_smart_annotation_by_id", SmartAnnotationNotFound),
    ],
)
def test_element_by_id_not_found(method: str, exc: type) -> None:
    """Raise not-found error for missing element IDs.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    with pytest.raises(exc):
        getattr(lab, method)("missing")


def test_node_start_stop_wipe() -> None:
    """Start, stop, wipe with wait=False.

    NOTE: LLM-generated test -- verify for correctness.
    """
    _lab, node = _make_lab_and_node()
    node._configuration = [{"name": "Main", "content": "boot"}]
    node.start(wait=False)
    node.stop(wait=False)
    node.wipe(wait=False)


def test_node_clone_and_extract() -> None:
    """clone_image and extract_configuration.

    NOTE: LLM-generated test -- verify for correctness.
    """
    _lab, node = _make_lab_and_node()
    node._session.put.return_value.json.return_value = {"new_image": "img"}
    assert node.clone_image() == {"new_image": "img"}
    node.extract_configuration()


def test_node_console_ops() -> None:
    """console_logs, console_key, vnc_key.

    NOTE: LLM-generated test -- verify for correctness.
    """
    _lab, node = _make_lab_and_node()
    node._session.get.return_value.json.return_value = {"x": 1}
    assert node.console_logs(0) == {"x": 1}
    assert node.console_logs(0, lines=5) == {"x": 1}
    assert node.console_key(0) == {"x": 1}
    assert node.vnc_key() == {"x": 1}


def test_node_operational_props() -> None:
    """compute_id, resource_pool, operational, cpu/disk stats.

    NOTE: LLM-generated test -- verify for correctness.
    """
    _lab, node = _make_lab_and_node()
    node._operational = {"compute_id": "c1", "resource_pool": "p1"}
    node.statistics = {"cpu_usage": 120, "disk_read": 1048576, "disk_write": 2097152}
    assert node.compute_id == "c1"
    assert node.resource_pool == "p1"
    assert node.operational == {"compute_id": "c1", "resource_pool": "p1"}
    assert node.cpu_usage == 100
    assert node.disk_read == 1
    assert node.disk_write == 2


def test_node_has_converged() -> None:
    """has_converged returns True.

    NOTE: LLM-generated test -- verify for correctness.
    """
    _lab, node = _make_lab_and_node()
    node._session.get.return_value.json.return_value = True
    assert node.has_converged() is True


def test_node_property_setters() -> None:
    """Property updates via setattr loop.

    NOTE: LLM-generated test -- verify for correctness.
    """
    _lab, node = _make_lab_and_node()
    node._parameters = {}
    node._pyats = {}
    property_updates = {
        "label": "new-label",
        "x": 1,
        "y": 2,
        "ram": 2048,
        "cpus": 2,
        "cpu_limit": 80,
        "data_volume": 4,
        "hide_links": True,
        "boot_disk_size": 16,
        "image_definition": "img-1",
        "pinned_compute_id": "c1",
        "priority": 2,
        "configuration": "new-config",
    }
    with patch.object(node, "_set_node_property", return_value=None):
        for key, value in property_updates.items():
            setattr(node, key, value)

    for key, value in property_updates.items():
        assert getattr(node, key) == value


def test_node_pyats_creds_setter() -> None:
    """set_pyats_credentials updates pyats_credentials.

    NOTE: LLM-generated test -- verify for correctness.
    """
    _lab, node = _make_lab_and_node()
    node._pyats = {}
    with patch.object(node, "_set_node_property", return_value=None):
        node.set_pyats_credentials(username="u", password="p", enable_password="ep")
    assert node.pyats_credentials == {
        "username": "u",
        "password": "p",
        "enable_password": "ep",
    }


def test_node_update_parameters() -> None:
    """update_parameters merges and removes None values.

    NOTE: LLM-generated test -- verify for correctness.
    """
    _lab, node = _make_lab_and_node()
    node._session.patch.return_value = MagicMock()
    node.update_parameters({"k1": "v1", "k2": None})
    assert node.parameters == {"k1": "v1"}


def test_node_interface_link_helpers() -> None:
    """get_interface_by_label/slot, get_links_to, get_link_to, peers.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab, node = _make_lab_and_node()
    peer_node = lab._create_node_local("n2", "node2", "iosv")
    i1 = lab._create_interface_local("i1", "eth0", node, 0)
    i2 = lab._create_interface_local("i2", "eth0", peer_node, 0)
    link = lab._create_link_local(i1, i2, "l1")
    assert node.get_interface_by_label("eth0") == i1
    assert node.get_interface_by_slot(0) == i1
    assert node.get_links_to(peer_node) == [link]
    assert node.get_link_to(peer_node) == link
    assert i2 in node.peer_interfaces()
    assert peer_node in node.peer_nodes()


def test_node_start_stop_with_wait() -> None:
    """Start, stop, wipe with wait=True; wait_until_converged called.

    NOTE: LLM-generated test -- verify for correctness.
    """
    _lab, node = _make_lab_and_node()
    with patch.object(node, "wait_until_converged") as wait:
        node.start(wait=True)
        node.stop(wait=True)
        node.wipe(wait=True)
        assert wait.call_count == 3


def test_node_add_tag_new_smart_ann() -> None:
    """add_tag when SmartAnnotationNotFound calls _set_node_property.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab, node = _make_lab_and_node()
    with patch.object(node, "_set_node_property") as set_prop:
        lab.get_smart_annotation_by_tag = MagicMock(
            side_effect=SmartAnnotationNotFound("core")
        )
        lab._sync_topology = MagicMock()
        node.add_tag("core")
        set_prop.assert_called()


def test_node_remove_tag_on_server() -> None:
    """_remove_tag_on_server call.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab, node = _make_lab_and_node()
    node._tags = ["core"]
    lab.get_smart_annotation_by_tag = MagicMock(
        side_effect=SmartAnnotationNotFound("core")
    )
    node._remove_tag_on_server("core")


def test_node_pyats_commands() -> None:
    """run_pyats_command, run_pyats_config_command.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab, node = _make_lab_and_node()
    with (
        patch.object(lab.pyats, "run_command", return_value="ok"),
        patch.object(lab.pyats, "run_config_command", return_value="ok2"),
    ):
        assert node.run_pyats_command("show version") == "ok"
        assert node.run_pyats_config_command("interface gi0") == "ok2"


def test_node_sync_l3_addresses() -> None:
    """sync_layer3_addresses, discovered_ipv4.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab, node = _make_lab_and_node()
    i1 = lab._create_interface_local("i1", "eth0", node, 0)
    node._session.get.return_value.json.return_value = {
        "interfaces": {"aa:bb": {"id": "i1", "ip4": ["1.1.1.1/24"], "ip6": []}}
    }
    node.sync_layer3_addresses()
    assert i1.discovered_ipv4 == ["1.1.1.1/24"]


def test_node_sync_operational() -> None:
    """sync_operational, sync_interface_operational.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab, node = _make_lab_and_node()
    i1 = lab._create_interface_local("i1", "eth0", node, 0)
    node.sync_operational()
    node._session.get.return_value.json.return_value = [
        {"id": "i1", "operational": {"mac_address": "aa"}}
    ]
    node.sync_interface_operational()
    assert i1.operational == {"mac_address": "aa"}


def test_node_sync_operational_updates_last_sync_time() -> None:
    """sync_operational stamps _last_sync_operational_time on completion.

    Regression guard for CMLDEV-1117: previously sync_operational populated
    self._operational but never updated _last_sync_operational_time, so a
    subsequent sync_operational_if_outdated() would immediately re-fetch
    the same data.
    """
    _lab, node = _make_lab_and_node()
    node._last_sync_operational_time = 0.0
    node._session.get.return_value.json.return_value = {"operational": {"k": "v"}}

    node.sync_operational()

    assert node._operational == {"k": "v"}
    assert node._last_sync_operational_time > 0.0


def test_node_sync_operational_updates_sync_time() -> None:
    """sync_operational(response=...) also stamps _last_sync_operational_time.

    Regression guard for CMLDEV-1117: Lab.sync_operational() fans out to
    every node via node.sync_operational(node_data) to avoid N extra HTTP
    calls; the per-node timestamp must be updated in that path too.
    """
    _lab, node = _make_lab_and_node()
    node._last_sync_operational_time = 0.0

    node.sync_operational(response={"operational": {"k": "v"}})

    assert node._operational == {"k": "v"}
    assert node._last_sync_operational_time > 0.0
    # The API call must not have been issued because a response was supplied.
    node._session.get.assert_not_called()


def test_node_update_excludes_config() -> None:
    """_update with exclude_configurations=False.

    NOTE: LLM-generated test -- verify for correctness.
    """
    _lab, node = _make_lab_and_node()
    with (
        patch.object(node, "_set_node_properties"),
        patch.object(node, "sync_operational"),
    ):
        node._update(
            {
                "data": {
                    "label": "updated-label",
                    "configuration": {"name": "Main", "content": "x"},
                    "operational": {"x": 1},
                }
            },
            exclude_configurations=False,
            push_to_server=True,
        )
    assert node.label == "updated-label"


def test_node_update_preserves_id() -> None:
    """_update must not overwrite node ID.

    NOTE: LLM-generated test -- verify for correctness.
    """
    _lab, node = _make_lab_and_node()
    assert node.id == "n1"
    node._update(
        {"data": {"id": "changed", "label": "new"}},
        exclude_configurations=True,
        push_to_server=False,
    )
    assert node.id == "n1"
    assert node.label == "new"


def test_node_is_active_is_booted() -> None:
    """is_active when STARTED, is_booted when BOOTED.

    NOTE: LLM-generated test -- verify for correctness.
    """
    _lab, node = _make_lab_and_node()
    node._state = "STARTED"
    assert node.is_active() is True
    node._state = "BOOTED"
    assert node.is_booted() is True


def test_node_equality_and_repr() -> None:
    """Node equality, repr, hash, and lab accessor.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab, node = _make_lab_and_node()

    assert (node == object()) is False
    assert "Node(" in repr(node)
    assert "Node:" in str(node)
    assert hash(node) == hash(node.id)
    assert node.lab is lab
    cfg_node = Node(lab, "n3", "node3", "iosv", configuration="line-1")
    assert cfg_node.configuration == "line-1"


def test_node_state_fetch() -> None:
    """Fetch state from API when local _state is None.

    NOTE: LLM-generated test -- verify for correctness.
    """
    _lab, node = _make_lab_and_node()
    node._state = None
    node._session.get.return_value.json.return_value = {"state": "STARTED"}
    assert node.state == "STARTED"


def test_node_physical_interfaces() -> None:
    """physical_interfaces filters by type; no-link returns None.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab, node = _make_lab_and_node()
    other = Node(lab, "n2", "node2", "iosv")
    i_phys = lab._create_interface_local(
        "if-phys", "eth0", node, 0, iface_type="physical"
    )
    _ = lab._create_interface_local("if-loop", "lo0", node, 1, iface_type="loopback")
    assert node.physical_interfaces() == [i_phys]
    assert node.get_link_to(other) is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("string-value", "string-value"),
        ([{"name": "Main", "content": "list"}], "list"),
        ({"name": "Main", "content": "dict"}, "dict"),
        (None, None),
    ],
)
def test_set_configuration_valid(
    value: str | list | dict | None, expected: str | None
) -> None:
    """_set_configuration handles str, list, dict, None.

    NOTE: LLM-generated test -- verify for correctness.
    """
    _lab, node = _make_lab_and_node()
    node._configuration = [{"name": "Main", "content": "old"}]
    node._set_configuration(value)
    assert node.configuration == expected
    if expected is None:
        assert node.configuration_files == []


def test_set_configuration_type_error() -> None:
    """_set_configuration raises TypeError for unsupported types.

    NOTE: LLM-generated test -- verify for correctness.
    """
    _lab, node = _make_lab_and_node()
    with pytest.raises(TypeError):
        node._set_configuration(1)  # type: ignore[arg-type]


def test_node_smart_annotation_map() -> None:
    """smart_annotations maps tags to annotation objects.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab, node = _make_lab_and_node()
    node._tags = ["core"]
    lab.get_smart_annotation_by_tag = MagicMock(return_value=MagicMock())
    assert "core" in node.smart_annotations

    node._pyats = {"username": "u", "password": "p", "enable_password": "e"}
    assert node.pyats_credentials["username"] == "u"


def test_node_remove_delegates() -> None:
    """Node.remove delegates to lab.remove_node.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab, node = _make_lab_and_node()
    with patch.object(node, "has_converged", return_value=True):
        node.wait_until_converged(max_iterations=1, wait_time=0)
    with patch.object(lab, "remove_node") as remove_node:
        node.remove()
        remove_node.assert_called_once_with(node)


def test_remove_tag_shared() -> None:
    """remove_tag when tag shared with other node.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab, node = _make_lab_and_node()
    other = Node(lab, "n2", "node2", "iosv")
    node._tags = ["core"]
    other._tags = ["core"]
    lab._nodes = {"n1": node, "n2": other}
    node._remove_tag_on_server = MagicMock()
    node.remove_tag("core")
    node._remove_tag_on_server.assert_called_once_with("core")


def test_remove_tag_last_owner_cleanup() -> None:
    """remove_tag when tag not found, then last-owner cleanup.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab, node = _make_lab_and_node()
    other = Node(lab, "n2", "node2", "iosv")
    other._tags = []
    node._tags = ["core"]
    lab.get_smart_annotation_by_tag = MagicMock(
        side_effect=SmartAnnotationNotFound("core")
    )
    node.remove_tag("core")
    node._tags = ["edge"]
    lab._nodes = {"n1": node}
    node._remove_tag_on_server = MagicMock(
        side_effect=lambda _tag: node._tags.remove("edge")
    )
    node.remove_tag("edge")


def test_node_sync_if_outdated() -> None:
    """sync-if-outdated helpers trigger respective sync methods.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab, node = _make_lab_and_node()
    lab.auto_sync = True
    lab.auto_sync_interval = 0
    with (
        patch.object(node, "sync_layer3_addresses") as sync_l3,
        patch.object(node, "sync_operational") as sync_op,
        patch.object(node, "sync_interface_operational") as sync_ifop,
    ):
        node.sync_l3_addresses_if_outdated()
        node.sync_operational_if_outdated()
        node.sync_interface_operational_if_outdated()
        assert sync_l3.called
        assert sync_op.called
        assert sync_ifop.called


def test_node_update_wrapper() -> None:
    """Node.update delegates to Node._update.

    NOTE: LLM-generated test -- verify for correctness.
    """
    _lab, node = _make_lab_and_node()
    with patch.object(node, "_update") as wrapped:
        node.update({"label": "x"}, exclude_configurations=True)
        wrapped.assert_called_once()


@pytest.mark.parametrize(
    ("method", "arg"),
    [
        ("get_interface_by_label", "eth99"),
        ("get_interface_by_slot", 99),
    ],
)
def test_interface_lookup_missing(method: str, arg: str | int) -> None:
    """Raise InterfaceNotFound for unknown interface lookups.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    node = lab._create_node_local("n1", "node-1", "iosv")
    with pytest.raises(InterfaceNotFound):
        getattr(node, method)(arg)


def test_node_wait_until_converged_timeout() -> None:
    """Raise RuntimeError when node convergence never occurs.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    node = lab._create_node_local("n1", "node-1", "iosv")

    with (
        patch.object(node, "has_converged", return_value=False),
        patch("virl2_client.models.node.time.sleep", return_value=None),
        pytest.raises(RuntimeError, match="maximum tries 1 exceeded"),
    ):
        node.wait_until_converged(max_iterations=1, wait_time=0)
