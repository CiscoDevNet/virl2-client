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
"""Unit tests for authentication helpers and auth objects."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import httpx
import pytest

from virl2_client.exceptions import APIError
from virl2_client.models import TokenAuth
from virl2_client.models.authentication import DEFAULT_TIMEOUT, make_session


def _make_client(allow_http: bool = False) -> MagicMock:
    """Build a minimal client-library mock.

    :param allow_http: Value for the allow_http attribute.
    :returns: A mocked client object compatible with TokenAuth.
    """
    client = MagicMock()
    client.jwtoken = None
    client.username = "u"
    client.password = "p"
    client.allow_http = allow_http
    client._session.base_url = httpx.URL("http://example.local:8443/api/v0/")
    client._session.post.return_value.json.return_value = "jwt-token"
    return client


def test_token_auth_logs_insecure_url_details(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Warn when non-HTTPS or non-443 endpoint is used.

    NOTE: LLM-generated test -- verify for correctness.

    :param caplog: Pytest log capture fixture.
    """
    auth = TokenAuth(_make_client())

    with caplog.at_level(logging.WARNING):
        token = auth.token

    assert token == "jwt-token"
    assert "Not using SSL port of 443: 8443" in caplog.text
    assert "Not using https scheme: http" in caplog.text


def test_token_auth_suppresses_warnings_http(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Suppress scheme/port warnings when allow_http is True.

    NOTE: LLM-generated test -- verify for correctness.

    :param caplog: Pytest log capture fixture.
    """
    auth = TokenAuth(_make_client(allow_http=True))

    with caplog.at_level(logging.WARNING):
        token = auth.token

    assert token == "jwt-token"
    assert "Not using SSL port of 443" not in caplog.text
    assert "Not using https scheme" not in caplog.text


@pytest.mark.parametrize(
    ("clear_all_sessions", "expected_url"),
    [
        (False, "logout"),
        (True, "logout?clear_all_sessions=true"),
    ],
)
def test_token_auth_logout_builds_expected_url(
    clear_all_sessions: bool, expected_url: str
) -> None:
    """Build the correct logout URL for each clear-session mode.

    NOTE: LLM-generated test -- verify for correctness.

    :param clear_all_sessions: Whether all sessions should be cleared.
    :param expected_url: Expected API endpoint path.
    """
    client = _make_client()
    client._session.delete.return_value.json.return_value = True
    auth = TokenAuth(client)

    assert auth.logout(clear_all_sessions=clear_all_sessions) is True
    client._session.delete.assert_called_once_with(expected_url)


def test_auth_flow_no_creds_raises() -> None:
    """Raise APIError on 401 when username/password are unavailable.

    NOTE: LLM-generated test -- verify for correctness.
    """
    client = _make_client()
    client.username = None
    client.password = None
    auth = TokenAuth(client)
    auth.token = "expired-token"

    request = httpx.Request("GET", "https://example.local/api/v0/authentication")
    response = httpx.Response(401, request=request)
    flow = auth.auth_flow(request)
    next(flow)

    with pytest.raises(APIError, match="automatic re-authentication is not possible"):
        flow.send(response)


def test_make_session_default_timeout() -> None:
    """make_session applies DEFAULT_TIMEOUT when timeout is omitted."""
    session = make_session("https://example.local/api/v0/")
    assert session.timeout == DEFAULT_TIMEOUT


def test_make_session_send_client_uuid_false() -> None:
    """make_session omits X-Client-UUID when send_client_uuid is False."""
    session = make_session("https://example.local/api/v0/", send_client_uuid=False)
    assert "X-Client-UUID" not in session.headers
