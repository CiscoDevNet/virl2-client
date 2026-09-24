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
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import httpx
import pytest

from virl2_client.exceptions import APIError, InitializationError
from virl2_client.models import TokenAuth
from virl2_client.models.authentication import DEFAULT_TIMEOUT, make_session

if TYPE_CHECKING:
    from collections.abc import Iterator


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
    client._session.base_url = httpx.URL("https://example.local:8443/api/v0/")
    # TokenAuth.token uses `_session.stream(...)` as a context manager (not
    # `.post()`) so it can cap the login response body; mock the same shape.
    stream_response = client._session.stream.return_value.__enter__.return_value
    stream_response.status_code = 200
    stream_response.json.return_value = "jwt-token"
    return client


def test_token_auth_logs_insecure_url_details(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Warn when non-443 port is used over https.

    NOTE: LLM-generated test -- verify for correctness.

    :param caplog: Pytest log capture fixture.
    """
    auth = TokenAuth(_make_client())

    with caplog.at_level(logging.WARNING):
        token = auth.token

    assert token == "jwt-token"
    assert "Not using SSL port of 443: 8443" in caplog.text


def test_token_auth_suppresses_warnings_non_standard_port(
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


@pytest.mark.parametrize("allow_http", [False, True])
def test_token_auth_refuses_username_password_over_http(allow_http: bool) -> None:
    """Refuse username/password auth over http:// regardless of allow_http.

    Only a pre-obtained token (client.jwtoken) is permitted over http://
    (CMLDEV-1228 / H3+H5).

    NOTE: LLM-generated test -- verify for correctness.

    :param allow_http: Value for the allow_http attribute.
    """
    client = _make_client(allow_http=allow_http)
    client._session.base_url = httpx.URL("http://example.local/api/v0/")
    auth = TokenAuth(client)

    with pytest.raises(InitializationError, match="unencrypted"):
        _ = auth.token

    client._session.post.assert_not_called()
    client._session.stream.assert_not_called()


def test_token_auth_allows_preset_jwtoken_over_http() -> None:
    """Allow a pre-obtained jwtoken to be used over http://.

    NOTE: LLM-generated test -- verify for correctness.
    """
    client = _make_client(allow_http=True)
    client._session.base_url = httpx.URL("http://example.local/api/v0/")
    client.jwtoken = "preset-token"
    auth = TokenAuth(client)

    assert auth.token == "preset-token"
    client._session.post.assert_not_called()
    client._session.stream.assert_not_called()


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


def test_make_session_follow_redirects_default_false() -> None:
    """make_session defaults to not following redirects.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = make_session("https://example.local/api/v0/")
    assert session.follow_redirects is False


def test_make_session_follow_redirects_opt_in() -> None:
    """make_session follows redirects when explicitly opted in.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = make_session("https://example.local/api/v0/", follow_redirects=True)
    assert session.follow_redirects is True


def test_token_auth_logout_clears_cached_secrets() -> None:
    """logout() zeroes cached jwtoken/password on the client library.

    NOTE: LLM-generated test -- verify for correctness.
    """
    client = _make_client()
    client.jwtoken = "cached-token"
    client._session.delete.return_value.json.return_value = True
    auth = TokenAuth(client)

    assert auth.logout() is True
    assert client.jwtoken is None
    assert client.password is None


def test_token_auth_caps_buffered_response_body() -> None:
    """sync_auth_flow does not buffer an error response body beyond the cap.

    Only 4xx/5xx responses are capped (2xx/3xx pass through untouched, see
    test_token_auth_does_not_cap_successful_response_body), so this uses a
    401 status to exercise the cap. httpx's own auth-retry machinery needs
    username/password configured to retry a 401, so those are set here too.
    _content is always cached (a short truncation marker for oversized
    bodies) so later read()/re-iteration by httpx never hits the closed
    stream (regression: previously left unset, raising downstream).

    NOTE: LLM-generated test -- verify for correctness.
    """
    client = _make_client()
    client.username = "user"
    client.password = "pass"
    auth = TokenAuth(client)
    auth.MAX_RESPONSE_BODY_BYTES = 8

    request = httpx.Request("GET", "https://example.local/api/v0/authentication")
    oversized_body = b"x" * 1024

    def gen() -> Iterator[bytes]:
        """Yield the oversized body as a single chunk to simulate a stream."""
        yield oversized_body

    response = httpx.Response(
        401,
        request=request,
        content=gen(),
        headers={"content-length": str(len(oversized_body))},
    )

    flow = auth.sync_auth_flow(request)
    next(flow)
    flow.send(response)

    # Declared-oversize fast path: body replaced by a short truncation marker.
    assert b"truncated" in response._content
    assert len(response._content) < len(oversized_body)
    assert response.read() == response._content


def test_token_auth_does_not_cap_successful_response_body() -> None:
    """sync_auth_flow leaves 2xx response bodies untouched, even if large.

    Regression test: capping must be scoped to 4xx/5xx auth-error bodies
    only. Applying it to every response (as TokenAuth is the session-wide
    `auth`) would silently truncate/empty normal, larger-than-the-cap API
    payloads (lab lists, topologies, etc.).

    NOTE: LLM-generated test -- verify for correctness.
    """
    client = _make_client()
    client.jwtoken = "preset-token"
    big_body = b"[" + b",".join([b"1"] * 40_000) + b"]"

    def handler(request: httpx.Request) -> httpx.Response:
        """Return a large, streamed 200 JSON response.

        :param request: The outgoing request (unused).
        :returns: A streamed 200 response larger than MAX_RESPONSE_BODY_BYTES.
        """
        _ = request

        def gen() -> Iterator[bytes]:
            """Yield the body in chunks to simulate an unread stream."""
            for i in range(0, len(big_body), 4096):
                yield big_body[i : i + 4096]

        return httpx.Response(
            200, content=gen(), headers={"content-length": str(len(big_body))}
        )

    transport = httpx.MockTransport(handler)
    auth = TokenAuth(client)
    session = httpx.Client(
        transport=transport, auth=auth, base_url="https://example.local/"
    )
    response = session.get("/labs")
    assert response.content == big_body
    assert len(response.json()) == 40_000


def test_token_auth_capped_response_survives_raise_for_status() -> None:
    """An oversized 4xx/5xx auth response does not crash raise_for_status.

    Regression test: previously, _read_capped closed the stream without
    caching `_content`, so raise_for_status's own `response.read()` call
    raised an unhandled httpx stream exception instead of the intended
    HTTPStatusError.

    NOTE: LLM-generated test -- verify for correctness.
    """
    client = _make_client()
    client.jwtoken = "preset-token"

    def handler(request: httpx.Request) -> httpx.Response:
        """Return an oversized, streamed 403 response.

        :param request: The outgoing request (unused).
        :returns: A streamed 403 response exceeding the body-size cap.
        """
        _ = request

        def gen() -> Iterator[bytes]:
            """Yield the oversized body in chunks to simulate an unread stream."""
            for _ in range(20):
                yield b"x" * 10_000

        return httpx.Response(403, content=gen(), headers={"content-length": "200000"})

    transport = httpx.MockTransport(handler)
    auth = TokenAuth(client)
    session = httpx.Client(
        transport=transport, auth=auth, base_url="https://example.local/"
    )
    with pytest.raises(httpx.HTTPStatusError):
        session.get("/foo")


def test_token_auth_caps_streamed_response_without_content_length() -> None:
    """The streaming cap loop bounds bodies with no/understated Content-Length.

    Regression test: the Content-Length precheck shortcut in `_read_capped`
    is not the only enforcement path -- a chunked/streamed response without
    (or with an understated) Content-Length must still be capped by the
    `iter_bytes()` accumulation loop, not fully buffered.

    NOTE: LLM-generated test -- verify for correctness.
    """
    client = _make_client()
    client.jwtoken = "preset-token"

    def handler(request: httpx.Request) -> httpx.Response:
        """Return an oversized 403 response with no Content-Length header.

        :param request: The outgoing request (unused).
        :returns: A streamed 403 response exceeding the body-size cap.
        """
        _ = request

        def gen() -> Iterator[bytes]:
            """Yield the oversized body in chunks to simulate a stream."""
            for _ in range(20):
                yield b"x" * 10_000

        return httpx.Response(403, content=gen())

    transport = httpx.MockTransport(handler)
    auth = TokenAuth(client)
    session = httpx.Client(
        transport=transport, auth=auth, base_url="https://example.local/"
    )
    with pytest.raises(httpx.HTTPStatusError):
        session.get("/foo")


def test_token_auth_caps_oversized_login_response() -> None:
    """A hostile/oversized login (authenticate) response body is also capped.

    Regression test: `token` used to POST to `/authenticate` with `auth=None`
    via `.post()`, which made httpx fully buffer the response before this
    method regained control -- bypassing MAX_RESPONSE_BODY_BYTES entirely
    for the one endpoint reachable pre-authentication. `token` now uses
    `.stream()` so the same cap applies here too.

    NOTE: LLM-generated test -- verify for correctness.
    """
    client = _make_client()
    client.jwtoken = None

    def handler(request: httpx.Request) -> httpx.Response:
        """Return an oversized, streamed 401 login-failure response.

        :param request: The outgoing request (unused).
        :returns: A streamed 401 response exceeding the body-size cap.
        """
        _ = request

        def gen() -> Iterator[bytes]:
            """Yield the oversized body in chunks to simulate a stream."""
            for _ in range(20):
                yield b"x" * 10_000

        return httpx.Response(401, content=gen())

    transport = httpx.MockTransport(handler)
    real_session = httpx.Client(transport=transport, base_url="https://example.local/")
    client._session = real_session
    auth = TokenAuth(client)

    with pytest.raises(httpx.HTTPStatusError):
        _ = auth.token


def test_read_capped_tolerates_malformed_content_length() -> None:
    """A non-numeric Content-Length must not crash _read_capped.

    Regression test: a hostile/misbehaving server can send a bogus
    Content-Length (e.g. "not-a-number"). Parsing it must not raise; the
    header is treated as "unknown length" and the streaming loop still
    bounds how much of the body is buffered.

    NOTE: LLM-generated test -- verify for correctness.
    """
    request = httpx.Request("GET", "https://example.local/api/v0/authentication")
    oversized_body = b"x" * 1024

    def gen() -> Iterator[bytes]:
        """Yield the oversized body in chunks to simulate a stream."""
        for i in range(0, len(oversized_body), 128):
            yield oversized_body[i : i + 128]

    response = httpx.Response(
        403,
        request=request,
        content=gen(),
        headers={"content-length": "not-a-number"},
    )

    # Caps to a 64-byte prefix (+ marker) via the streaming loop, not raising.
    TokenAuth._read_capped(response, 64)

    assert response._content.startswith(b"x" * 64)
    assert b"truncated" in response._content
    assert len(response._content) < len(oversized_body)
    assert response.read() == response._content


def test_token_auth_warns_on_non_https_scheme(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Warn when the base URL scheme is neither https nor http.

    With allow_http=False and a scheme that is not "http" (which would be
    refused outright) nor "https", `token` logs a "Not using https scheme"
    warning before attempting the login.

    NOTE: LLM-generated test -- verify for correctness.

    :param caplog: Pytest log capture fixture.
    """
    client = _make_client()
    # Scheme-less URL: not "http" (so not refused) and not "https" (so warned).
    client._session.base_url = httpx.URL("//example.local/api/v0/")
    auth = TokenAuth(client)

    with caplog.at_level(logging.WARNING):
        token = auth.token

    assert token == "jwt-token"
    assert "Not using https scheme" in caplog.text
