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
"""Tests for ClientLibrary runtime branches: readiness, events, and lab management."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
import pytest

from virl2_client.exceptions import InitializationError, LabNotFound
from virl2_client.models import Lab
from virl2_client.virl2_client import (
    ClientConfig,
    ClientLibrary,
    DiagnosticsCategory,
    Version,
    _prepare_url,
)


def _make_client() -> ClientLibrary:
    """Build a lightweight ClientLibrary mock.

    :returns: Client-like object with mocked collaborators.
    """
    client = ClientLibrary.__new__(ClientLibrary)
    client._session = MagicMock()
    client._session.lock = None
    client._labs = {}
    client.username = "user"
    client.password = "pass"
    client.auto_sync = False
    client.auto_sync_interval = 1.0
    client.convergence_wait_max_iter = 1
    client.convergence_wait_time = 0
    client.resource_pool_management = MagicMock()
    client.user_management = MagicMock()
    client.event_listener = None
    client._url_for = MagicMock(side_effect=lambda endpoint, **_kwargs: endpoint)
    return client


def test_is_system_ready_retry() -> None:
    """is_system_ready retries when ready=False then returns True.

    NOTE: LLM-generated test -- verify for correctness.
    """
    client = _make_client()
    with (
        patch.object(
            client, "system_info", side_effect=[{"ready": False}, {"ready": True}]
        ),
        patch("virl2_client.virl2_client.time.sleep", return_value=None),
    ):
        assert client.is_system_ready(wait=True, max_wait=2, sleep=1)


def test_is_system_ready_502_retry() -> None:
    """is_system_ready retries on 502 then succeeds.

    NOTE: LLM-generated test -- verify for correctness.
    """
    client = _make_client()
    bad_gateway = httpx.HTTPStatusError(
        "bad",
        request=httpx.Request("GET", "https://x"),
        response=httpx.Response(status_code=httpx.codes.BAD_GATEWAY),
    )
    with (
        patch.object(client, "system_info", side_effect=[bad_gateway, {"ready": True}]),
        patch("virl2_client.virl2_client.time.sleep", return_value=None),
    ):
        assert client.is_system_ready(wait=True, max_wait=2, sleep=1)


def test_is_system_ready_non_502() -> None:
    """is_system_ready raises on non-502 HTTP error.

    NOTE: LLM-generated test -- verify for correctness.
    """
    client = _make_client()
    other_error = httpx.HTTPStatusError(
        "bad",
        request=httpx.Request("GET", "https://x"),
        response=httpx.Response(status_code=500),
    )
    with (
        patch.object(client, "system_info", side_effect=other_error),
        pytest.raises(httpx.HTTPStatusError),
    ):
        client.is_system_ready(wait=False)


def test_is_virl_1x() -> None:
    """is_virl_1x returns True for .virl, False for .yaml.

    NOTE: LLM-generated test -- verify for correctness.
    """
    client = _make_client()
    assert client.is_virl_1x(Path("x.virl")) is True
    assert client.is_virl_1x(Path("x.yaml")) is False


def test_event_listening_lifecycle() -> None:
    """start_event_listening and stop_event_listening lifecycle.

    NOTE: LLM-generated test -- verify for correctness.
    """
    client = _make_client()
    listener = MagicMock()
    listener.__bool__.return_value = False
    fake_listener_module = SimpleNamespace(
        EventListener=MagicMock(return_value=listener)
    )
    with patch.dict(
        "sys.modules", {"virl2_client.event_listening": fake_listener_module}
    ):
        client.start_event_listening()
    client.event_listener = listener
    listener.__bool__.return_value = True
    client.stop_event_listening()
    listener.stop_listening.assert_called_once()


def test_sample_labs() -> None:
    """get_sample_labs and import_sample_lab delegate to join_existing_lab.

    NOTE: LLM-generated test -- verify for correctness.
    """
    client = _make_client()
    with patch.object(
        client, "join_existing_lab", return_value=MagicMock()
    ) as join_lab:
        client._session.get.return_value.json.return_value = {"sample": {}}
        assert client.get_sample_labs() == {"sample": {}}
        client._session.put.return_value.json.return_value = "id-1"
        client.import_sample_lab("id-1")  # need to check the ID is correct
        join_lab.assert_called_with("id-1")


def test_all_labs_runtime() -> None:
    """all_labs joins and returns labs from get_lab_list.

    NOTE: LLM-generated test -- verify for correctness.
    """
    client = _make_client()
    with (
        patch.object(client, "get_lab_list", return_value=["l1", "l2"]),
        patch.object(
            client, "join_existing_lab", side_effect=[MagicMock(), MagicMock()]
        ),
    ):
        assert len(client.all_labs()) == 2


def test_local_labs_and_get() -> None:
    """local_labs filters stale; get_local_lab raises LabNotFound for missing.

    NOTE: LLM-generated test -- verify for correctness.
    """
    client = _make_client()
    stale_lab = MagicMock(_id="stale", _stale=True)
    active_lab = MagicMock(_id="active", _stale=False)
    client._labs = {"stale": stale_lab, "active": active_lab}
    assert client.local_labs() == [active_lab]
    with pytest.raises(LabNotFound):
        client.get_local_lab("missing")


def test_remove_lab_runtime() -> None:
    """remove_lab by id skips unknown; removes known lab.

    NOTE: LLM-generated test -- verify for correctness.
    """
    client = _make_client()
    joined_lab = MagicMock(spec=Lab)
    joined_lab._id = "joined"
    joined_lab._stale = False
    client._labs = {"joined": joined_lab}
    client.remove_lab("unjoined-id")
    client.remove_lab("joined")


def test_get_diagnostics_runtime() -> None:
    """get_diagnostics returns data per category; handles success and error.

    NOTE: LLM-generated test -- verify for correctness.
    """
    client = _make_client()
    ok = MagicMock()
    ok.raise_for_status.return_value = None
    ok.json.return_value = {"ok": True}
    fail = MagicMock()
    fail.raise_for_status.side_effect = httpx.HTTPStatusError(
        "err",
        request=httpx.Request("GET", "https://x"),
        response=httpx.Response(status_code=500),
    )
    client._session.get.side_effect = [ok, fail]
    result = client.get_diagnostics(
        DiagnosticsCategory.COMPUTES, DiagnosticsCategory.LABS
    )
    values = list(result.values())
    assert {"ok": True} in values
    assert any(isinstance(item, dict) and "error" in item for item in values)


def test_system_health_and_stats() -> None:
    """get_system_health and get_system_stats return session JSON.

    NOTE: LLM-generated test -- verify for correctness.
    """
    client = _make_client()
    client._session.get.side_effect = None
    client._session.get.return_value.json.return_value = {"health": "ok"}
    assert client.get_system_health() == {"health": "ok"}
    assert client.get_system_stats() == {"health": "ok"}


def test_find_labs_lab_tiles_rt() -> None:
    """find_labs_by_title queries lab_tiles dict.

    NOTE: LLM-generated test -- verify for correctness.
    """
    client = _make_client()
    client._session.get.return_value.json.return_value = {
        "lab_tiles": {
            "l1": {"lab_title": "A"},
            "l2": {"lab_title": "B"},
        }
    }
    with patch.object(
        client, "join_existing_lab", side_effect=[MagicMock()]
    ) as join_lab:
        assert len(client.find_labs_by_title("A")) == 1
        join_lab.assert_called_once_with("l1")


def test_find_labs_flat_dict_rt() -> None:
    """find_labs_by_title queries flat dict.

    NOTE: LLM-generated test -- verify for correctness.
    """
    client = _make_client()
    client._session.get.return_value.json.return_value = {
        "l3": {"lab_title": "C"},
        "l4": {"lab_title": "D"},
    }
    with patch.object(
        client, "join_existing_lab", side_effect=[MagicMock()]
    ) as join_lab:
        assert len(client.find_labs_by_title("C")) == 1
        join_lab.assert_called_once_with("l3")


def test_join_lab_no_sync() -> None:
    """join_existing_lab with sync_lab=False returns lab without sync.

    NOTE: LLM-generated test -- verify for correctness.
    """
    client = _make_client()
    client._labs = {}
    lab = client.join_existing_lab("id-5", sync_lab=False)
    assert lab.id == "id-5"
    assert lab.owner is None


def test_join_lab_already_joined() -> None:
    """join_existing_lab returns cached lab when already joined.

    NOTE: LLM-generated test -- verify for correctness.
    """
    client = _make_client()
    existing = MagicMock(spec=Lab)
    existing._stale = False
    client._labs["lab-1"] = existing
    result = client.join_existing_lab("lab-1")
    assert result is existing


@pytest.mark.parametrize("show_all", [True, False], ids=["show_all", "hide_all"])
def test_get_lab_list_show_all(show_all: bool) -> None:
    """get_lab_list returns lab IDs for show_all True and False.

    NOTE: LLM-generated test -- verify for correctness.

    :param show_all: Value for show_all query param.
    """
    client = _make_client()
    client._session.get.return_value.json.return_value = ["id-5"]
    result = client.get_lab_list(show_all=show_all)
    assert result == ["id-5"]


@pytest.mark.parametrize(
    ("url", "urlsplit_side_effect"),
    [
        ("bad://", ValueError),
        (
            "bad-host",
            [MagicMock(scheme="https", netloc="", path="x"), ValueError],
        ),
    ],
    ids=["urlsplit_value_error", "bad_host_value_error"],
)
def test_prepare_url_error_paths(url: str, urlsplit_side_effect: object) -> None:
    """_prepare_url raises InitializationError for invalid URL parsing.

    NOTE: LLM-generated test -- verify for correctness.

    :param url: Invalid URL string.
    :param urlsplit_side_effect: Side effect for urlsplit patch.
    """
    with (
        patch(
            "virl2_client.virl2_client.urlsplit",
            side_effect=urlsplit_side_effect,
        ),
        pytest.raises(InitializationError),
    ):
        _prepare_url(url, allow_http=True)


def test_client_uuid_rt() -> None:
    """Client uuid returns header value.

    NOTE: LLM-generated test -- verify for correctness.
    """
    client = _make_client()
    client._session.headers = {"X-Client-UUID": "uuid-1"}
    assert client.uuid == "uuid-1"


def test_client_logout_rt() -> None:
    """Client logout returns auth result.

    NOTE: LLM-generated test -- verify for correctness.
    """
    client = _make_client()
    client._session.auth = MagicMock()
    client._session.auth.logout.return_value = True
    assert client.logout(clear_all_sessions=True) is True


def test_client_get_host_rt() -> None:
    """Client get_host returns host from base_url.

    NOTE: LLM-generated test -- verify for correctness.
    """
    client = _make_client()
    client._session.base_url = httpx.URL("https://host.example/api/v0")
    assert client.get_host() == "host.example"


def test_check_version_invalid_str_rt() -> None:
    """check_controller_version raises InitializationError for invalid version string."""
    client = _make_client()
    client._session.get.return_value.json.return_value = {"version": "not-a-version"}
    with pytest.raises(InitializationError, match="invalid version"):
        client.check_controller_version()


def test_check_version_disabled_rt() -> None:
    """check_controller_version returns parsed Version when check_version=False."""
    client = _make_client()
    client.check_version = False
    client._session.get.return_value.json.return_value = {"version": "2.10.0"}
    result = client.check_controller_version()
    assert result == Version("2.10.0")


def test_check_version_major_mismatch_rt() -> None:
    """check_controller_version raises on major version mismatch.

    NOTE: LLM-generated test -- verify for correctness.
    """
    client = _make_client()
    client.check_version = True
    client.VERSION = Version("2.10.0")
    client._session.get.return_value.json.return_value = {"version": "3.0.0"}
    with pytest.raises(InitializationError):
        client.check_controller_version()


def test_imported_lab_no_id_rt() -> None:
    """_create_imported_lab raises ValueError when API returns no lab ID.

    NOTE: LLM-generated test -- verify for correctness.
    """
    client = _make_client()
    client._session.post.return_value.json.return_value = {}
    with pytest.raises(ValueError, match="No lab ID returned"):
        client._create_imported_lab("topo")


def test_import_path_missing_rt(tmp_path: Path) -> None:
    """import_lab_from_path raises FileNotFoundError for missing path.

    NOTE: LLM-generated test -- verify for correctness.

    :param tmp_path: Temporary directory fixture.
    """
    client = _make_client()
    with pytest.raises(FileNotFoundError):
        client.import_lab_from_path(tmp_path / "missing.yaml")


def test_create_lab_rt() -> None:
    """create_lab passes autostart and node_staging in payload.

    NOTE: LLM-generated test -- verify for correctness.
    """
    client = _make_client()
    client._session.post.return_value.json.return_value = {
        "id": "lab-1",
        "lab_title": "L1",
        "lab_description": "",
        "lab_notes": "",
        "lab_owner": "u",
    }
    client._session.get.return_value.json.return_value = [
        {"id": "u", "username": "user"}
    ]
    client.create_lab(autostart={"enabled": True}, node_staging={"enabled": True})
    assert client._session.post.call_args.kwargs["json"]["autostart"] == {
        "enabled": True
    }
    assert client._session.post.call_args.kwargs["json"]["node_staging"] == {
        "enabled": True
    }


def test_remove_lab_rt() -> None:
    """remove_lab delegates to Lab.remove and _remove_lab_local.

    NOTE: LLM-generated test -- verify for correctness.
    """
    client = _make_client()
    lab_obj = MagicMock(spec=Lab)
    client._remove_lab_local = MagicMock()
    client._remove_stale_labs = MagicMock()
    client.remove_lab(lab_obj)
    lab_obj.remove.assert_called_once()
    client._remove_lab_local.assert_called_once_with(lab_obj)


def test_remove_lab_local_keyerror_guard() -> None:
    """_remove_lab_local tolerates already-removed lab.

    NOTE: LLM-generated test -- verify for correctness.
    """
    client = _make_client()
    lab_obj = MagicMock(spec=Lab)
    lab_obj._id = "gone"
    client._remove_lab_local(lab_obj)


@pytest.mark.parametrize(
    ("status", "exc_type"),
    [
        (500, httpx.HTTPStatusError),
        (404, LabNotFound),
    ],
)
def test_join_lab_error_rt(status: int, exc_type: type) -> None:
    """join_existing_lab propagates HTTP errors as expected exception type.

    NOTE: LLM-generated test -- verify for correctness.
    """
    client = _make_client()
    err = httpx.HTTPStatusError(
        "error",
        request=httpx.Request("GET", "https://x"),
        response=httpx.Response(status_code=status),
    )
    client._session.get.side_effect = err
    with pytest.raises(exc_type):
        client.join_existing_lab(f"lab-{status}")


def test_join_lab_sets_sync_topology_time() -> None:
    """join_existing_lab sets _last_sync_topology_time after import."""
    client = _make_client()
    topology = {
        "lab": {"title": "T", "description": "", "notes": "", "owner": None},
        "nodes": [],
        "links": [],
        "annotations": [],
        "smart_annotations": [],
    }
    client._session.get.return_value.json.return_value = topology
    lab = client.join_existing_lab("lab-new")
    assert lab._last_sync_topology_time > 0
    assert lab._initialized is True


def test_join_lab_no_duplicate_topology_fetch() -> None:
    """nodes() should not re-fetch topology right after join_existing_lab."""
    client = _make_client()
    client.auto_sync = True
    client.auto_sync_interval = 1.0
    topology = {
        "lab": {"title": "T", "description": "", "notes": "", "owner": None},
        "nodes": [],
        "links": [],
        "annotations": [],
        "smart_annotations": [],
    }
    client._session.get.return_value.json.return_value = topology
    lab = client.join_existing_lab("lab-sync")
    client._session.get.reset_mock()
    with patch.object(lab, "_sync_topology") as sync_topo:
        lab.nodes()
        sync_topo.assert_not_called()


def test_events_init_starts_listener(monkeypatch: pytest.MonkeyPatch) -> None:
    """Client init with events=True starts event listener.

    NOTE: LLM-generated test -- verify for correctness.

    :param monkeypatch: Pytest fixture for temporary attribute patching.
    """
    monkeypatch.setattr(
        ClientLibrary, "check_controller_version", lambda _self: Version("2.10.0")
    )
    monkeypatch.setattr(
        ClientLibrary, "_make_test_auth_call", lambda _self, _new_auth: None
    )
    started = {"called": False}
    monkeypatch.setattr(
        ClientLibrary,
        "start_event_listening",
        lambda _self: started.__setitem__("called", True),
    )
    cl = ClientLibrary("https://localhost", "u", "p", events=True, check_version=False)
    assert cl.auto_sync is False
    assert started["called"] is True


def test_auth_call_propagates_500() -> None:
    """_make_test_auth_call propagates HTTPStatusError on 500.

    NOTE: LLM-generated test -- verify for correctness.
    """
    original_make_test_auth_call = ClientLibrary._make_test_auth_call
    failing = _make_client()
    non_403 = httpx.HTTPStatusError(
        "error",
        request=httpx.Request("GET", "https://x"),
        response=httpx.Response(status_code=500),
    )
    failing._url_for = MagicMock(return_value="auth")
    with (
        patch.object(failing._session, "get", side_effect=non_403),
        pytest.raises(httpx.HTTPStatusError),
    ):
        original_make_test_auth_call(failing, new_auth=False)


def test_config_populate_inputs_uses_jwtoken(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cover long auth-input branch that stores a JWT token.

    NOTE: LLM-generated test -- verify for correctness.

    :param monkeypatch: Pytest fixture for replacing interactive input.
    """
    config = {
        "url": None,
        "username": None,
        "password": None,
        "jwtoken": None,
        "ssl_verify": True,
    }
    values = iter(["https://host", "x" * 40])
    monkeypatch.setattr("builtins.input", lambda _: next(values))
    ClientConfig._populate_from_inputs(config)
    assert config["jwtoken"] == "x" * 40
