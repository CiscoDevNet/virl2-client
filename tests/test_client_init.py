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
"""Tests for ClientLibrary constructor, URL parsing, and repr."""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
import pytest

from virl2_client.virl2_client import ClientLibrary, InitializationError

if TYPE_CHECKING:
    from unittest.mock import MagicMock

FAKE_URL = "https://0.0.0.0/fake_url/"


@pytest.fixture
def reset_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear VIRL2-related environment variables for isolated init tests.

    :param monkeypatch: Pytest monkeypatch fixture.
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


@pytest.mark.parametrize("allow_http", [None, False], ids=["default", "explicit_false"])
def test_init_disallow_http(
    client_library_server_current: MagicMock,
    allow_http: bool | None,
) -> None:
    """Client raises InitializationError for http:// when allow_http disallows.

    NOTE: LLM-generated test -- verify for correctness.

    :param client_library_server_current: Patched system_info fixture.
    :param allow_http: Value for allow_http (None = omit kwarg).
    """
    _ = client_library_server_current
    kwargs = {} if allow_http is None else {"allow_http": allow_http}
    with pytest.raises(InitializationError, match="must be https"):
        ClientLibrary("http://somehost", "virl2", "virl2", **kwargs)


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
        if isinstance(err.value, OSError):
            assert "reading from stdin" in str(err.value)
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
        if isinstance(err.value, OSError):
            assert "reading from stdin" in str(err.value)
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
        if isinstance(err.value, OSError):
            assert "reading from stdin" in str(err.value)
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
