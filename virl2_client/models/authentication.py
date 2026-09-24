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
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, ClassVar
from uuid import uuid4

import httpx

from ..exceptions import APIError, InitializationError

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from collections.abc import Generator

    from ..virl2_client import ClientLibrary


_AUTH_URL = "authenticate"


def raise_for_status(response: httpx.Response) -> None:
    """
    Ensure response body is read before raising for status.

    https://github.com/encode/httpx/discussions/2224#discussioncomment-2732372

    When raising for status from certain places, if response is unread, the stream is
    automatically closed, and we then cannot read the response in later error handling.
    We thus need to check if the response is 4/500 and read it preemptively if so.

    :param response: The httpx response to check.
    """
    if response.status_code // 100 in (4, 5):
        response.read()
    response.raise_for_status()


class TokenAuth(httpx.Auth):
    """
    Token-based authentication for an httpx session.

    Inspired by:
    https://requests.readthedocs.io/en/v2.9.1/user/authentication/?highlight=AuthBase#new-forms-of-authentication
    Modified for httpx based on:
    https://www.python-httpx.org/advanced/#customizing-authentication
    """

    # Read by httpx.Auth at runtime. When True, httpx would buffer the full
    # response body before invoking `auth_flow`. We override `sync_auth_flow`
    # below to apply a max-bytes cap instead, so this flag is not actually
    # consumed by the base implementation for us -- it documents intent for
    # readers, and would still gate `async_auth_flow` if it were used.
    requires_response_body = True

    # Safety cap on how much of a 4xx/5xx (or any) response body we buffer
    # per auth round-trip. Prevents a hostile/misbehaving server from
    # forcing the client to hold an unbounded body in memory.
    MAX_RESPONSE_BODY_BYTES = 64 * 1024

    def __init__(self, client_library: ClientLibrary) -> None:
        """
        Initialize the TokenAuth object with a client library instance.

        :param client_library: A client library instance.
        """
        self.client_library = client_library

    @staticmethod
    def _read_capped(response: httpx.Response, limit: int) -> None:
        """
        Read up to `limit` bytes of the response body, then stop.

        Mirrors httpx.Response.read(), but bounds how much is buffered so a
        hostile/misbehaving server cannot force unbounded memory use. A bogus
        Content-Length (non-numeric/negative/multiple values) is treated as
        unknown length rather than raising. Always caches a `_content` value
        (truncated bodies get a trailing marker) so later read()/re-iteration
        by httpx (raise_for_status, auth retry) sees cached content instead of
        hitting the closed stream (StreamClosed/StreamConsumed).

        :param response: The response to (partially) read.
        :param limit: Maximum number of bytes to buffer.
        """
        if hasattr(response, "_content"):
            return
        content_length = response.headers.get("content-length")
        try:
            declared_length = int(content_length) if content_length is not None else -1
        except ValueError:
            declared_length = -1
        # Fast path: skip reading when the server honestly declares oversize.
        if declared_length > limit:
            response.close()
            response._content = (
                b"<error response truncated: declared %d bytes exceeds %d>"
                % (declared_length, limit)
            )
            return
        chunks: list[bytes] = []
        total = 0
        truncated = False
        for chunk in response.iter_bytes():
            remaining = limit - total
            if len(chunk) > remaining:
                # Keep the prefix that fits, then stop.
                chunks.append(chunk[:remaining])
                truncated = True
                break
            chunks.append(chunk)
            total += len(chunk)
        if truncated:
            response.close()
        body = b"".join(chunks)
        if truncated:
            body += b"... <error response truncated at %d bytes>" % limit
        response._content = body

    def sync_auth_flow(
        self, request: httpx.Request
    ) -> Generator[httpx.Request, httpx.Response, None]:
        """
        Run the authentication flow, capping buffered 4xx/5xx response bodies.

        Overrides httpx.Auth.sync_auth_flow (rather than relying on
        `requires_response_body`) so the automatic body read of error
        responses is bounded by MAX_RESPONSE_BODY_BYTES instead of
        unbounded. Successful (2xx/3xx) responses are left untouched and
        are read normally by the caller.

        :param request: The request object to authenticate.
        :yields: The authenticated request and response in sequence.
        """
        flow = self.auth_flow(request)
        request = next(flow)
        while True:
            response = yield request
            # Only 4xx/5xx responses are capped here: those are the ones
            # auth_flow's own raise_for_status() (and error reporting) read
            # eagerly, and the only ones a hostile server could otherwise
            # force the client to buffer without bound. 2xx/3xx application
            # responses are left untouched so normal, larger-than-the-cap
            # API payloads (lab topologies, image/definition lists, etc.)
            # are not truncated.
            if response.status_code // 100 in (4, 5):
                self._read_capped(response, self.MAX_RESPONSE_BODY_BYTES)
            try:
                request = flow.send(response)
            except StopIteration:
                break

    @property
    def token(self) -> str | None:
        """
        Return the authentication token. If the token has not been set, it is obtained
        from the server.

        :returns: The JWT token or None.
        :raises InitializationError: If credentials would be sent over
            unencrypted HTTP.
        """
        if self.client_library.jwtoken:
            return self.client_library.jwtoken

        base_url = self.client_library._session.base_url
        if base_url.scheme == "http":
            # Never post username/password in cleartext; only a preset token.
            raise InitializationError(
                "Refusing to send username/password over unencrypted "
                "http://. Set client.jwtoken to a pre-obtained token instead."
            )
        if not self.client_library.allow_http:
            if base_url.port is not None and base_url.port != 443:
                _LOGGER.warning("Not using SSL port of 443: %s", base_url.port)
            if base_url.scheme != "https":
                _LOGGER.warning("Not using https scheme: %s", base_url.scheme)
        data = {
            "username": self.client_library.username,
            "password": self.client_library.password,
        }
        # Use `.stream()` (not `.post()`) so the body is not auto-buffered
        # before we can apply MAX_RESPONSE_BODY_BYTES.
        with self.client_library._session.stream(
            "POST",
            _AUTH_URL,
            json=data,
            auth=None,  # type: ignore[arg-type]
        ) as response:  # auth=None works but is missing from .stream's type hint
            # Cap regardless of status: /authenticate returns only a small JWT.
            self._read_capped(response, self.MAX_RESPONSE_BODY_BYTES)
            raise_for_status(response)
            self.client_library.jwtoken = response.json()
        return self.client_library.jwtoken

    @token.setter
    def token(self, value: str | None) -> None:
        """
        Set the authentication token to the specified value.

        :param value: The value to set as the authentication token.
        """
        self.client_library.jwtoken = value

    def auth_flow(
        self, request: httpx.Request
    ) -> Generator[httpx.Request, httpx.Response, None]:
        """
        Implement the authentication flow for the token-based authentication.

        :param request: The request object to authenticate.
        :yields: The authenticated request and response in sequence.
        """
        request.headers["Authorization"] = f"Bearer {self.token}"
        response = yield request

        if response.status_code == 401:
            _LOGGER.warning("re-auth called on 401 unauthorized")
            self.token = None
            if not (self.client_library.username and self.client_library.password):
                raise APIError(
                    "JWT token expired and automatic re-authentication is not "
                    "possible because username/password are not configured. "
                    "Set client.jwtoken, or initialize with username/password.",
                    request=response.request,
                    response=response,
                )
            request.headers["Authorization"] = f"Bearer {self.token}"
            response = yield request

        raise_for_status(response)

    def logout(self, clear_all_sessions: bool = False) -> bool:
        """
        Log out the user (invalidate the current token).

        Also clears cached secrets (token, password) from the client
        library so they do not linger in memory after logout.

        :param clear_all_sessions: Whether to clear all sessions.
        :returns: Whether the logout succeeded.
        """
        url = "logout" + ("?clear_all_sessions=true" if clear_all_sessions else "")
        try:
            return self.client_library._session.delete(url).json()
        finally:
            self.client_library.jwtoken = None
            self.client_library.password = None


class BlankAuth(httpx.Auth):
    """An httpx Auth implementation that performs no authentication."""

    def auth_flow(
        self, request: httpx.Request
    ) -> Generator[httpx.Request, httpx.Response, None]:
        """
        Pass through the request without adding authentication headers.

        :param request: The request to send.
        :yields: The request and response in sequence.
        """
        response = yield request
        raise_for_status(response)


class CustomClient(httpx.Client):
    """httpx Client that raises APIError with server description on HTTP errors."""

    _ERROR_PREFIX: ClassVar[dict[int, str]] = MappingProxyType(
        {
            4: "Client error - ",
            5: "Server error - ",
        }
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """
        Initialize the custom client, wrapping request to raise APIError on failures.

        :param args: Positional arguments passed to httpx.Client.
        :param kwargs: Keyword arguments passed to httpx.Client.
        """
        super().__init__(*args, **kwargs)
        self._original_request = self.request
        self.request = self._request

    def _request(self, *args: Any, **kwargs: Any) -> httpx.Response:
        """
        Override httpx.Client.request to raise APIError with server description.

        Replaces the default httpx HTTPStatusError with APIError containing
        the server's error description when available.

        :param args: Positional arguments passed to the underlying request.
        :param kwargs: Keyword arguments passed to the underlying request.
        :returns: The HTTP response on success.
        :raises APIError: If the response has an HTTP status error.
        """
        try:
            return self._original_request(*args, **kwargs)
        except httpx.HTTPStatusError as error:
            try:
                error_detail = json.loads(error.response.text)["description"]
            except (json.JSONDecodeError, IndexError, KeyError, TypeError):
                error_detail = error.response.text
            prefix = self._ERROR_PREFIX.get(error.response.status_code // 100, "")
            api_error = APIError(
                f"{prefix}{error_detail or error}",
                request=error.request,
                response=error.response,
            )
            raise api_error from None


DEFAULT_TIMEOUT = httpx.Timeout(connect=10.0, read=300.0, write=60.0, pool=10.0)


def make_session(
    base_url: str,
    ssl_verify: bool | str = True,
    client_type: str | None = None,
    timeout: httpx.Timeout | float | None = None,
    send_client_uuid=True,
    follow_redirects: bool = False,
) -> httpx.Client:
    """
    Create an httpx Client object with the specified base URL
    and SSL verification setting.

    Note: The base URL is automatically prepended to all HTTP calls. This means you
    should use _session.get("labs") rather than _session.get(base_url + "labs").

    :param base_url: The base URL for the client.
    :param ssl_verify: Whether to perform SSL verification.
    :param client_type: The client type identifier.
    :param timeout: HTTP timeout override. Defaults to a 10s connect /
        300s read / 60s write / 10s pool budget when omitted or None.
        Pass a larger httpx.Timeout for long-running synchronous lab
        operations.
    :param send_client_uuid: When True (default), send an X-Client-UUID
        header on every request so the controller can correlate activity.
        Set to False in privacy-sensitive automation.
    :param follow_redirects: When False (default), the client does not
        auto-follow HTTP redirects. A redirect can silently retarget a
        request (and its Authorization header) to a different host; opt in
        with True only when the controller is trusted to redirect safely.
    :returns: The created httpx Client object.
    """
    headers = {"X-CML-CLIENT": "PCL" if client_type is None else client_type}
    if send_client_uuid:
        headers["X-Client-UUID"] = str(uuid4())
    return CustomClient(
        base_url=base_url,
        verify=ssl_verify,
        auth=BlankAuth(),
        follow_redirects=follow_redirects,
        timeout=DEFAULT_TIMEOUT if timeout is None else timeout,
        headers=headers,
    )
