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
"""Tests for ClientLibrary authentication, lab management, and diagnostics."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx

from virl2_client.exceptions import APIError, LabNotFound
from virl2_client.models import Lab
from virl2_client.virl2_client import (
    ClientLibrary,
    DiagnosticsCategory,
    InitializationError,
    Version,
)

CURRENT_VERSION = ClientLibrary.VERSION.version_str
FAKE_URL = "https://0.0.0.0/fake_url/"


@pytest.mark.parametrize("title", [None, "new_title"], ids=["default", "custom_title"])
def test_import_lab_from_path_virl(
    client_library_server_current: MagicMock,
    mocked_session: MagicMock,
    tmp_path: Path,
    title: str | None,
) -> None:
    """Import lab from .virl file path; optional title as query param.

    :param client_library_server_current: Patched system_info fixture.
    :param mocked_session: Mocked HTTP session fixture.
    :param tmp_path: Temporary directory fixture.
    :param title: Optional lab title for import.
    """
    _ = client_library_server_current, mocked_session
    cl = ClientLibrary(url=FAKE_URL, username="test", password="pa$$")
    (tmp_path / "topology.virl").write_text("<?xml version='1.0' encoding='UTF-8'?>")
    kwargs = {"title": title} if title is not None else {}
    with patch.object(Lab, "sync"):
        lab = cl.import_lab_from_path(
            path=(tmp_path / "topology.virl").as_posix(),
            **kwargs,
        )
    assert lab.title is not None
    assert lab._url_for("lab").startswith("labs/")
    expected_params = {"title": title} if title else None
    cl._session.post.assert_called_once_with(
        "import/virl-1x",
        params=expected_params,
        content="<?xml version='1.0' encoding='UTF-8'?>",
    )


@respx.mock
def test_new_auth_url_used_with_cml_2_10(
    client_library_server_current: MagicMock,
) -> None:
    """Verify new auth URL is used with CML 2.10.x controllers.

    With client 2.10.0, _make_test_auth_call uses "authentication" not "authok".

    :param client_library_server_current: Patched system_info fixture.
    """

    _ = client_library_server_current

    respx.post(f"{FAKE_URL}api/v0/authenticate").respond(json="BOGUS_TOKEN")
    new_auth_route = respx.get(f"{FAKE_URL}api/v0/authentication").respond(
        200,
        json={
            "username": "username",
            "admin": True,
            "id": "6c7dd461-1cbe-428f-bdd5-545a0d766ed7",
            "token": "BOGUS_TOKEN",
            "error": None,
        },
    )
    old_auth_route = respx.get(f"{FAKE_URL}api/v0/authok").respond(404)

    ClientLibrary(url=FAKE_URL, username="test", password="pa$$")

    assert new_auth_route.called
    assert not old_auth_route.called


@respx.mock
def test_auth_and_reauth_token(client_library_server_current: MagicMock) -> None:
    """Verify auth token flow: initial failure, re-auth, and subsequent success.

    :param client_library_server_current: Patched system_info fixture.
    """

    def initial_different_response(
        initial: httpx.Response, subsequent: httpx.Response | None = None
    ) -> Iterator[httpx.Response]:
        """Yield one initial response, then yield the subsequent response forever.

        :param initial: First response emitted exactly once.
        :param subsequent: Response repeatedly emitted after first yield.
        :returns: Infinite response iterator with first-response override.
        """
        _ = client_library_server_current
        if subsequent is None:
            subsequent = httpx.Response(200)
        yield initial
        while True:
            yield subsequent

    # mock failed and successful authentication
    side_effect = initial_different_response(
        httpx.Response(403), httpx.Response(200, json="7bbcan78a98bch7nh3cm7hao3nc7")
    )
    respx.post(f"{FAKE_URL}api/v0/authenticate").side_effect = side_effect
    side_effect = initial_different_response(
        httpx.Response(401),
        httpx.Response(
            200,
            json={
                "username": "username",
                "admin": True,
                "id": "6c7dd461-1cbe-428f-bdd5-545a0d766ed7",
                "token": "BOGUS_TOKEN",
                "error": None,
            },
        ),
    )
    respx.get(f"{FAKE_URL}api/v0/authentication").side_effect = side_effect

    # mock get labs
    respx.get(f"{FAKE_URL}api/v0/labs").respond(json=[])

    with pytest.raises(InitializationError):
        # Test returns custom exception when instructed to raise on failure
        ClientLibrary(
            url=FAKE_URL,
            username="test",
            password="pa$$",
            raise_for_auth_failure=True,
        )

    cl = ClientLibrary(url=FAKE_URL, username="test", password="pa$$")

    cl.all_labs()

    assert respx.calls[0].request.url == f"{FAKE_URL}api/v0/authenticate"
    assert json.loads(respx.calls[0].request.content) == {
        "username": "test",
        "password": "pa$$",
    }
    assert respx.calls[1].request.url == f"{FAKE_URL}api/v0/authenticate"
    assert respx.calls[2].request.url == f"{FAKE_URL}api/v0/authentication"
    assert respx.calls[3].request.url == f"{FAKE_URL}api/v0/authenticate"
    assert respx.calls[4].request.url == f"{FAKE_URL}api/v0/authentication"
    assert respx.calls[5].request.url == f"{FAKE_URL}api/v0/labs"
    assert respx.calls.call_count == 6


@respx.mock
def test_jwt_valid_token_skips_auth(
    client_library_server_current: MagicMock,
) -> None:
    """Skip password auth when a valid JWT token is provided.

    NOTE: LLM-generated test -- verify for correctness.

    :param client_library_server_current: Patched system_info fixture.
    """
    _ = client_library_server_current

    auth_route = respx.get(f"{FAKE_URL}api/v0/authentication").respond(
        200,
        json={
            "username": "jwt_user",
            "admin": False,
            "id": "6c7dd461-1cbe-428f-bdd5-545a0d766ed7",
            "token": "VALID_TOKEN",
            "error": None,
        },
    )
    password_auth_route = respx.post(f"{FAKE_URL}api/v0/authenticate").respond(
        json="SHOULD_NOT_BE_USED"
    )
    respx.get(f"{FAKE_URL}api/v0/labs").respond(json=[])

    cl = ClientLibrary(url=FAKE_URL, jwtoken="VALID_TOKEN")
    cl.all_labs()

    assert auth_route.called
    assert not password_auth_route.called


@respx.mock
def test_jwt_expired_reauths(
    client_library_server_current: MagicMock,
) -> None:
    """Re-authenticate with username/password when JWT is expired.

    NOTE: LLM-generated test -- verify for correctness.

    :param client_library_server_current: Patched system_info fixture.
    """
    _ = client_library_server_current

    auth_route = respx.get(f"{FAKE_URL}api/v0/authentication")
    auth_route.side_effect = [
        httpx.Response(401),
        httpx.Response(
            200,
            json={
                "username": "test",
                "admin": True,
                "id": "6c7dd461-1cbe-428f-bdd5-545a0d766ed7",
                "token": "REFRESHED_TOKEN",
                "error": None,
            },
        ),
    ]
    password_auth_route = respx.post(f"{FAKE_URL}api/v0/authenticate").respond(
        json="REFRESHED_TOKEN"
    )

    ClientLibrary(
        url=FAKE_URL,
        username="test",
        password="pa$$",
        jwtoken="EXPIRED_TOKEN",
    )

    assert auth_route.called
    assert auth_route.call_count == 2
    assert password_auth_route.called
    assert json.loads(password_auth_route.calls[0].request.content) == {
        "username": "test",
        "password": "pa$$",
    }


@respx.mock
def test_jwt_reauth_no_creds_fails(
    client_library_server_current: MagicMock,
    reset_env: None,
) -> None:
    """Raise APIError when expired JWT cannot be refreshed without credentials.

    NOTE: LLM-generated test -- verify for correctness.

    :param client_library_server_current: Patched system_info fixture.
    :param reset_env: Fixture clearing VIRL2 env vars.
    """
    _ = client_library_server_current, reset_env

    auth_route = respx.get(f"{FAKE_URL}api/v0/authentication").respond(401)
    password_auth_route = respx.post(f"{FAKE_URL}api/v0/authenticate").respond(
        json="SHOULD_NOT_BE_USED"
    )

    with pytest.raises(
        APIError,
        match="JWT token expired and automatic re-authentication is not possible",
    ):
        ClientLibrary(url=FAKE_URL, jwtoken="EXPIRED_TOKEN")

    assert auth_route.called
    assert auth_route.call_count == 1
    assert not password_auth_route.called


@respx.mock
def test_old_auth_url_used_with_cml_2_9(
    client_library_server_2_9_0: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify legacy auth URL is used with CML 2.9.x controller and 2.9.x client.

    :param client_library_server_2_9_0: Patched system_info for 2.9.0.
    :param monkeypatch: Pytest monkeypatch fixture.
    """

    _ = client_library_server_2_9_0

    monkeypatch.setattr(ClientLibrary, "VERSION", Version("2.9.0"))

    respx.post(f"{FAKE_URL}api/v0/authenticate").respond(json="BOGUS_TOKEN")
    old_auth_route = respx.get(f"{FAKE_URL}api/v0/authok").respond(200, text="OK")
    new_auth_route = respx.get(f"{FAKE_URL}api/v0/authentication").respond(404)

    ClientLibrary(url=FAKE_URL, username="test", password="pa$$")

    assert old_auth_route.called
    assert not new_auth_route.called


@respx.mock
def test_new_auth_url_fails_with_cml_2_9(
    client_library_server_2_9_0: MagicMock,
) -> None:
    """Negative test: new auth URL does not work with CML 2.9.x.

    With the current client version (2.10.0) and a 2.9 controller, only the
    legacy "authok" endpoint is expected to exist server-side.

    :param client_library_server_2_9_0: Patched system_info for 2.9.0.
    """

    _ = client_library_server_2_9_0

    respx.post(f"{FAKE_URL}api/v0/authenticate").respond(json="BOGUS_TOKEN")
    old_auth_route = respx.get(f"{FAKE_URL}api/v0/authok").respond(200, text="OK")
    new_auth_route = respx.get(f"{FAKE_URL}api/v0/authentication").respond(404)

    ClientLibrary(url=FAKE_URL, username="test", password="pa$$")

    assert old_auth_route.called
    assert not new_auth_route.called


@respx.mock
def test_old_auth_url_deprecated_with_cml_2_10(
    client_library_server_current: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Negative test: legacy auth URL should be considered deprecated on
    CML 2.10.x controllers.  This is a theoretical scenario in case it is not
    forbidden to connect to a newer controller with an older client anymore.

    This simulates using an older client (2.9.x) against a 2.10 controller,
    where the "authok" endpointis deprecated. _make_test_auth_call will
    select the "legacy" endpoint, which still works, but eventually won't.

    :param client_library_server_current: Patched system_info fixture.
    :param monkeypatch: Pytest monkeypatch fixture.
    """

    _ = client_library_server_current

    monkeypatch.setattr(ClientLibrary, "VERSION", Version("2.9.0"))

    respx.post(f"{FAKE_URL}api/v0/authenticate").respond(json="BOGUS_TOKEN")
    old_auth_route = respx.get(f"{FAKE_URL}api/v0/authok").respond(200, text="OK")
    new_auth_route = respx.get(f"{FAKE_URL}api/v0/authentication").respond(
        200,
        json={
            "username": "username",
            "admin": True,
            "id": "6c7dd461-1cbe-428f-bdd5-545a0d766ed7",
            "token": "BOGUS_TOKEN",
            "error": None,
        },
    )

    ClientLibrary(url=FAKE_URL, username="test", password="pa$$")

    assert new_auth_route.called
    assert not old_auth_route.called


def test_incompatible_version(
    client_library_server_2_0_0: MagicMock,
) -> None:
    """ClientLibrary raises InitializationError for unsupported controller version.

    :param client_library_server_2_0_0: Patched system_info for 2.0.0.
    """
    _ = client_library_server_2_0_0
    with pytest.raises(InitializationError) as err:
        ClientLibrary("somehost", "virl2", password="virl2")
    assert str(err.value) == (
        "Unsupported minor version (only last 3 minor versions are supported). "
        f"Client {ClientLibrary.VERSION}, controller 2.0.0."
    )


def test_exact_version_no_warn(
    client_library_server_current: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """No version warning when client and controller versions match.

    NOTE: LLM-generated test -- verify for correctness.

    :param client_library_server_current: Patched system_info fixture.
    :param caplog: Pytest log capture fixture.
    """
    _ = client_library_server_current
    with caplog.at_level(logging.WARNING):
        ClientLibrary("somehost", "virl2", password="virl2")
    assert "Please ensure the client version is compatible" not in caplog.text


def test_client_minor_version_lt_warn(
    client_library_server_2_19_0: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """Version warning when client minor is less than controller.

    :param client_library_server_2_19_0: Patched system_info for 2.19.0.
    :param caplog: Pytest log capture fixture.
    """
    _ = client_library_server_2_19_0
    with caplog.at_level(logging.WARNING):
        ClientLibrary("somehost", "virl2", password="virl2")
    assert (
        f"Please ensure the client version is compatible with the controller version. "
        f"Client {CURRENT_VERSION}, controller 2.19.0." in caplog.text
    )


def test_import_lab_rejects_offline_argument(
    client_library_server_current: MagicMock,
    mocked_session: MagicMock,
    tmp_path: Path,
    test_data_dir: Path,
) -> None:
    """import_lab with offline=True emits deprecation warning.

    :param client_library_server_current: Patched system_info fixture.
    :param mocked_session: Mocked HTTP session fixture.
    :param tmp_path: Temporary directory fixture.
    :param test_data_dir: Path to test data fixtures.
    """
    _ = client_library_server_current, mocked_session, tmp_path
    client_library = ClientLibrary(url=FAKE_URL, username="test", password="pa$$")
    topology_file_path = test_data_dir / "sample_topology.json"
    with open(topology_file_path) as fh:
        topology_file = fh.read()
        with pytest.raises(TypeError):
            client_library.import_lab(topology_file, "topology-v0_0_4", offline=True)


def test_convergence_params_to_lab(
    client_library_server_current: MagicMock, mocked_session: MagicMock
) -> None:
    """Convergence params flow from client to lab.

    NOTE: LLM-generated test -- verify for correctness.

    :param client_library_server_current: Patched system_info fixture.
    :param mocked_session: Mocked HTTP session fixture.
    """
    _ = client_library_server_current, mocked_session
    max_iter = 2
    max_time = 1
    cl = ClientLibrary(
        url=FAKE_URL,
        username="test",
        password="pa$$",
        convergence_wait_max_iter=max_iter,
        convergence_wait_time=max_time,
    )
    lab = cl.create_lab()
    assert lab.wait_max_iterations == max_iter
    assert lab.wait_time == max_time


def test_convergence_timeout(
    client_library_server_current: MagicMock, mocked_session: MagicMock
) -> None:
    """wait_until_lab_converged raises RuntimeError when max tries exceeded.

    NOTE: LLM-generated test -- verify for correctness.

    :param client_library_server_current: Patched system_info fixture.
    :param mocked_session: Mocked HTTP session fixture.
    """
    _ = client_library_server_current, mocked_session
    cl = ClientLibrary(
        url=FAKE_URL,
        username="test",
        password="pa$$",
        convergence_wait_max_iter=2,
        convergence_wait_time=1,
    )
    lab = cl.create_lab()
    with patch.object(Lab, "has_converged", return_value=False):
        with pytest.raises(RuntimeError) as err:
            lab.wait_until_lab_converged()
        assert "has not converged, maximum tries 2 exceeded" in err.value.args[0]


def test_convergence_override(
    client_library_server_current: MagicMock, mocked_session: MagicMock
) -> None:
    """wait_until_lab_converged accepts max_iterations override on call.

    NOTE: LLM-generated test -- verify for correctness.

    :param client_library_server_current: Patched system_info fixture.
    :param mocked_session: Mocked HTTP session fixture.
    """
    _ = client_library_server_current, mocked_session
    cl = ClientLibrary(
        url=FAKE_URL,
        username="test",
        password="pa$$",
        convergence_wait_max_iter=2,
        convergence_wait_time=1,
    )
    lab = cl.create_lab()
    with patch.object(Lab, "has_converged", return_value=False):
        with pytest.raises(RuntimeError) as err:
            lab.wait_until_lab_converged(max_iterations=1)
        assert "has not converged, maximum tries 1 exceeded" in err.value.args[0]


@pytest.mark.parametrize(
    "categories",
    [
        [DiagnosticsCategory.ALL],
        [DiagnosticsCategory.COMPUTES],
        [DiagnosticsCategory.LABS, DiagnosticsCategory.SERVICES],
        [DiagnosticsCategory.ALL, DiagnosticsCategory.COMPUTES],
    ],
)
@pytest.mark.parametrize("valid", [True, False])
def test_get_diagnostics_paths(
    client_library: ClientLibrary, categories: list[DiagnosticsCategory], valid: bool
) -> None:
    """get_diagnostics returns data per category; handles valid and invalid responses.

    :param client_library: ClientLibrary instance with mocked lab API.
    :param categories: Diagnostics categories to request.
    :param valid: Whether API returns 200 (True) or 404 (False).
    """
    data = {"data": "sample"}
    return_value = httpx.Response(200, json=data) if valid else httpx.Response(404)

    expected_categories = categories
    if DiagnosticsCategory.ALL in categories:
        expected_categories = list(DiagnosticsCategory)[1:]

    with respx.mock(base_url="https://0.0.0.0/api/v0/") as respx_mock:
        for category in expected_categories:
            respx_mock.get(f"diagnostics/{category.value}").mock(
                return_value=return_value
            )
        diagnostics_data = client_library.get_diagnostics(*categories)

    for category in expected_categories:
        if not valid:
            data = {"error": f"Failed to fetch {category.value} diagnostics"}
        assert diagnostics_data[category.value] == data


def test_get_diagnostics_requires_categories(client_library: ClientLibrary) -> None:
    """Raise ValueError when no diagnostics category is provided.

    NOTE: LLM-generated test -- verify for correctness.

    :param client_library: ClientLibrary instance with mocked lab API.
    """
    with pytest.raises(ValueError, match="No diagnostics category provided"):
        client_library.get_diagnostics()


def test_get_diagnostics_warns_user_list(
    client_library: ClientLibrary,
) -> None:
    """get_diagnostics emits deprecation warning for USER_LIST category.

    NOTE: LLM-generated test -- verify for correctness.

    :param client_library: ClientLibrary instance with mocked lab API.
    """
    with respx.mock(base_url="https://0.0.0.0/api/v0/") as respx_mock:
        respx_mock.get("diagnostics/user_list").respond(200, json={"users": []})
        with pytest.deprecated_call(match="DiagnosticsCategory.USER_LIST"):
            diagnostics_data = client_library.get_diagnostics(
                DiagnosticsCategory.USER_LIST
            )

    assert diagnostics_data["user_list"] == {"users": []}


@respx.mock
def test_system_controller_compute_load(
    client_library_server_current: MagicMock,
) -> None:
    """system_management.controller returns connector host from compute_hosts.

    NOTE: LLM-generated test -- verify for correctness.

    :param client_library_server_current: Patched system_info fixture.
    """
    _ = client_library_server_current
    respx.post("https://localhost/api/v0/authenticate").respond(json="fake_token")
    respx.get("https://localhost/api/v0/authentication").respond(
        200,
        json={
            "username": "username",
            "id": "6c7dd461-1cbe-428f-bdd5-545a0d766ed7",
            "token": "BOGUS_TOKEN",
            "admin": True,
            "error": None,
        },
    )

    compute_hosts_response = [
        {
            "id": "controller-123",
            "hostname": "controller-host",
            "server_address": "192.168.1.100",
            "is_connector": True,
            "is_simulator": False,
            "is_connected": True,
            "is_synced": True,
            "admission_state": "approved",
            "node_counts": {"deployed": 0, "running": 0, "orphans": 0},
        }
    ]

    respx.get("https://localhost/api/v0/system/compute_hosts").respond(
        json=compute_hosts_response
    )

    client_library = ClientLibrary(
        "https://localhost", "user", "pass", ssl_verify=False
    )

    controller = client_library.system_management.controller

    assert controller.is_connector is True
    assert controller.hostname == "controller-host"


def test_create_lab_missing_id_raises_key_error(
    client_library_server_current: MagicMock, mocked_session: MagicMock
) -> None:
    """create_lab raises KeyError when API returns no lab ID.

    NOTE: LLM-generated test -- verify for correctness.

    :param client_library_server_current: Patched system_info fixture.
    :param mocked_session: Mocked HTTP session fixture.
    :raises KeyError: If the API response does not include id.
    """
    _ = client_library_server_current, mocked_session
    cl = ClientLibrary(url=FAKE_URL, username="test", password="pa$$")
    cl._session.post.return_value.json.return_value = {"lab_title": "no-id"}

    with pytest.raises(KeyError, match="id"):
        cl.create_lab(title="broken")


def test_import_lab_from_path_missing_file_raises(
    client_library_server_current: MagicMock, mocked_session: MagicMock
) -> None:
    """import_lab_from_path raises FileNotFoundError for missing path.

    NOTE: LLM-generated test -- verify for correctness.

    :param client_library_server_current: Patched system_info fixture.
    :param mocked_session: Mocked HTTP session fixture.
    """
    _ = client_library_server_current, mocked_session
    cl = ClientLibrary(url=FAKE_URL, username="test", password="pa$$")

    with pytest.raises(FileNotFoundError):
        cl.import_lab_from_path("/definitely/missing/topology.virl")


def test_get_lab_list_show_all_sends_query_param(
    client_library_server_current: MagicMock, mocked_session: MagicMock
) -> None:
    """get_lab_list with show_all=True passes query param to API.

    NOTE: LLM-generated test -- verify for correctness.

    :param client_library_server_current: Patched system_info fixture.
    :param mocked_session: Mocked HTTP session fixture.
    """
    _ = client_library_server_current, mocked_session
    cl = ClientLibrary(url=FAKE_URL, username="test", password="pa$$")
    cl._session.get.return_value.json.return_value = ["lab-a"]

    result = cl.get_lab_list(show_all=True)

    assert result == ["lab-a"]
    cl._session.get.assert_called_with("labs", params={"show_all": True})


def test_check_controller_version_major_mismatch(
    client_library_server_current: MagicMock,
    mocked_session: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Raise when controller major version is incompatible.

    NOTE: LLM-generated test -- verify for correctness.

    :param client_library_server_current: Patched current-version fixture.
    :param mocked_session: Mocked HTTP session fixture.
    :param monkeypatch: Fixture for temporary attribute patching.
    """
    _ = client_library_server_current, mocked_session
    cl = ClientLibrary(url=FAKE_URL, username="test", password="pa$$")
    monkeypatch.setattr(cl, "system_info", lambda: {"version": "99.0.0"})

    with pytest.raises(InitializationError, match="Major version mismatch"):
        cl.check_controller_version()


@respx.mock
def test_join_existing_lab_404_not_found(
    client_library_server_current: MagicMock,
) -> None:
    """Raise LabNotFound when joining a missing lab returns 404.

    NOTE: LLM-generated test -- verify for correctness.

    :param client_library_server_current: Patched current-version fixture.
    :raises LabNotFound: When the requested lab is not found on the server.
    """
    _ = client_library_server_current
    lab_id = "missing-lab"
    respx.post(f"{FAKE_URL}api/v0/authenticate").respond(json="BOGUS_TOKEN")
    respx.get(f"{FAKE_URL}api/v0/authentication").respond(
        200,
        json={
            "username": "username",
            "admin": True,
            "id": "6c7dd461-1cbe-428f-bdd5-545a0d766ed7",
            "token": "BOGUS_TOKEN",
            "error": None,
        },
    )
    respx.get(f"{FAKE_URL}api/v0/labs/{lab_id}/topology").respond(
        status_code=404, text=f"Lab not found: {lab_id}"
    )
    cl = ClientLibrary(url=FAKE_URL, username="test", password="pa$$")

    with pytest.raises(LabNotFound):
        cl.join_existing_lab(lab_id)


def test_client_uuid(
    client_library_server_current: MagicMock, mocked_session: MagicMock
) -> None:
    """Client uuid property returns X-Client-UUID header value.

    NOTE: LLM-generated test -- verify for correctness.

    :param client_library_server_current: Session fixture setup.
    :param mocked_session: Session mock fixture.
    """
    _ = client_library_server_current, mocked_session
    cl = ClientLibrary(url=FAKE_URL, username="test", password="pa$$")
    cl._session.headers = {"X-Client-UUID": "uuid-1"}
    assert cl.uuid == "uuid-1"


def test_client_logout(
    client_library_server_current: MagicMock, mocked_session: MagicMock
) -> None:
    """Client logout returns True when auth.logout succeeds.

    NOTE: LLM-generated test -- verify for correctness.

    :param client_library_server_current: Session fixture setup.
    :param mocked_session: Session mock fixture.
    """
    _ = client_library_server_current, mocked_session
    cl = ClientLibrary(url=FAKE_URL, username="test", password="pa$$")
    cl._session.auth = MagicMock()
    cl._session.auth.logout.return_value = True
    assert cl.logout(clear_all_sessions=True) is True


def test_client_get_host(
    client_library_server_current: MagicMock, mocked_session: MagicMock
) -> None:
    """Client get_host returns hostname from base URL.

    NOTE: LLM-generated test -- verify for correctness.

    :param client_library_server_current: Session fixture setup.
    :param mocked_session: Session mock fixture.
    """
    _ = client_library_server_current, mocked_session
    cl = ClientLibrary(url=FAKE_URL, username="test", password="pa$$")
    cl._session.base_url = httpx.URL("https://demo.local:443/api/v0/")
    assert cl.get_host() == "demo.local"


def test_create_lab_options(
    client_library_server_current: MagicMock, mocked_session: MagicMock
) -> None:
    """create_lab passes autostart and node_staging in payload.

    NOTE: LLM-generated test -- verify for correctness.

    :param client_library_server_current: Session fixture setup.
    :param mocked_session: Session mock fixture.
    """
    _ = client_library_server_current, mocked_session
    cl = ClientLibrary(url=FAKE_URL, username="test", password="pa$$")
    cl._session.post.return_value.json.return_value = {
        "id": "new1",
        "lab_title": "L1",
        "lab_description": "",
        "lab_notes": "",
        "lab_owner": "user-1",
    }
    cl.create_lab(autostart={"enabled": True}, node_staging={"enabled": True})
    body = cl._session.post.call_args.kwargs["json"]
    assert body["autostart"] == {"enabled": True}
    assert body["node_staging"] == {"enabled": True}


def test_check_version_skip_paths(
    client_library_server_current: MagicMock, mocked_session: MagicMock
) -> None:
    """Skip version check when check_version is False.

    NOTE: LLM-generated test -- verify for correctness.

    :param client_library_server_current: Session fixture setup.
    :param mocked_session: Session mock fixture.
    """
    _ = client_library_server_current, mocked_session
    cl = ClientLibrary(url=FAKE_URL, username="test", password="pa$$")
    cl.check_version = False
    with patch.object(cl, "system_info", return_value={"version": "2.0.0"}):
        result = cl.check_controller_version()
        assert result == Version("2.0.0")
    with (
        patch.object(cl, "system_info", return_value={"version": object()}),
        pytest.raises(InitializationError, match="invalid version"),
    ):
        cl.check_controller_version()


def test_join_lab_propagates_error(
    client_library_server_current: MagicMock, mocked_session: MagicMock
) -> None:
    """join_existing_lab propagates HTTPStatusError on 500.

    NOTE: LLM-generated test -- verify for correctness.

    :param client_library_server_current: Session fixture setup.
    :param mocked_session: Session mock fixture.
    """
    _ = client_library_server_current, mocked_session
    cl = ClientLibrary(url=FAKE_URL, username="test", password="pa$$")
    request = httpx.Request("GET", "https://x")
    cl._session.get.side_effect = httpx.HTTPStatusError(
        "boom",
        request=request,
        response=httpx.Response(status_code=500, request=request),
    )
    with pytest.raises(httpx.HTTPStatusError):
        cl.join_existing_lab("missing", sync_lab=True)
