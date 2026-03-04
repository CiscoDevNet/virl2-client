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

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock, Mock, call, patch

import httpx
import pytest
import respx

from virl2_client.exceptions import APIError
from virl2_client.models import Lab
from virl2_client.virl2_client import (
    ClientLibrary,
    DiagnosticsCategory,
    InitializationError,
    Version,
)

CURRENT_VERSION = ClientLibrary.VERSION.version_str
FAKE_URL = "https://0.0.0.0/fake_url/"


# TODO: split into multiple test modules, by feature.
@pytest.fixture
def reset_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear VIRL2-related environment variables for isolated init tests.

    :param monkeypatch: Pytest monkeypatch fixture.
    :returns: None.
    """
    env_vars = [
        "VIRL2_URL",
        "VIRL_HOST",
        "VIRL2_USER",
        "VIRL_USERNAME",
        "VIRL2_PASS",
        "VIRL_PASSWORD",
        "VIRL2_JWT",
    ]

    for key in env_vars:
        monkeypatch.delenv(key, raising=False)


def test_import_lab_from_path_virl(
    client_library_server_current: MagicMock,
    mocked_session: MagicMock,
    tmp_path: Path,
) -> None:
    """Import lab from .virl file path and verify POST to import/virl-1x.

    :param client_library_server_current: Patched system_info fixture.
    :param mocked_session: Mocked HTTP session fixture.
    :param tmp_path: Temporary directory fixture.
    """
    _ = client_library_server_current, mocked_session
    cl = ClientLibrary(url=FAKE_URL, username="test", password="pa$$")
    Lab.sync = Mock()

    (tmp_path / "topology.virl").write_text("<?xml version='1.0' encoding='UTF-8'?>")
    lab = cl.import_lab_from_path(path=(tmp_path / "topology.virl").as_posix())

    assert lab.title is not None
    assert lab._url_for("lab").startswith("labs/")

    cl._session.post.assert_called_once_with(
        "import/virl-1x",
        params=None,
        content="<?xml version='1.0' encoding='UTF-8'?>",
    )
    cl._session.post.assert_called_once()


def test_import_lab_from_path_virl_title(
    client_library_server_current: MagicMock,
    mocked_session: MagicMock,
    tmp_path: Path,
) -> None:
    """Import lab with custom title passed as query parameter.

    :param client_library_server_current: Patched current-version fixture.
    :param mocked_session: Mocked HTTP session fixture.
    :param tmp_path: Temporary directory for generated VIRL file.
    :returns: ``None``.
    """
    _ = client_library_server_current, mocked_session
    cl = ClientLibrary(url=FAKE_URL, username="test", password="pa$$")
    Lab.sync = Mock()
    new_title = "new_title"
    (tmp_path / "topology.virl").write_text("<?xml version='1.0' encoding='UTF-8'?>")
    lab = cl.import_lab_from_path(
        path=(tmp_path / "topology.virl").as_posix(), title=new_title
    )
    assert lab.title is not None
    assert lab._url_for("lab").startswith("labs/")

    cl._session.post.assert_called_once_with(
        "import/virl-1x",
        params={"title": new_title},
        content="<?xml version='1.0' encoding='UTF-8'?>",
    )


def test_ssl_certificate(
    client_library_server_current: MagicMock, mocked_session: MagicMock
) -> None:
    """Use constructor-provided SSL CA bundle path for requests.

    :param client_library_server_current: Patched current-version fixture.
    :param mocked_session: Mocked HTTP session fixture.
    :returns: ``None``.
    """
    _ = client_library_server_current, mocked_session
    cl = ClientLibrary(
        url=FAKE_URL,
        username="test",
        password="pa$$",
        ssl_verify="/home/user/cert.pem",
    )
    cl.is_system_ready(wait=True)

    assert cl._ssl_verify == "/home/user/cert.pem"
    assert cl._session.mock_calls[0] == call.get("authentication")


def test_ssl_certificate_from_env_variable(
    client_library_server_current: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    mocked_session: MagicMock,
) -> None:
    """Use ``CA_BUNDLE`` environment variable for SSL verification.

    :param client_library_server_current: Patched current-version fixture.
    :param monkeypatch: Fixture for temporary environment mutation.
    :param mocked_session: Mocked HTTP session fixture.
    :returns: ``None``.
    """
    _ = client_library_server_current, mocked_session
    monkeypatch.setenv("CA_BUNDLE", "/home/user/cert.pem")
    cl = ClientLibrary(url=FAKE_URL, username="test", password="pa$$")

    assert cl.is_system_ready()
    assert cl._ssl_verify == "/home/user/cert.pem"
    assert cl._session.mock_calls[0] == call.get("authentication")


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
        initial: httpx.Response, subsequent: httpx.Response = httpx.Response(200)
    ) -> Iterator[httpx.Response]:
        """Yield one initial response, then yield the subsequent response forever.

        :param initial: First response emitted exactly once.
        :param subsequent: Response repeatedly emitted after first yield.
        :returns: Infinite response iterator with first-response override.
        """
        _ = client_library_server_current
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
def test_jwt_only_valid_token_does_not_call_password_auth(
    client_library_server_current: MagicMock,
):
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
def test_jwt_expired_with_credentials_reauths_using_password_auth(
    client_library_server_current: MagicMock,
):
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
def test_jwt_reauth_without_credentials_fails_cleanly(
    client_library_server_current: MagicMock,
    reset_env: None,
):
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


def test_client_library_init_allow_http(
    client_library_server_current: MagicMock,
) -> None:
    """Client accepts http:// URL when allow_http=True.

    :param client_library_server_current: Patched system_info fixture.
    """
    _ = client_library_server_current
    cl = ClientLibrary("http://somehost", "virl2", "virl2", allow_http=True)
    assert cl._session.base_url.scheme == "http"
    assert cl._session.base_url.host == "somehost"
    assert cl._session.base_url.port is None
    assert cl._session.base_url.path.endswith("/api/v0/")
    assert cl.username == "virl2"
    assert cl.password == "virl2"


def test_client_library_init_disallow_http(
    client_library_server_current: MagicMock,
) -> None:
    """Client raises InitializationError for http:// when allow_http=False.

    :param client_library_server_current: Patched system_info fixture.
    """
    _ = client_library_server_current
    with pytest.raises(InitializationError, match="must be https"):
        ClientLibrary("http://somehost", "virl2", "virl2")
    with pytest.raises(InitializationError, match="must be https"):
        ClientLibrary("http://somehost", "virl2", "virl2", allow_http=False)


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


# the test fails if you have variables set in env
@pytest.mark.parametrize("via", ["environment", "parameter"])
@pytest.mark.parametrize("env_var", ["VIRL2_URL", "VIRL_HOST"])
@pytest.mark.parametrize(
    "params",
    [
        (False, "somehost"),
        (False, "http://somehost"),
        (False, "https://somehost:443"),
        (True, "xyz://somehost:443"),
        (True, "https:@somehost:4:4:3"),
        (True, ""),
        (True, None),
    ],
)
def test_client_library_init_url(
    client_library_server_current: MagicMock,
    reset_env: None,
    monkeypatch: pytest.MonkeyPatch,
    via: str,
    env_var: str,
    params: tuple[bool, str | None],
) -> None:
    """ClientLibrary URL init from env or parameter with validation.

    :param client_library_server_current: Patched system_info fixture.
    :param reset_env: Fixture clearing VIRL2 env vars.
    :param monkeypatch: Pytest monkeypatch fixture.
    :param via: Source of URL ('environment' or 'parameter').
    :param env_var: Environment variable name for URL.
    :param params: Tuple of (should_fail, url_value).
    """
    _ = client_library_server_current, reset_env
    monkeypatch.setattr("getpass.getpass", input)
    (fail, url) = params
    expected_parts = None if fail else httpx.URL(url)
    if via == "environment":
        env = url
        url = None
    else:
        env = "http://badhost" if url else None
    if env is None:
        monkeypatch.delenv(env_var, raising=False)
    else:
        monkeypatch.setenv(env_var, env)
    if fail:
        with pytest.raises((InitializationError, OSError)) as err:
            ClientLibrary(
                url=url,
                username="virl2",
                password="virl2",
                allow_http=True,
                raise_for_auth_failure=True,
            )
        if isinstance(err, OSError):
            pattern = "(reading from stdin)"
            assert re.match(pattern, str(err.value))
    else:
        cl = ClientLibrary(url, username="virl2", password="virl2", allow_http=True)
        url_parts = cl._session.base_url
        assert url_parts.scheme == (expected_parts.scheme or "https")
        assert url_parts.host == (expected_parts.host or expected_parts.path)
        assert url_parts.port == expected_parts.port
        assert url_parts.path == "/api/v0/"
        assert cl._session.base_url.path.endswith("/api/v0/")
        assert cl.username == "virl2"
        assert cl.password == "virl2"


# the test fails if you have variables set in env
@pytest.mark.parametrize("via", ["environment", "parameter"])
@pytest.mark.parametrize("env_var", ["VIRL2_USER", "VIRL_USERNAME"])
@pytest.mark.parametrize("params", [(False, "johndoe"), (True, ""), (True, None)])
def test_client_library_init_user(
    client_library_server_current: MagicMock,
    reset_env: None,
    monkeypatch: pytest.MonkeyPatch,
    via: str,
    env_var: str,
    params: tuple[bool, str | None],
) -> None:
    """ClientLibrary username init from env or parameter with validation.

    :param client_library_server_current: Patched system_info fixture.
    :param reset_env: Fixture clearing VIRL2 env vars.
    :param monkeypatch: Pytest monkeypatch fixture.
    :param via: Source of username ('environment' or 'parameter').
    :param env_var: Environment variable name for username.
    :param params: Tuple of (should_fail, username_value).
    """
    _ = client_library_server_current, reset_env
    monkeypatch.setattr("getpass.getpass", input)
    url = "validhostname"
    (fail, user) = params
    if via == "environment":
        # can't set a None value for an environment variable
        env = user or ""
        user = None
    else:
        env = "baduser" if user else ""
    if env is None:
        monkeypatch.delenv(env_var, raising=False)
    else:
        monkeypatch.setenv(env_var, env)
    if fail:
        with pytest.raises((OSError, InitializationError)) as err:
            ClientLibrary(url=url, username=user, password="virl2")
        if isinstance(err, OSError):
            pattern = "(reading from stdin)"
            assert re.match(pattern, str(err.value))
    else:
        cl = ClientLibrary(url, username=user, password="virl2")
        assert cl.username == params[1]
        assert cl.password == "virl2"
        assert cl._session.base_url == "https://validhostname/api/v0/"


# the test fails if you have variables set in env
@pytest.mark.parametrize("via", ["environment", "parameter"])
@pytest.mark.parametrize("env_var", ["VIRL2_PASS", "VIRL_PASSWORD"])
@pytest.mark.parametrize("params", [(False, "validPa$$w!2"), (True, ""), (True, None)])
def test_client_library_init_password(
    client_library_server_current: MagicMock,
    reset_env: None,
    monkeypatch: pytest.MonkeyPatch,
    via: str,
    env_var: str,
    params: tuple[bool, str | None],
) -> None:
    """ClientLibrary password init from env or parameter with validation.

    :param client_library_server_current: Patched system_info fixture.
    :param reset_env: Fixture clearing VIRL2 env vars.
    :param monkeypatch: Pytest monkeypatch fixture.
    :param via: Source of password ('environment' or 'parameter').
    :param env_var: Environment variable name for password.
    :param params: Tuple of (should_fail, password_value).
    """
    _ = client_library_server_current, reset_env
    monkeypatch.setattr("getpass.getpass", input)
    url = "validhostname"
    (fail, password) = params
    if via == "environment":
        # can't set a None value for an environment variable
        env = password or ""
        password = None
    else:
        env = "badpass" if password else ""
    if env is None:
        monkeypatch.delenv(env_var, raising=False)
    else:
        monkeypatch.setenv(env_var, env)
    if fail:
        with pytest.raises((OSError, InitializationError)) as err:
            ClientLibrary(url=url, username="virl2", password=password)
        if isinstance(err, OSError):
            pattern = "(reading from stdin)"
            assert re.match(pattern, str(err.value))
    else:
        cl = ClientLibrary(url, username="virl2", password=password)
        assert cl.username == "virl2"
        assert cl.password == params[1]
        assert cl._session.base_url == "https://validhostname/api/v0/"


def test_client_library_str_and_repr(
    client_library_server_current: MagicMock,
) -> None:
    """ClientLibrary str and repr return expected format.

    :param client_library_server_current: Patched system_info fixture.
    """
    _ = client_library_server_current
    client_library = ClientLibrary("somehost", "virl2", password="virl2")
    assert repr(client_library) == "ClientLibrary('https://somehost')"
    assert str(client_library) == "ClientLibrary URL: https://somehost/api/v0/"


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


def test_client_minor_version_gt_nowarn(
    client_library_server_current: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """No version warning when client minor is greater than controller.

    :param client_library_server_current: Patched system_info fixture.
    :param caplog: Pytest log capture fixture.
    """
    _ = client_library_server_current
    with caplog.at_level(logging.WARNING):
        ClientLibrary("somehost", "virl2", password="virl2")
    assert (
        f"Please ensure the client version is compatible with the controller version. "
        f"Client {CURRENT_VERSION}, controller 2.0.0." not in caplog.text
    )


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


def test_exact_version_no_warn(
    client_library_server_current: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """No version warning when client and controller versions match.

    :param client_library_server_current: Patched system_info fixture.
    :param caplog: Pytest log capture fixture.
    """
    _ = client_library_server_current
    with caplog.at_level(logging.WARNING):
        ClientLibrary("somehost", "virl2", password="virl2")
    assert (
        f"Please ensure the client version is compatible with the controller version. "
        f"Client {CURRENT_VERSION}, controller 2.0.0." not in caplog.text
    )


@pytest.mark.parametrize(
    "greater, lesser, expected",
    [
        pytest.param(
            Version("2.0.1"), Version("2.0.0"), True, id="Patch is greater than"
        ),
        pytest.param(
            Version("2.0.10"), Version("2.0.0"), True, id="Patch is much greater than"
        ),
        pytest.param(
            Version("2.1.0"), Version("2.0.0"), True, id="Minor is greater than"
        ),
        pytest.param(
            Version("2.10.0"), Version("2.0.0"), True, id="Minor is much greater than"
        ),
        pytest.param(
            Version("3.0.0"), Version("2.0.0"), True, id="Major is greater than"
        ),
        pytest.param(
            Version("10.0.0"), Version("2.0.0"), True, id="Major is much greater than"
        ),
        pytest.param(
            Version("2.0.0"), Version("2.0.1"), False, id="Patch is lesser than"
        ),
        pytest.param(
            Version("2.0.0"), Version("2.0.10"), False, id="Patch is much lesser than"
        ),
        pytest.param(
            Version("2.0.0"), Version("2.1.0"), False, id="Minor is lesser than"
        ),
        pytest.param(
            Version("2.0.0"), Version("2.10.0"), False, id="Minor is much lesser than"
        ),
        pytest.param(
            Version("2.0.0"), Version("3.0.0"), False, id="Major is lesser than"
        ),
        pytest.param(
            Version("2.0.0"), Version("10.0.0"), False, id="Major is much lesser than"
        ),
        pytest.param(
            Version("2.0.0"),
            "random string",
            False,
            id="Other object is string and not a Version object",
        ),
        pytest.param(
            Version("2.0.0"),
            12345,
            False,
            id="Other object is int and not a Version object",
        ),
    ],
)
def test_version_comparison_greater_than(
    greater: Version, lesser: Version | str | int, expected: bool
) -> None:
    """Compare Version objects with greater-than operator.

    :param greater: Version expected to be greater.
    :param lesser: Version or other object to compare against.
    :param expected: Expected result of greater > lesser.
    """
    assert (greater > lesser) == expected


@pytest.mark.parametrize(
    "first, second, expected",
    [
        pytest.param(
            Version("2.0.1"), Version("2.0.0"), True, id="Patch is greater than"
        ),
        pytest.param(
            Version("2.0.10"), Version("2.0.0"), True, id="Patch is much greater than"
        ),
        pytest.param(
            Version("2.1.0"), Version("2.0.0"), True, id="Minor is greater than"
        ),
        pytest.param(
            Version("2.10.0"), Version("2.0.0"), True, id="Minor is much greater than"
        ),
        pytest.param(
            Version("3.0.0"), Version("2.0.0"), True, id="Major is greater than"
        ),
        pytest.param(
            Version("10.0.0"), Version("2.0.0"), True, id="Major is much greater than"
        ),
        pytest.param(
            Version("2.0.0"), Version("2.0.1"), False, id="Patch is lesser than"
        ),
        pytest.param(
            Version("2.0.0"), Version("2.0.10"), False, id="Patch is much lesser than"
        ),
        pytest.param(
            Version("2.0.0"), Version("2.1.0"), False, id="Minor is lesser than"
        ),
        pytest.param(
            Version("2.0.0"), Version("2.10.0"), False, id="Minor is much lesser than"
        ),
        pytest.param(
            Version("2.0.0"), Version("3.0.0"), False, id="Major is lesser than"
        ),
        pytest.param(
            Version("2.0.0"), Version("10.0.0"), False, id="Major is much lesser than"
        ),
        pytest.param(
            Version("2.0.0"),
            Version("2.0.0"),
            True,
            id="Equal versions no minor no patch",
        ),
        pytest.param(
            Version("2.0.1"),
            Version("2.0.1"),
            True,
            id="Equal versions patch increment",
        ),
        pytest.param(
            Version("2.1.0"),
            Version("2.1.0"),
            True,
            id="Equal versions minor increment",
        ),
        pytest.param(
            Version("3.0.0"),
            Version("3.0.0"),
            True,
            id="Equal versions major increment",
        ),
        pytest.param(
            Version("2.0.0"),
            "random string",
            False,
            id="Other object is string and not a Version object",
        ),
        pytest.param(
            Version("2.0.0"),
            12345,
            False,
            id="Other object is int and not a Version object",
        ),
    ],
)
def test_version_comparison_greater_than_or_equal_to(
    first: Version, second: Version, expected: bool
) -> None:
    """Compare Version objects with greater-than-or-equal operator.

    :param first: First Version to compare.
    :param second: Second Version to compare against.
    :param expected: Expected result of first >= second.
    """
    assert (first >= second) == expected


@pytest.mark.parametrize(
    "lesser, greater, expected",
    [
        pytest.param(Version("2.0.0"), Version("2.0.1"), True, id="Patch is less than"),
        pytest.param(
            Version("2.0.0"), Version("2.0.10"), True, id="Patch is much less than"
        ),
        pytest.param(Version("2.0.0"), Version("2.1.0"), True, id="Minor is less than"),
        pytest.param(
            Version("2.0.0"), Version("2.10.0"), True, id="Minor is much less than"
        ),
        pytest.param(Version("2.0.0"), Version("3.0.0"), True, id="Major is less than"),
        pytest.param(
            Version("2.0.0"), Version("10.0.0"), True, id="Major is much less than"
        ),
        pytest.param(
            Version("2.0.1"), Version("2.0.0"), False, id="Patch is greater than"
        ),
        pytest.param(
            Version("2.0.10"), Version("2.0.0"), False, id="Patch is much greater than"
        ),
        pytest.param(
            Version("2.1.0"), Version("2.0.0"), False, id="Minor is greater than"
        ),
        pytest.param(
            Version("2.10.0"), Version("2.0.0"), False, id="Minor is much greater than"
        ),
        pytest.param(
            Version("3.0.0"), Version("2.0.0"), False, id="Major is greater than"
        ),
        pytest.param(
            Version("10.0.0"), Version("2.0.0"), False, id="Major is much greater than"
        ),
        pytest.param(
            Version("2.0.0"),
            "random string",
            False,
            id="Other object is string and not a Version object",
        ),
        pytest.param(
            Version("2.0.0"),
            12345,
            False,
            id="Other object is int and not a Version object",
        ),
    ],
)
def test_version_comparison_less_than(
    lesser: Version, greater: Version | str | int, expected: bool
) -> None:
    """Compare Version objects with less-than operator.

    :param lesser: Version expected to be lesser.
    :param greater: Version or other object to compare against.
    :param expected: Expected result of lesser < greater.
    """
    assert (lesser < greater) == expected


@pytest.mark.parametrize(
    "first, second, expected",
    [
        pytest.param(Version("2.0.0"), Version("2.0.1"), True, id="Patch is less than"),
        pytest.param(
            Version("2.0.0"), Version("2.0.10"), True, id="Patch is much less than"
        ),
        pytest.param(Version("2.0.0"), Version("2.1.0"), True, id="Minor is less than"),
        pytest.param(
            Version("2.0.0"), Version("2.10.0"), True, id="Minor is much less than"
        ),
        pytest.param(Version("2.0.0"), Version("3.0.0"), True, id="Major is less than"),
        pytest.param(
            Version("2.0.0"), Version("10.0.0"), True, id="Major is much less than"
        ),
        pytest.param(
            Version("2.0.1"), Version("2.0.0"), False, id="Patch is greater than"
        ),
        pytest.param(
            Version("2.0.10"), Version("2.0.0"), False, id="Patch is much greater than"
        ),
        pytest.param(
            Version("2.1.0"), Version("2.0.0"), False, id="Minor is greater than"
        ),
        pytest.param(
            Version("2.10.0"), Version("2.0.0"), False, id="Minor is much greater than"
        ),
        pytest.param(
            Version("3.0.0"), Version("2.0.0"), False, id="Major is greater than"
        ),
        pytest.param(
            Version("10.0.0"), Version("2.0.0"), False, id="Major is much greater than"
        ),
        pytest.param(
            Version("2.0.0"),
            Version("2.0.0"),
            True,
            id="Equal versions no minor no patch",
        ),
        pytest.param(
            Version("2.0.1"),
            Version("2.0.1"),
            True,
            id="Equal versions patch increment",
        ),
        pytest.param(
            Version("2.1.0"),
            Version("2.1.0"),
            True,
            id="Equal versions minor increment",
        ),
        pytest.param(
            Version("3.0.0"),
            Version("3.0.0"),
            True,
            id="Equal versions major increment",
        ),
        pytest.param(
            Version("2.0.0"),
            "random string",
            False,
            id="Other object is string and not a Version object",
        ),
        pytest.param(
            Version("2.0.0"),
            12345,
            False,
            id="Other object is int and not a Version object",
        ),
    ],
)
def test_version_comparison_less_than_or_equal_to(
    first: Version, second: Version, expected: bool
) -> None:
    """Compare Version objects with less-than-or-equal operator.

    :param first: First Version to compare.
    :param second: Second Version to compare against.
    :param expected: Expected result of first <= second.
    """
    assert (first <= second) == expected


def test_different_version_strings() -> None:
    """Parse various Version string formats and reject invalid ones."""
    v = Version("2.1.0-dev0+build8.7ee86bf8")
    assert v.major == 2 and v.minor == 1 and v.patch == 0
    v = Version("2.1.0dev0+build8.7ee86bf8")
    assert v.major == 2 and v.minor == 1 and v.patch == 0
    v = Version("2.1.0--dev0+build8.7ee86bf8")
    assert v.major == 2 and v.minor == 1 and v.patch == 0
    v = Version("2.1.0_dev0+build8.7ee86bf8")
    assert v.major == 2 and v.minor == 1 and v.patch == 0
    v = Version("2.1.0")
    assert v.major == 2 and v.minor == 1 and v.patch == 0
    v = Version("2.1.0-")
    assert v.major == 2 and v.minor == 1 and v.patch == 0

    with pytest.raises(ValueError):
        Version("2.1-dev0+build8.7ee86bf8")
    with pytest.raises(ValueError):
        Version("2-dev0+build8.7ee86bf8")
    with pytest.raises(ValueError):
        Version("54dev0+build8.7ee86bf8")


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


def test_convergence_parametrization(
    client_library_server_current: MagicMock, mocked_session: MagicMock
) -> None:
    """Convergence wait params flow from client to lab and override on call.

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
    # check that passing of value from client to lab is working
    lab = cl.create_lab()
    assert lab.wait_max_iterations == max_iter
    assert lab.wait_time == max_time
    with patch.object(Lab, "has_converged", return_value=False):
        with pytest.raises(RuntimeError) as err:
            lab.wait_until_lab_converged()
        assert (
            "has not converged, maximum tries %s exceeded" % max_iter
        ) in err.value.args[0]

        # try to override values on function
        with pytest.raises(RuntimeError) as err:
            lab.wait_until_lab_converged(max_iterations=1)
        assert ("has not converged, maximum tries %s exceeded" % 1) in err.value.args[0]


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
    if valid:
        return_value = httpx.Response(200, json=data)
    else:
        return_value = httpx.Response(404)

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


def test_get_diagnostics_requires_categories(client_library: ClientLibrary):
    with pytest.raises(ValueError, match="No diagnostics category provided"):
        client_library.get_diagnostics()


@respx.mock
def test_system_management_controller_triggers_compute_load(
    client_library_server_current: MagicMock,
) -> None:
    """system_management.controller returns connector host from compute_hosts.

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
