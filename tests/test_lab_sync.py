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

"""Lab topology sync, import handlers, and L3 address sync tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest
from helpers import make_lab

from virl2_client.exceptions import (
    ElementAlreadyExists,
    LabNotFound,
    SmartAnnotationNotFound,
)


def test_sync_topology_import_path() -> None:
    """_sync_topology calls import_lab when not initialized.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    topology = {
        "lab": {"title": "T", "description": "D", "notes": "N", "owner": None},
        "nodes": [],
        "links": [],
        "annotations": [],
        "smart_annotations": [],
    }
    lab._initialized = False
    lab._session.get.return_value = MagicMock(json=MagicMock(return_value=topology))
    with patch.object(lab, "import_lab") as import_lab:
        lab._sync_topology()
        import_lab.assert_called_once()
        assert lab._initialized is True


def test_sync_topology_update_path() -> None:
    """_sync_topology calls update_lab when initialized.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    topology = {
        "lab": {"title": "T", "description": "D", "notes": "N", "owner": None},
        "nodes": [],
        "links": [],
        "annotations": [],
        "smart_annotations": [],
    }
    lab._initialized = True
    lab._session.get.return_value = MagicMock(json=MagicMock(return_value=topology))
    with patch.object(lab, "update_lab") as update_lab_mock:
        lab._sync_topology()
        update_lab_mock.assert_called_once()


def test_sync_topology_404() -> None:
    """_sync_topology raises LabNotFound on 404 and marks stale.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    not_found = httpx.HTTPStatusError(
        "404",
        request=httpx.Request("GET", "https://x"),
        response=httpx.Response(status_code=404, text="Lab not found: l1"),
    )
    lab._session.get.side_effect = not_found
    with pytest.raises(LabNotFound):
        lab._sync_topology()
    assert lab._stale is True


def test_sync_topology_500() -> None:
    """_sync_topology raises HTTPStatusError on 500.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    generic = httpx.HTTPStatusError(
        "500",
        request=httpx.Request("GET", "https://x"),
        response=httpx.Response(status_code=500, text="boom"),
    )
    lab._session.get.side_effect = generic
    with pytest.raises(httpx.HTTPStatusError):
        lab._sync_topology()


def test_import_old_schema() -> None:
    """_import_lab handles old schema path for created labs.

    NOTE: LLM-generated test -- verify for correctness.
    """
    user_mgmt = MagicMock()
    user_mgmt.get_user.return_value = {"username": "owner-1"}
    lab = make_lab(user_management=user_mgmt)
    old_schema = {
        "lab_title": "created",
        "lab_description": "desc",
        "lab_notes": "notes",
        "lab_owner": "u1",
        "autostart": {"enabled": True, "priority": 1, "delay": 0},
        "node_staging": {
            "enabled": True,
            "start_remaining": False,
            "abort_on_failure": True,
        },
    }
    lab._import_lab(old_schema, created=True)
    assert lab.title == "created"
    assert lab.owner == "owner-1"
    assert lab.owner_id == "u1"
    assert lab.autostart["enabled"] is True
    assert lab.node_staging["enabled"] is True
    user_mgmt.get_user.assert_called_once_with("u1")


def test_owner_fallback() -> None:
    """Owner fallback when user id not resolved.

    NOTE: LLM-generated test -- verify for correctness.
    """
    user_mgmt = MagicMock()
    user_mgmt.get_user.side_effect = Exception("User not found")
    lab = make_lab(user_management=user_mgmt)
    lab._set_owner(user_id="missing", user_name="fallback")
    assert lab.owner == "fallback"
    assert lab.owner_id == "missing"


@pytest.mark.parametrize(
    "method,sync_target,last_time_attr",
    [
        (
            "sync_statistics_if_outdated",
            "sync_statistics",
            "_last_sync_statistics_time",
        ),
        ("sync_states_if_outdated", "sync_states", "_last_sync_state_time"),
        (
            "sync_l3_addresses_if_outdated",
            "sync_layer3_addresses",
            "_last_sync_l3_address_time",
        ),
    ],
)
def test_sync_outdated_triggers(
    method: str, sync_target: str, last_time_attr: str
) -> None:
    """sync_*_if_outdated delegates when auto-sync interval has elapsed.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    lab.auto_sync = True
    lab.auto_sync_interval = 0
    setattr(lab, last_time_attr, 0.0)
    with (
        patch.object(lab, sync_target) as sync_mock,
        patch("virl2_client.models.lab.time.time", return_value=10.0),
    ):
        getattr(lab, method)()
        sync_mock.assert_called_once()


def test_topology_sync_stale_configs() -> None:
    """Force topology sync when configs are stale, regardless of timer.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    lab._synced_configs = False
    with patch.object(lab, "_sync_topology") as sync_topology:
        lab.sync_topology_if_outdated(exclude_configurations=False)
        sync_topology.assert_called_once_with(exclude_configurations=False)


def test_sync_states_unknown_interface() -> None:
    """sync_states tolerates unknown interface IDs in the response.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    node = lab._create_node_local("n1", "n1", "iosv")
    i1 = lab._create_interface_local("i1", "eth0", node, 0)
    i2 = lab._create_interface_local("i2", "eth1", node, 1)
    _ = lab._create_link_local(i1, i2, "l1")

    lab._session.get.return_value.json.return_value = {
        "nodes": {"n1": "STARTED"},
        "interfaces": {"missing-iface": "up"},
        "links": {"l1": "up"},
    }
    lab.sync_states()
    assert lab._nodes["n1"]._state == "STARTED"


def test_sync_full_path() -> None:
    """Lab.sync delegates to all sub-sync methods.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    with (
        patch.object(lab, "_sync_topology") as sync_topo,
        patch.object(lab, "sync_statistics") as sync_stats,
        patch.object(lab, "sync_layer3_addresses") as sync_l3,
        patch.object(lab, "sync_operational") as sync_op,
    ):
        lab.sync(topology_only=False)
        assert sync_topo.called and sync_stats.called
        assert sync_l3.called and sync_op.called


def test_import_nodes_no_interfaces() -> None:
    """_handle_import_nodes accepts nodes without interfaces.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    topo_nodes_no_ifaces = {
        "nodes": [{"id": "n3", "label": "n3", "node_definition": "iosv"}]
    }
    lab._handle_import_nodes(topo_nodes_no_ifaces)
    assert "n3" in lab._nodes


def test_import_nodes_dup_raises() -> None:
    """_handle_import_nodes raises ElementAlreadyExists for duplicate interface.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    _ = lab._create_interface_local(
        "i1", "eth0", lab._create_node_local("n1", "n1", "iosv"), 0
    )
    dup_iface_topo = {
        "nodes": [
            {
                "id": "n4",
                "label": "n4",
                "node_definition": "iosv",
                "interfaces": [
                    {"id": "i1", "label": "eth0", "type": "physical", "slot": 0}
                ],
            }
        ]
    }
    with pytest.raises(ElementAlreadyExists):
        lab._handle_import_nodes(dup_iface_topo)


def test_import_interfaces() -> None:
    """_handle_import_interfaces adds interfaces from topology.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    _ = lab._create_node_local("n1", "n1", "iosv")
    topo_interface = {
        "interfaces": [
            {"id": "i5", "node": "n1", "label": "eth5", "type": "physical", "slot": 5}
        ]
    }
    lab._handle_import_interfaces(topo_interface)
    assert "i5" in lab._interfaces


def test_import_annotations() -> None:
    """_handle_import_annotations handles annotations and smart_annotations.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    annotation_topo = {"annotations": [{"id": "a5", "type": "rectangle"}]}
    lab._handle_import_annotations(annotation_topo)
    assert "a5" in lab._annotations
    lab._handle_import_annotations({"annotations": []})
    lab._handle_import_annotations(
        {"annotations": [], "smart_annotations": [{"id": "s5", "tag": "tag5"}]}
    )
    assert "s5" in lab._smart_annotations


def test_import_node_and_interface() -> None:
    """_import_interface and _import_node add elements from payload.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    _ = lab._create_node_local("n1", "n1", "iosv")
    lab._import_interface(
        "i6", "n1", {"data": {"label": "eth6", "slot": 6, "type": "physical"}}
    )
    lab._import_node("n6", {"data": {"label": "n6", "node_definition": "iosv"}})
    assert "i6" in lab._interfaces
    assert "n6" in lab._nodes


def test_add_interfaces_branch() -> None:
    """_add_interfaces adds top-level interfaces from topology.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    _ = lab._create_node_local("n1", "n1", "iosv")
    lab._add_interfaces(
        {
            "interfaces": [
                {
                    "id": "i7",
                    "node": "n1",
                    "label": "eth7",
                    "type": "physical",
                    "slot": 7,
                }
            ]
        },
        new_interfaces=["i7"],
    )
    assert "i7" in lab._interfaces


def test_sync_layer3_addresses() -> None:
    """sync_layer3_addresses maps addresses to node interfaces.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    node = lab._create_node_local("n1", "n1", "iosv")
    with (
        patch.object(lab, "sync_topology_if_outdated", return_value=None),
        patch.object(node, "map_l3_addresses_to_interfaces") as map_l3,
    ):
        lab._session.get.return_value.json.return_value = {
            "n1": {"interfaces": {"aa": {"id": "i1"}}}
        }
        lab.sync_layer3_addresses()
        map_l3.assert_called_with({"aa": {"id": "i1"}})


def test_clear_discovered_addresses() -> None:
    """clear_discovered_addresses clears L3 address mapping.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    node = lab._create_node_local("n1", "n1", "iosv")
    with (
        patch.object(lab, "sync_topology_if_outdated", return_value=None),
        patch.object(node, "map_l3_addresses_to_interfaces") as map_l3,
    ):
        lab._session.get.return_value.json.return_value = {
            "n1": {"interfaces": {"aa": {"id": "i1"}}}
        }
        lab.sync_layer3_addresses()
        lab.clear_discovered_addresses()
        map_l3.assert_called_with({})


def test_get_smart_annotation_by_tag_missing() -> None:
    """Raise SmartAnnotationNotFound when no local tag matches.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    with patch.object(lab, "sync_topology_if_outdated", return_value=None):
        with pytest.raises(SmartAnnotationNotFound):
            lab.get_smart_annotation_by_tag("missing-tag")
