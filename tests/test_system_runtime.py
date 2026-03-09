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
"""Tests for SystemManagement runtime: compute hosts, connectors, timeout, telemetry."""

from __future__ import annotations

from unittest.mock import MagicMock

from virl2_client.models.system import SystemManagement
from virl2_client.utils import OptInStatus


def test_compute_host_state_crud() -> None:
    """Get and set new_compute_host_state.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    system = SystemManagement(session, auto_sync=False)
    session.get.return_value.json.return_value = {"admission_state": "approved"}
    assert system.get_new_compute_host_state() == "approved"
    session.patch.return_value.json.return_value = {"admission_state": "denied"}
    assert system.set_new_compute_host_state("denied") == "denied"


def test_get_external_connectors_rt() -> None:
    """Get external connectors.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    system = SystemManagement(session, auto_sync=False)
    session.get.return_value.json.return_value = [{"id": "c1"}]
    assert system.get_external_connectors() == [{"id": "c1"}]


def test_sync_external_connectors_rt() -> None:
    """Sync external connectors via put.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    system = SystemManagement(session, auto_sync=False)
    session.put.return_value.json.return_value = [{"id": "c1", "ok": True}]
    assert system.get_external_connectors(sync=True)[0]["ok"] is True


def test_update_external_connector_rt() -> None:
    """Update external connector.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    system = SystemManagement(session, auto_sync=False)
    session.patch.return_value.json.return_value = {"id": "x", "label": "L"}
    assert system.update_external_connector("x", {"label": "L"})["label"] == "L"


def test_delete_external_connector_rt() -> None:
    """Delete external connector.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    system = SystemManagement(session, auto_sync=False)
    system.delete_external_connector("x")
    session.delete.assert_called_once()


def test_web_session_timeout_rt() -> None:
    """Get and set web_session_timeout.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    system = SystemManagement(session, auto_sync=False)
    session.get.return_value.json.return_value = 1200
    assert system.get_web_session_timeout() == 1200
    system.set_web_session_timeout(1800)


def test_telemetry_state_get_rt() -> None:
    """Get telemetry_state.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    system = SystemManagement(session, auto_sync=False)
    session.get.return_value.json.return_value = {"opt_in": "accepted"}
    assert system.telemetry_state == OptInStatus.ACCEPTED


def test_telemetry_state_set_rt() -> None:
    """Set telemetry_state.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    system = SystemManagement(session, auto_sync=False)
    system.telemetry_state = OptInStatus.DECLINED


def test_get_telemetry_events_rt() -> None:
    """get_telemetry_events returns event list.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    system = SystemManagement(session, auto_sync=False)
    session.get.return_value.json.return_value = [{"event": "boot"}]
    assert system.get_telemetry_events() == [{"event": "boot"}]


def test_sync_compute_hosts_props() -> None:
    """sync_compute_hosts populates host properties.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    system = SystemManagement(session, auto_sync=False)
    session.get.side_effect = [
        MagicMock(
            json=MagicMock(
                return_value=[
                    {
                        "id": "h1",
                        "hostname": "host1",
                        "server_address": "10.0.0.1",
                        "is_connector": True,
                        "is_simulator": True,
                        "is_connected": True,
                        "is_synced": True,
                        "admission_state": "approved",
                        "node_counts": {"running": 0},
                    }
                ]
            )
        ),
        MagicMock(json=MagicMock(return_value=[])),
        MagicMock(
            json=MagicMock(return_value={"maintenance_mode": False, "notice": None})
        ),
    ]
    system.sync_compute_hosts()
    assert "h1" in system.compute_hosts
    host = system.compute_hosts["h1"]
    assert host.hostname == "host1"
    assert host.server_address == "10.0.0.1"
    assert host.is_connector is True
    assert host.is_simulator is True
    assert host.is_connected is True
    assert host.is_synced is True
    assert host.node_counts == {"running": 0}


def test_compute_host_mutations_rt() -> None:
    """admission_state setter, update, remove on compute host.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    system = SystemManagement(session, auto_sync=False)
    session.get.side_effect = [
        MagicMock(
            json=MagicMock(
                return_value=[
                    {
                        "id": "h1",
                        "hostname": "host1",
                        "server_address": "10.0.0.1",
                        "is_connector": False,
                        "is_simulator": False,
                        "is_connected": True,
                        "is_synced": True,
                        "admission_state": "pending",
                        "node_counts": {},
                    }
                ]
            )
        ),
        MagicMock(json=MagicMock(return_value=[])),
        MagicMock(
            json=MagicMock(return_value={"maintenance_mode": False, "notice": None})
        ),
    ]
    system.sync_compute_hosts()
    host = system.compute_hosts["h1"]
    session.patch.return_value.json.return_value = {"admission_state": "approved"}
    host.admission_state = "approved"
    host.update({"hostname": "host2"})
    host.remove()


def test_sync_system_notices_props() -> None:
    """sync_system_notices populates notice properties.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    system = SystemManagement(session, auto_sync=False)
    session.get.side_effect = [
        MagicMock(
            json=MagicMock(
                return_value=[
                    {
                        "id": "n1",
                        "level": "info",
                        "label": "lbl",
                        "content": "cnt",
                        "enabled": True,
                        "acknowledged": {},
                    }
                ]
            )
        ),
        MagicMock(
            json=MagicMock(return_value={"maintenance_mode": True, "notice": "n1"})
        ),
    ]
    system.sync_system_notices()
    assert system.maintenance_mode is True
    assert system.maintenance_notice is not None
    notice = system.system_notices["n1"]
    assert notice.level == "info"
    assert notice.label == "lbl"
    assert notice.content == "cnt"
    assert notice.enabled is True
    assert notice.acknowledged == {}
    assert notice.groups is None


def test_system_notice_mutations_rt() -> None:
    """update and remove on system notice.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    system = SystemManagement(session, auto_sync=False)
    session.get.side_effect = [
        MagicMock(
            json=MagicMock(
                return_value=[
                    {
                        "id": "n1",
                        "level": "info",
                        "label": "lbl",
                        "content": "cnt",
                        "enabled": True,
                        "acknowledged": {},
                    }
                ]
            )
        ),
        MagicMock(
            json=MagicMock(return_value={"maintenance_mode": True, "notice": "n1"})
        ),
    ]
    system.sync_system_notices()
    notice = system.system_notices["n1"]
    session.patch.return_value.json.return_value = {"content": "new"}
    notice.update({"content": "new"})
    notice.remove()
