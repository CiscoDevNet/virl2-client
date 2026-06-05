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
"""Lab sync/associations unit tests covering topology and management helpers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from tests.helpers import make_lab
from virl2_client.exceptions import (
    AnnotationNotFound,
    InterfaceNotFound,
    InvalidAnnotationType,
    LinkNotFound,
    NodeNotFound,
    SmartAnnotationNotFound,
)
from virl2_client.models import Lab


def _make_lab_context() -> tuple[Lab, MagicMock, MagicMock]:
    """Create a test lab with mocked session and resource pool manager.

    :returns: Lab, mocked session, mocked pool manager.
    """
    session = MagicMock()
    rpm = MagicMock()
    lab = make_lab(session=session, resource_pool_manager=rpm)
    return lab, session, rpm


def test_sync_statistics() -> None:
    """sync_statistics updates node, link, and interface statistics.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab, session, _ = _make_lab_context()
    n1 = lab._create_node_local("n1", "n1", "iosv")
    i1 = lab._create_interface_local("i1", "eth0", n1, 0)
    i2 = lab._create_interface_local("i2", "eth1", n1, 1)
    link = lab._create_link_local(i1, i2, "l1")

    session.get.return_value.json.return_value = {
        "nodes": {
            "n1": {
                "cpu_usage": "50.5",
                "block0_rd_bytes": "1048576",
                "block0_wr_bytes": "0",
                "times": {"QUEUED": 25, "STARTED": 200, "BOOTED": 175},
            }
        },
        "links": {
            "l1": {
                "readbytes": "10",
                "readpackets": "2",
                "writebytes": "20",
                "writepackets": "4",
            }
        },
    }
    lab.sync_statistics()
    assert n1.statistics["cpu_usage"] == 50.5
    assert n1.statistics["times"] == {"QUEUED": 25, "STARTED": 200, "BOOTED": 175}
    assert link.statistics["readbytes"] == 10
    assert i2.statistics["writebytes"] == 10


def test_sync_stats_without_resource_stats() -> None:
    """Tolerate ext_conn/UMS/QUEUED node payloads that only carry `times`.

    The CML controller only reports cpu_usage / block0_* for nodes
    backed by a real VM. External connectors, unmanaged switches, and
    nodes still in the QUEUED state come back as just ``{"times": ...}``
    on v2.9 / v2.10 (and ``{"times": ..., "is_running": ...}`` on dev).

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab, session, _ = _make_lab_context()
    ext_conn = lab._create_node_local("ec", "ec", "external_connector")
    ums = lab._create_node_local("us", "us", "unmanaged_switch")

    session.get.return_value.json.return_value = {
        "nodes": {
            "ec": {"times": {"QUEUED": 10, "STARTED": 50, "BOOTED": 45}},
            "us": {
                "times": {"QUEUED": 12, "STARTED": 40, "BOOTED": 35},
                "is_running": True,
            },
        },
        "links": {},
    }
    lab.sync_statistics()
    assert ext_conn.statistics["cpu_usage"] == 0
    assert ext_conn.statistics["disk_read"] == 0
    assert ext_conn.statistics["disk_write"] == 0
    assert ext_conn.statistics["times"] == {"QUEUED": 10, "STARTED": 50, "BOOTED": 45}
    assert ums.statistics["times"] == {"QUEUED": 12, "STARTED": 40, "BOOTED": 35}
    assert ext_conn.boot_time == 45
    assert ums.boot_time == 35


def test_node_times_properties_expose_simulation_stats() -> None:
    """Node.times/boot_time/started_time/queued_time mirror simulation_stats.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab, _session, _ = _make_lab_context()
    n1 = lab._create_node_local("n1", "n1", "iosv")
    n1.statistics = {
        "cpu_usage": 0,
        "disk_read": 0,
        "disk_write": 0,
        "times": {"QUEUED": 25, "STARTED": 200, "BOOTED": 175},
    }
    with patch.object(lab, "sync_statistics_if_outdated"):
        assert n1.times == {"QUEUED": 25, "STARTED": 200, "BOOTED": 175}
        assert n1.boot_time == 175
        assert n1.started_time == 200
        assert n1.queued_time == 25


def test_node_times_defaults_to_empty_pre_sync() -> None:
    """Node.times returns {} pre-sync; convenience properties return 0.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab, _session, _ = _make_lab_context()
    n1 = lab._create_node_local("n1", "n1", "iosv")

    with patch.object(lab, "sync_statistics_if_outdated"):
        assert n1.times == {}
        assert n1.boot_time == 0
        assert n1.started_time == 0
        assert n1.queued_time == 0


def test_lab_uptime_min_started_running_nodes() -> None:
    """Lab.uptime is the smallest Node.started_time when all nodes are running.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab, _session, _ = _make_lab_context()
    n1 = lab._create_node_local("n1", "n1", "iosv")
    n2 = lab._create_node_local("n2", "n2", "iosv")
    n1.statistics["times"] = {"QUEUED": 5, "STARTED": 7200, "BOOTED": 7000}
    n2.statistics["times"] = {"QUEUED": 8, "STARTED": 600, "BOOTED": 540}

    with patch.object(lab, "sync_statistics_if_outdated"):
        assert lab.uptime == 600


def test_lab_uptime_zero_when_any_node_not_running() -> None:
    """Lab.uptime is 0 if any node is not running, or the lab is empty.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab, _session, _ = _make_lab_context()
    assert lab.uptime == 0  # empty lab

    running = lab._create_node_local("n1", "n1", "iosv")
    queued = lab._create_node_local("n2", "n2", "iosv")
    running.statistics["times"] = {"QUEUED": 5, "STARTED": 600, "BOOTED": 540}
    queued.statistics["times"] = {"QUEUED": 30, "STARTED": 0, "BOOTED": 0}

    with patch.object(lab, "sync_statistics_if_outdated"):
        assert lab.uptime == 0
        assert queued.started_time == 0


def test_sync_states() -> None:
    """sync_states updates states and marks stale nodes, interfaces, links.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab, session, _ = _make_lab_context()
    n1 = lab._create_node_local("n1", "n1", "iosv")
    stale_node = lab._create_node_local("n-stale", "n-stale", "iosv")
    i1 = lab._create_interface_local("i1", "eth0", n1, 0)
    i2 = lab._create_interface_local("i2", "eth1", n1, 1)
    stale_interface = lab._create_interface_local("i-stale", "eth9", n1, 9)
    link = lab._create_link_local(i1, i2, "l1")
    stale_link = lab._create_link_local(
        stale_interface,
        lab._create_interface_local("i-stale2", "eth10", stale_node, 0),
        "l-stale",
    )

    session.get.return_value.json.return_value = {
        "nodes": {"n1": "started", "unknown-node": "booted"},
        "interfaces": {"i1": "up", "i2": "down", "unknown-iface": "up"},
        "links": {"l1": "up", "unknown-link": "active"},
    }
    lab.sync_states()
    assert n1._state == "started"
    assert stale_node._stale is True
    assert i1._state == "up"
    assert i2._state == "down"
    assert stale_interface._stale is True
    assert link._state == "up"
    assert stale_link._stale is True


@pytest.mark.parametrize("annotation_type", ["rectangle", "ellipse", "line", "text"])
def test_create_annotation_variants(annotation_type: str) -> None:
    """Create each supported annotation type.

    NOTE: LLM-generated test -- verify for correctness.

    :param annotation_type: The annotation type under test.
    :raises AssertionError: If creation result is inconsistent.
    """
    lab, session, _ = _make_lab_context()
    session.post.return_value.json.return_value = {
        "id": f"a-{annotation_type}",
        "type": annotation_type,
    }
    annotation = lab.create_annotation(annotation_type)
    assert annotation.id == f"a-{annotation_type}"
    assert lab._initialized is True


def test_create_annotation_invalid_type_raises() -> None:
    """Raise InvalidAnnotationType for unsupported annotation kinds.

    NOTE: LLM-generated test -- verify for correctness.

    :raises AssertionError: If expected exception is not raised.
    """
    lab, _, _ = _make_lab_context()
    with pytest.raises(InvalidAnnotationType):
        lab._create_annotation_local("a1", "unknown")


def test_create_smart_annotation_nodes_update() -> None:
    """Create smart annotation from node ids/objects and apply updates.

    NOTE: LLM-generated test -- verify for correctness.

    :raises AssertionError: If tag/update workflow is not applied.
    """
    lab, _, _ = _make_lab_context()
    n1 = lab._create_node_local("n1", "n1", "iosv")
    n2 = lab._create_node_local("n2", "n2", "iosv")
    n1.add_tag = MagicMock()
    n2.add_tag = MagicMock()
    smart_annotation = MagicMock()

    nodes_arg = [n1.id, n2]
    with (
        patch.object(lab, "_sync_topology"),
        patch.object(lab, "get_smart_annotation_by_tag", return_value=smart_annotation),
    ):
        result = lab.create_smart_annotation("core", nodes_arg, z_index=2)

    assert result is smart_annotation
    n1.add_tag.assert_called_once_with("core")
    n2.add_tag.assert_called_once_with("core")
    smart_annotation.update.assert_called_once_with({"z_index": 2})
    # Regression guard for CMLDEV-1117: the caller's list must not be
    # mutated (previously, string IDs were replaced with Node objects
    # in-place as an unexpected side effect).
    assert nodes_arg == [n1.id, n2]


@pytest.mark.parametrize(
    ("finder", "element_id"),
    [
        (Lab._find_node_in_topology, "n1"),
        (Lab._find_link_in_topology, "l1"),
        (Lab._find_interface_in_topology, "i1"),
        (Lab._find_annotation_in_topology, "a1"),
        (Lab._find_smart_annotation_in_topology, "s1"),
    ],
)
def test_find_in_topology_success(finder: Callable[..., Any], element_id: str) -> None:
    """_find_*_in_topology returns element when present.

    NOTE: LLM-generated test -- verify for correctness.
    """
    topology = {
        "nodes": [{"id": "n1"}],
        "links": [{"id": "l1", "interface_a": "i1", "interface_b": "i2"}],
        "interfaces": [{"id": "i1", "node": "n1"}],
        "annotations": [{"id": "a1"}],
        "smart_annotations": [{"id": "s1"}],
    }
    assert finder(element_id, topology)["id"] == element_id


@pytest.mark.parametrize(
    ("finder", "exception"),
    [
        (Lab._find_node_in_topology, NodeNotFound),
        (Lab._find_link_in_topology, LinkNotFound),
        (Lab._find_interface_in_topology, InterfaceNotFound),
        (Lab._find_annotation_in_topology, AnnotationNotFound),
        (Lab._find_smart_annotation_in_topology, SmartAnnotationNotFound),
    ],
)
def test_find_in_topology_missing(
    finder: Callable[..., Any], exception: type[Exception]
) -> None:
    """_find_*_in_topology raises when element not in topology.

    NOTE: LLM-generated test -- verify for correctness.
    """
    topology = {
        "nodes": [{"id": "n1"}],
        "links": [{"id": "l1"}],
        "interfaces": [{"id": "i1"}],
        "annotations": [{"id": "a1"}],
        "smart_annotations": [{"id": "s1"}],
    }
    with pytest.raises(exception):
        finder("missing", topology)


def test_update_lab_properties() -> None:
    """update_lab_properties updates title, description, notes, owner, etc.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab, _, _ = _make_lab_context()
    lab._user_management.get_username.return_value = "from-cache"
    lab.update_lab_properties(
        {
            "title": "new-title",
            "description": "new-desc",
            "notes": "new-notes",
            "owner": "owner-id-123",
            "owner_username": "from-response",
            "autostart": {"enabled": True},
            "node_staging": {
                "enabled": True,
                "start_remaining": True,
                "abort_on_failure": False,
            },
        }
    )
    assert lab.title == "new-title"
    assert lab.description == "new-desc"
    assert lab.notes == "new-notes"
    # Response-supplied username wins over the cached value (no cache lookup).
    assert lab.owner == "from-response"
    assert lab.owner_id == "owner-id-123"
    lab._user_management.get_username.assert_not_called()
    assert lab.autostart["enabled"] is True
    assert lab.node_staging["enabled"] is True


def test_get_pyats_testbed() -> None:
    """get_pyats_testbed returns YAML; hostname param passed through.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab, session, _ = _make_lab_context()
    session.get.return_value.text = "pyats-yaml"
    assert lab.get_pyats_testbed() == "pyats-yaml"
    assert lab.get_pyats_testbed(hostname="host") == "pyats-yaml"


def test_sync_and_cleanup_pyats() -> None:
    """sync_pyats forwards the password, cleanup delegates to pyats.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab, _, _ = _make_lab_context()
    with patch.object(lab.pyats, "sync_testbed") as sync_testbed:
        lab.sync_pyats()
        sync_testbed.assert_called_once_with(lab.username, lab.password)
    with patch.object(lab.pyats, "cleanup") as cleanup:
        lab.cleanup_pyats_connections()
        cleanup.assert_called_once()


def test_sync_pyats_jwt_when_password_missing() -> None:
    """sync_pyats uses the active JWT when the client has no password.

    Token-only clients (e.g. ClientLibrary initialized via cml_token /
    jwtoken) leave Lab.password unset.  In that case sync_pyats must
    fall back to the live JWT on the session's auth handler so the SSH
    console can verify the token instead of creating a new one.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab, session, _ = _make_lab_context()
    lab.password = None
    session.auth.token = "jwt-token-placeholder"
    with patch.object(lab.pyats, "sync_testbed") as sync_testbed:
        lab.sync_pyats()
        sync_testbed.assert_called_once_with(lab.username, "jwt-token-placeholder")


def test_associations_crud() -> None:
    """associations get and update_associations return expected data.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab, session, _ = _make_lab_context()
    session.get.return_value.json.return_value = {"groups": [], "users": []}
    assert lab.associations == {"groups": [], "users": []}
    session.patch.return_value.json.return_value = {"groups": [], "users": []}
    assert lab.update_associations({"groups": [], "users": []}) == {
        "groups": [],
        "users": [],
    }


def test_connector_mappings() -> None:
    """connector_mappings get and update return expected data.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab, session, _ = _make_lab_context()
    session.get.return_value.json.return_value = [{"key": "nat", "device_name": "br0"}]
    assert lab.connector_mappings == [{"key": "nat", "device_name": "br0"}]
    session.patch.return_value.json.return_value = [
        {"key": "nat", "device_name": "br1"}
    ]
    assert lab.update_connector_mappings([{"key": "nat", "device_name": "br1"}]) == [
        {"key": "nat", "device_name": "br1"}
    ]


def test_download_topology() -> None:
    """download returns topology YAML from session.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab, session, _ = _make_lab_context()
    session.get.return_value.text = "topology-yaml"
    assert lab.download() == "topology-yaml"


def test_sync_operational() -> None:
    """sync_operational updates node operational state.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab, session, rpm = _make_lab_context()
    n1 = lab._create_node_local("n1", "n1", "iosv")
    n1.sync_operational = MagicMock()

    session.get.side_effect = [
        MagicMock(json=MagicMock(return_value=["pool-1"])),
        MagicMock(json=MagicMock(return_value=[{"id": "n1", "state": "running"}])),
        MagicMock(json=MagicMock(return_value=[])),
    ]
    rpm.get_resource_pools_by_ids.return_value = {"pool-1": MagicMock(id="pool-1")}
    lab.sync_operational()
    n1.sync_operational.assert_called_once_with({"id": "n1", "state": "running"})
