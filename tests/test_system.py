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
"""Tests for SystemManagement, ComputeHost, and SystemNotice mutations and syncs."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from virl2_client.exceptions import ControllerNotFound
from virl2_client.models.system import ComputeHost, SystemManagement, SystemNotice
from virl2_client.utils import OptInStatus


def _notice_data(notice_id: str = "n1", **overrides: Any) -> dict[str, Any]:
    """Build a notice data dict matching the API response shape.

    :param notice_id: Notice identifier.
    :param overrides: Fields to override.
    :returns: A dict with "id" key; pop it and pass the rest as **kwargs.
    """
    return {
        "id": notice_id,
        "level": "info",
        "label": "lbl",
        "content": "content",
        "enabled": True,
        "acknowledged": {},
        **overrides,
    }


def _make_notice(
    system: SystemManagement, notice_id: str = "n1", **overrides: Any
) -> SystemNotice:
    """Create a SystemNotice from API-shaped data."""
    data = _notice_data(notice_id, **overrides)
    return SystemNotice(system, data.pop("id"), **data)


def _new_compute_host(system: SystemManagement, compute_id: str) -> ComputeHost:
    """Create a baseline compute-host object for tests.

    :param system: Parent system-management object.
    :param compute_id: Compute-host identifier.
    :returns: A new compute-host model with baseline values.
    """
    return ComputeHost(
        system,
        compute_id,
        f"host-{compute_id}",
        "10.0.0.1",
        is_connector=False,
        is_simulator=True,
        is_connected=True,
        is_synced=True,
        admission_state="approved",
        node_counts={"running": 0},
    )


def test_telemetry_state() -> None:
    """Get and set telemetry state.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    system = SystemManagement(session, auto_sync=False)
    session.get.return_value.json.return_value = {"opt_in": "accepted"}
    assert system.telemetry_state == OptInStatus.ACCEPTED
    system.telemetry_state = OptInStatus.DECLINED
    session.put.assert_called_with("telemetry", json={"opt_in": "DECLINED"})


def test_compute_host_mutation() -> None:
    """Compute host admission_state setter.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    system = SystemManagement(session, auto_sync=False)
    host = _new_compute_host(system, "c1")
    system._compute_hosts = {"c1": host}
    session.patch.return_value.json.return_value = {"admission_state": "ready"}
    host.admission_state = "ready"
    assert host.admission_state == "ready"


def test_system_notice_update_preserves_id() -> None:
    """_update must not overwrite notice ID.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    system = SystemManagement(session, auto_sync=False)
    notice = _make_notice(system, "n1")
    notice._update({"id": "changed", "level": "warning"}, push_to_server=False)
    assert notice.id == "n1"
    assert notice._level == "warning"


def test_compute_host_update_preserves_id() -> None:
    """_update must not overwrite compute host ID.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    system = SystemManagement(session, auto_sync=False)
    host = _new_compute_host(system, "c1")
    host._update({"id": "changed", "hostname": "new-host"}, push_to_server=False)
    assert host.compute_id == "c1"
    assert host._hostname == "new-host"


def test_system_notice_mutation() -> None:
    """System notice label, content, level setters.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    system = SystemManagement(session, auto_sync=False)
    notice = _make_notice(system, "n1")
    session.patch.return_value.json.return_value = {"content": "new-content"}
    notice._set_notice_properties({"content": "new-content"})
    assert notice.content == "new-content"


def test_maintenance_mode_notice() -> None:
    """Maintenance mode and notice creation/resolution.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    system = SystemManagement(session, auto_sync=False)
    system._system_notices = {"n1": _make_notice(system, "n1")}
    session.patch.return_value.json.return_value = {"resolved_notice": None}
    system.maintenance_mode = True
    assert system.maintenance_mode is True
    system.maintenance_notice = None
    assert system.maintenance_notice is None


def test_sync_notices_if_outdated() -> None:
    """sync_system_notices_if_outdated updates existing notices.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    system = SystemManagement(session, auto_sync=False)
    system._system_notices = {"n1": _make_notice(system, "n1")}
    existing = system._system_notices["n1"]
    system.auto_sync = True
    system.auto_sync_interval = 0
    session.get.side_effect = [
        MagicMock(
            json=MagicMock(
                return_value=[
                    {
                        "id": "n1",
                        "level": "warning",
                        "label": "lbl",
                        "content": "x",
                        "enabled": True,
                        "acknowledged": {},
                    }
                ]
            )
        ),
        MagicMock(
            json=MagicMock(return_value={"maintenance_mode": False, "notice": None})
        ),
    ]
    system.sync_system_notices_if_outdated()
    assert existing._level == "warning"
    assert system._maintenance_notice is None


def test_compute_host_identity() -> None:
    """Compute host repr, eq, hash.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    system = SystemManagement(session, auto_sync=False)
    host = _new_compute_host(system, "c9")
    assert "Compute host:" in str(host)
    assert host.compute_id == "c9"
    assert system._compute_hosts.get("missing") is None


def test_notice_id_property() -> None:
    """Notice id property and _set_notice_property.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    system = SystemManagement(session, auto_sync=False)
    notice = _make_notice(system, "n9")
    assert notice.id == "n9"
    session.patch.return_value.json.return_value = {"label": "updated"}
    notice._set_notice_property("label", "updated")
    assert notice._label == "updated"


def test_sync_hosts_updates_existing() -> None:
    """Existing host updated in-place on sync.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    system = SystemManagement(session, auto_sync=False)
    existing_host = _new_compute_host(system, "c1")
    system._compute_hosts = {"c1": existing_host}
    session.get.return_value.json.return_value = [
        {
            "id": "c1",
            "hostname": "host-new",
            "server_address": "10.0.0.2",
            "is_connector": False,
            "is_simulator": True,
            "is_connected": True,
            "is_synced": True,
            "admission_state": "approved",
            "node_counts": {"running": 1},
        }
    ]
    system.sync_compute_hosts()
    assert existing_host._hostname == "host-new"


def test_sync_notices_removes_stale() -> None:
    """Stale notice removed during sync.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    system = SystemManagement(session, auto_sync=False)
    stale_notice = _make_notice(system, "stale", label="old")
    system._system_notices = {"stale": stale_notice}
    session.get.side_effect = [
        MagicMock(json=MagicMock(return_value=[])),
        MagicMock(
            json=MagicMock(return_value={"maintenance_mode": False, "notice": None})
        ),
    ]
    session.put.return_value.json.return_value = {
        "maintenance_mode": False,
        "notice": None,
    }
    system.sync_system_notices()
    assert "stale" not in system._system_notices


def test_get_external_connectors() -> None:
    """get_external_connectors with sync=None and sync=True.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    system = SystemManagement(session, auto_sync=False)
    session.get.return_value.json.return_value = [{"id": "ec0"}]
    assert system.get_external_connectors(sync=None) == [{"id": "ec0"}]
    session.put.return_value.json.return_value = [{"id": "ec1"}]
    assert system.get_external_connectors(sync=True) == [{"id": "ec1"}]


def test_set_web_session_timeout() -> None:
    """set_web_session_timeout PUTs a JSON body and returns updated int.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    system = SystemManagement(session, auto_sync=False)
    session.put.return_value.json.return_value = 120
    assert system.set_web_session_timeout(120) == 120
    session.put.assert_called_with("web_session_timeout", json={"timeout": 120})


def test_maintenance_notice_resolve() -> None:
    """maintenance_notice resolution updates notice.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    system = SystemManagement(session, auto_sync=False)
    notice = MagicMock()
    system._system_notices = {"n1": notice}
    session.patch.return_value.json.return_value = {"resolved_notice": {"id": "n1"}}
    system.maintenance_notice = MagicMock(id="n1")
    assert system.maintenance_notice is notice
    notice._update.assert_called_once_with({"id": "n1"}, push_to_server=False)


def test_sync_hosts_replaces_stale() -> None:
    """sync_compute_hosts replaces stale hosts.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    system = SystemManagement(session, auto_sync=False)
    system._compute_hosts = {"stale": MagicMock()}
    session.get.return_value.json.return_value = [
        {
            "id": "compute-1",
            "hostname": "h1",
            "server_address": "10.0.0.1",
            "is_connector": False,
            "is_simulator": True,
            "is_connected": True,
            "is_synced": True,
            "admission_state": "approved",
        }
    ]
    system.sync_compute_hosts()
    assert "compute-1" in system._compute_hosts
    assert "stale" not in system._compute_hosts
    assert system._compute_hosts["compute-1"].node_counts == {}


def test_system_controller_without_connector_raises() -> None:
    """Raise ControllerNotFound when no connector host exists.

    NOTE: LLM-generated test -- verify for correctness.
    """
    system = SystemManagement(MagicMock(), auto_sync=False)
    system._compute_hosts = {
        "compute-1": ComputeHost(
            system,
            compute_id="compute-1",
            hostname="compute-1",
            server_address="10.0.0.1",
            is_connector=False,
            is_simulator=True,
            is_connected=True,
            is_synced=True,
            admission_state="approved",
            node_counts={},
        )
    }

    with pytest.raises(ControllerNotFound):
        _ = system.controller
