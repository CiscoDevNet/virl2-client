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
"""Lab lifecycle, element removal, and convergence tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from tests.helpers import make_lab
from virl2_client.exceptions import LabNotFound, NodeNotFound


def test_remove_link_with_wait() -> None:
    """remove_link with wait=True triggers wait_until_lab_converged.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    node = lab._create_node_local("n1", "n1", "iosv")
    interface_a = lab._create_interface_local("i1", "eth0", node, 0)
    interface_b = lab._create_interface_local("i2", "eth1", node, 1)
    _ = lab._create_link_local(interface_a, interface_b, "l1")
    with patch.object(lab, "wait_until_lab_converged", return_value=None) as wait:
        lab.remove_link("l1", wait=True)
        wait.assert_called_once()


def test_remove_interface_with_wait() -> None:
    """remove_interface with wait=True triggers wait_until_lab_converged.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    node = lab._create_node_local("n1", "n1", "iosv")
    interface_a = lab._create_interface_local("i1", "eth0", node, 0)
    interface_b = lab._create_interface_local("i2", "eth1", node, 1)
    _ = lab._create_link_local(interface_a, interface_b, "l1")
    with patch.object(lab, "wait_until_lab_converged", return_value=None) as wait:
        lab.remove_interface("i1", wait=True)
        wait.assert_called_once()


def test_remove_link_no_wait() -> None:
    """remove_link without wait does not block.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    node = lab._create_node_local("n1", "n1", "iosv")
    interface_a = lab._create_interface_local("i1", "eth0", node, 0)
    interface_b = lab._create_interface_local("i2", "eth1", node, 1)
    _ = lab._create_link_local(interface_a, interface_b, "l2")
    lab.remove_link("l2")


def test_remove_node_with_wait() -> None:
    """remove_node with wait=True triggers wait_until_lab_converged.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    node = lab._create_node_local("n1", "n1", "iosv")
    interface_a = lab._create_interface_local("i1", "eth0", node, 0)
    interface_b = lab._create_interface_local("i2", "eth1", node, 1)
    _ = lab._create_link_local(interface_a, interface_b, "l1")
    with patch.object(lab, "wait_until_lab_converged", return_value=None) as wait:
        lab.remove_node("n1", wait=True)
        wait.assert_called_once()


def test_remove_annotation_by_id() -> None:
    """remove_annotation by string id removes from lab.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    _ = lab._create_annotation_local("a1", "rectangle")
    lab.remove_annotation("a1")
    assert "a1" not in lab._annotations


def test_remove_annotation_by_obj() -> None:
    """remove_annotation by object removes from lab.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    annotation = lab._create_annotation_local("a1", "rectangle")
    annotation._stale = False
    lab.remove_annotation(annotation)
    assert "a1" not in lab._annotations


def test_remove_smart_annotation_by_id() -> None:
    """remove_smart_annotation by string id removes from lab.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    _ = lab._create_smart_annotation_local("s1", tag="core")
    lab.remove_smart_annotation("s1")
    assert "s1" not in lab._smart_annotations


def test_remove_smart_annotation_by_obj() -> None:
    """remove_smart_annotation by object removes from lab.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    smart_annotation = lab._create_smart_annotation_local("s1", tag="core")
    smart_annotation._stale = False
    lab.remove_smart_annotation(smart_annotation)
    assert "s1" not in lab._smart_annotations


def test_bulk_remove_annotations() -> None:
    """remove_annotations clears all annotations.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    _ = lab._create_annotation_local("a2", "rectangle")
    lab.remove_annotations()
    assert not lab._annotations


def test_bulk_remove_smart_annotations() -> None:
    """remove_smart_annotations clears all smart annotations.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    _ = lab._create_smart_annotation_local("s2", tag="tag2")
    lab.remove_smart_annotations()
    assert not lab._smart_annotations


def test_bulk_remove_nodes() -> None:
    """remove_nodes with wait triggers convergence and marks stale.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    node2 = lab._create_node_local("n2", "n2", "iosv")
    with patch.object(lab, "wait_until_lab_converged", return_value=None) as wait_nodes:
        lab.remove_nodes(wait=True)
        wait_nodes.assert_called_once()
    assert not lab._nodes
    assert node2._stale is True


def test_remove_keyerror_node_guard() -> None:
    """_remove_node_local tolerates already-removed node.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    node = lab._create_node_local("n1", "n1", "iosv")
    with patch.object(lab, "wait_until_lab_converged", return_value=None):
        lab.remove_node("n1", wait=True)
    lab._remove_node_local(node)


def test_remove_keyerror_link_guard() -> None:
    """_remove_link_local tolerates already-removed link.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    node = lab._create_node_local("n1", "n1", "iosv")
    interface_a = lab._create_interface_local("i1", "eth0", node, 0)
    interface_b = lab._create_interface_local("i2", "eth1", node, 1)
    link = lab._create_link_local(interface_a, interface_b, "l1")
    lab.remove_link("l1")
    lab._remove_link_local(link)


def test_remove_keyerror_interface_guard() -> None:
    """_remove_interface_local tolerates already-removed interface.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    node = lab._create_node_local("n1", "n1", "iosv")
    interface_a = lab._create_interface_local("i1", "eth0", node, 0)
    lab.remove_interface("i1")
    lab._remove_interface_local(interface_a)


def test_remove_keyerror_annotation_guard() -> None:
    """_remove_annotation_local tolerates already-removed annotation.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    annotation = lab._create_annotation_local("a1", "rectangle")
    lab.remove_annotation("a1")
    lab._remove_annotation_local(annotation)


def test_remove_keyerror_smart_annotation_guard() -> None:
    """_remove_smart_annotation_local tolerates already-removed smart annotation.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    smart_annotation = lab._create_smart_annotation_local("s1", tag="core")
    lab.remove_smart_annotation("s1")
    lab._remove_smart_annotation_local(smart_annotation)


@pytest.mark.parametrize("method", ["start", "stop", "wipe"])
def test_lab_method_waits(method: str) -> None:
    """Start/stop/wipe each trigger wait_until_lab_converged.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    with patch.object(lab, "wait_until_lab_converged") as wait:
        getattr(lab, method)(wait=True)
        wait.assert_called_once()


def test_lab_state_fetch() -> None:
    """state() returns API value.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    lab._session.get.return_value.json.return_value = "STARTED"
    lab._state = None
    assert lab.state() == "STARTED"
    lab._state = "STOPPED"
    lab._session.lock = MagicMock()
    assert lab.state() == "STOPPED"


def test_lab_is_active() -> None:
    """is_active when STARTED, not active when STOPPED.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    lab._state = "STARTED"
    assert lab.is_active() is True
    lab._state = "STOPPED"
    assert lab.is_active() is False


def test_lab_details() -> None:
    """Details returns JSON from session.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    lab._session.get.return_value.json.return_value = {"id": "l1"}
    assert lab.details() == {"id": "l1"}


def test_lab_download() -> None:
    """Download returns text from session.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    lab._session.get.return_value.text = "yaml"
    assert lab.download() == "yaml"


def test_lab_sync_events() -> None:
    """sync_events returns True then False on subsequent calls.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    lab._session.get.return_value.json.return_value = [{"event": 1}]
    assert lab.sync_events() is True
    assert lab.sync_events() is False


def test_lab_build_configurations() -> None:
    """build_configurations returns per-node results and calls sync_topology_if_outdated."""
    lab = make_lab()
    expected_results = [
        {"id": "n0", "label": "R1", "result": "generated", "reason": None},
        {
            "id": "n1",
            "label": "R2",
            "result": "skipped",
            "reason": "already configured",
        },
    ]
    lab._session.put.return_value.status_code = 200
    lab._session.put.return_value.json.return_value = expected_results
    with patch.object(
        lab, "sync_topology_if_outdated", return_value=None
    ) as sync_topology:
        results = lab.build_configurations()
        sync_topology.assert_called_once()
    assert results == expected_results


def test_lab_build_configurations_pre_211_no_content() -> None:
    """Pre-2.11 bootstrap returned 204 with no body; return an empty list."""
    lab = make_lab()
    lab._session.put.return_value.status_code = 204
    with patch.object(
        lab, "sync_topology_if_outdated", return_value=None
    ) as sync_topology:
        results = lab.build_configurations()
        sync_topology.assert_called_once()
    assert results == []
    lab._session.put.return_value.json.assert_not_called()


def test_lab_convergence_timeout() -> None:
    """Raise RuntimeError when convergence max_iterations exceeded.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    with (
        patch.object(lab, "has_converged", return_value=False),
        patch("virl2_client.models.lab.time.sleep", return_value=None),
        pytest.raises(RuntimeError),
    ):
        lab.wait_until_lab_converged(max_iterations=1, wait_time=0)


def test_lab_has_converged_success() -> None:
    """has_converged returns True; wait succeeds immediately.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    lab._session.get.return_value.json.return_value = True
    assert lab.has_converged() is True
    with patch.object(lab, "has_converged", return_value=True):
        lab.wait_until_lab_converged()


def test_lab_remove_marks_stale() -> None:
    """Lab.remove marks the instance as stale.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    lab.remove()
    assert lab._stale is True


def test_sync_topology_import_path() -> None:
    """_sync_topology calls import_lab when not initialized."""
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
    """_sync_topology calls update_lab when initialized."""
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
    """_sync_topology raises LabNotFound on 404 and marks stale."""
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
    """_sync_topology raises HTTPStatusError on 500."""
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
    """_import_lab handles old schema path for created labs."""
    user_mgmt = MagicMock()
    user_mgmt.get_username.return_value = "owner-1"
    lab = make_lab(user_management=user_mgmt)
    old_schema = {
        "lab_title": "created",
        "lab_description": "desc",
        "lab_notes": "notes",
        "owner": "u1",
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
    user_mgmt.get_username.assert_called_once_with("u1")


def test_set_owner_username_overrides_cache() -> None:
    """Caller-supplied user_name wins and the cache is not consulted."""
    user_mgmt = MagicMock()
    user_mgmt.get_username.return_value = "from-cache"
    lab = make_lab(user_management=user_mgmt)
    lab._set_owner(user_id="u1", user_name="from-response")
    assert lab.owner == "from-response"
    assert lab.owner_id == "u1"
    user_mgmt.get_username.assert_not_called()


def test_set_owner_unresolved_user_none() -> None:
    """When only user_id is supplied and the cache misses, owner is None."""
    user_mgmt = MagicMock()
    user_mgmt.get_username.return_value = None
    lab = make_lab(user_management=user_mgmt)
    lab._set_owner(user_id="missing")
    assert lab.owner is None
    assert lab.owner_id == "missing"
    user_mgmt.get_username.assert_called_once_with("missing")


def test_remove_elements_helper() -> None:
    """_remove_elements removes nodes, links, interfaces, annotations.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    n_keep = lab._create_node_local("n-keep", "n-keep", "iosv")
    _ = lab._create_node_local("n-rm", "n-rm", "iosv")
    i_keep = lab._create_interface_local("i-keep", "eth0", n_keep, 0)
    i_rm = lab._create_interface_local("i-rm", "eth0", lab._nodes["n-rm"], 0)
    _ = lab._create_link_local(i_keep, i_rm, "l-rm")
    _ = lab._create_annotation_local("a-rm", "rectangle")
    _ = lab._create_smart_annotation_local("s-rm", tag="x")

    lab._remove_elements(
        removed_nodes=["n-rm"],
        removed_links=["l-rm"],
        removed_interfaces=["i-rm"],
        removed_annotations=["a-rm"],
        removed_smart_annotations=["s-rm"],
    )
    assert "n-rm" not in lab._nodes


def test_add_elements_helper() -> None:
    """_add_elements adds nodes, links, interfaces, annotations.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    n_keep = lab._create_node_local("n-keep", "n-keep", "iosv")
    lab._create_interface_local("i-keep", "eth0", n_keep, 0)
    topology = {
        "nodes": [
            {
                "id": "n-keep",
                "label": "n-keep-2",
                "node_definition": "iosv",
                "interfaces": [
                    {"id": "i-new", "label": "eth1", "type": "physical", "slot": 1}
                ],
            },
            {
                "id": "n-new",
                "label": "n-new",
                "node_definition": "iosv",
                "interfaces": [],
            },
        ],
        "interfaces": [
            {
                "id": "i-keep",
                "node": "n-keep",
                "label": "eth0",
                "type": "physical",
                "slot": 0,
            }
        ],
        "links": [{"id": "l-new", "interface_a": "i-keep", "interface_b": "i-new"}],
        "annotations": [{"id": "a-new", "type": "rectangle"}],
        "smart_annotations": [{"id": "s-new", "tag": "new-tag"}],
        "lab": {"title": "T", "description": "D", "notes": "N", "owner": None},
    }

    lab._add_elements(
        topology=topology,
        new_nodes=["n-new"],
        new_links=["l-new"],
        new_interfaces=["i-new"],
        new_annotations=["a-new"],
        new_smart_annotations=["s-new"],
    )
    assert "n-new" in lab._nodes
    assert "i-new" in lab._interfaces
    assert "l-new" in lab._links
    assert "a-new" in lab._annotations
    assert "s-new" in lab._smart_annotations


def test_update_elements_helper() -> None:
    """_update_elements calls _update on kept elements.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    n_keep = lab._create_node_local("n-keep", "n-keep", "iosv")
    lab._create_interface_local("i-keep", "eth0", n_keep, 0)
    _ = lab._create_annotation_local("a-new", "rectangle")
    _ = lab._create_smart_annotation_local("s-new", tag="new-tag")
    topology = {
        "nodes": [
            {
                "id": "n-keep",
                "label": "n-keep-2",
                "node_definition": "iosv",
                "interfaces": [
                    {"id": "i-new", "label": "eth1", "type": "physical", "slot": 1}
                ],
            },
        ],
        "interfaces": [
            {
                "id": "i-keep",
                "node": "n-keep",
                "label": "eth0",
                "type": "physical",
                "slot": 0,
            }
        ],
        "links": [],
        "annotations": [{"id": "a-new", "type": "rectangle"}],
        "smart_annotations": [{"id": "s-new", "tag": "new-tag"}],
        "lab": {"title": "T", "description": "D", "notes": "N", "owner": None},
    }

    with (
        patch.object(lab._nodes["n-keep"], "_update") as node_update,
        patch.object(lab._interfaces["i-keep"], "_update") as interface_update,
        patch.object(lab._annotations["a-new"], "_update") as annotation_update,
        patch.object(
            lab._smart_annotations["s-new"], "_update"
        ) as smart_annotation_update,
    ):
        lab._update_elements(
            topology=topology,
            kept_nodes=["n-keep"],
            kept_interfaces=["i-keep"],
            kept_annotations=["a-new"],
            kept_smart_annotations=["s-new"],
            exclude_configurations=True,
        )
        node_update.assert_called_once()
        interface_update.assert_called_once()
        annotation_update.assert_called_once()
        smart_annotation_update.assert_called_once()


def test_update_lab_route() -> None:
    """update_lab updates lab properties with topology.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    topology = {
        "nodes": [],
        "interfaces": [],
        "links": [],
        "annotations": [],
        "smart_annotations": [],
        "lab": {"title": "T", "description": "D", "notes": "N", "owner": None},
    }
    lab.update_lab(topology, exclude_configurations=False)
    assert lab.title == "T"


def test_update_lab_interfaces_from_nodes() -> None:
    """update_lab extracts interfaces from nodes when no top-level interfaces key."""
    lab = make_lab()
    node = lab._create_node_local("n1", "n1", "iosv")
    lab._create_interface_local("i1", "eth0", node, 0)
    topology = {
        "nodes": [
            {
                "id": "n1",
                "label": "n1",
                "node_definition": "iosv",
                "interfaces": [
                    {"id": "i1", "label": "eth0", "type": "physical", "slot": 0}
                ],
            }
        ],
        "links": [],
        "annotations": [],
        "smart_annotations": [],
        "lab": {"title": "T", "description": "D", "notes": "N", "owner": None},
    }
    lab.update_lab(topology, exclude_configurations=False)
    assert "i1" in lab._interfaces


def test_lab_resource_pools() -> None:
    """resource_pools property returns cached pools after sync.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    lab._resource_pools = ["rp1"]  # type: ignore[assignment]
    with patch.object(lab, "sync_operational_if_outdated", return_value=None):
        assert lab.resource_pools == ["rp1"]  # type: ignore[comparison-overlap]


def test_get_node_by_id_missing() -> None:
    """get_node_by_id raises NodeNotFound for missing id.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    with (
        patch.object(lab, "sync_topology_if_outdated", return_value=None),
        pytest.raises(NodeNotFound),
    ):
        lab.get_node_by_id("missing")


def test_get_smart_annotation_by_tag() -> None:
    """get_smart_annotation_by_tag returns annotation by tag.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    _ = lab._create_smart_annotation_local("s1", tag="core")
    with patch.object(lab, "sync_topology_if_outdated", return_value=None):
        assert lab.get_smart_annotation_by_tag("core").id == "s1"


def test_create_node_with_wait() -> None:
    """create_node with populate_interfaces and wait returns node.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    lab._session.post.return_value.json.return_value = {"id": "n2"}
    with (
        patch.object(lab, "sync_topology_if_outdated", return_value=None),
        patch.object(lab, "wait_until_lab_converged", return_value=None),
    ):
        created = lab.create_node("n2", "iosv", populate_interfaces=True, wait=True)
    assert created.id == "n2"


def test_create_link_interface_wait() -> None:
    """create_link and create_interface with wait trigger convergence.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    node = lab._create_node_local("n1", "n1", "iosv")
    i1 = lab._create_interface_local("i1", "eth0", node, 0)
    i2 = lab._create_interface_local("i2", "eth1", node, 1)
    lab._session.post.side_effect = [
        MagicMock(json=MagicMock(return_value={"id": "l2"})),
        MagicMock(
            json=MagicMock(return_value={"id": "i3", "label": "eth2", "slot": 2})
        ),
    ]
    with (
        patch.object(lab, "sync_topology_if_outdated", return_value=None),
        patch.object(lab, "get_interface_by_id", side_effect=[i1, i2]),
        patch.object(lab, "get_node_by_id", return_value=node),
        patch.object(lab, "wait_until_lab_converged", return_value=None) as wait,
    ):
        _ = lab.create_link("i1", "i2", wait=True)
        _ = lab.create_interface("n1", slot=2, wait=True)
        assert wait.call_count == 2
