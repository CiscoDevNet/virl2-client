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

from ..exceptions import APIError

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

    # Read by httpx.Auth at runtime. When True, httpx buffers the full
    # response body before invoking `auth_flow`, so our retry logic can
    # safely inspect `response.json()` / `response.text` to decide
    # whether a 4xx was caused by an expired token. Looks like dead
    # code at a glance because nothing in this module references it
    # directly -- the consumer is the httpx.Auth contract.
    requires_response_body = True

    def __init__(self, client_library: ClientLibrary) -> None:
        """
        Initialize the TokenAuth object with a client library instance.

        :param client_library: A client library instance.
        """
        self.client_library = client_library

    @property
    def token(self) -> str | None:
        """
        Return the authentication token. If the token has not been set, it is obtained
        from the server.

        :returns: The JWT token or None.
        """
        if self.client_library.jwtoken:
            return self.client_library.jwtoken

        base_url = self.client_library._session.base_url
        if not self.client_library.allow_http:
            if base_url.port is not None and base_url.port != 443:
                _LOGGER.warning("Not using SSL port of 443: %s", base_url.port)
            if base_url.scheme != "https":
                _LOGGER.warning("Not using https scheme: %s", base_url.scheme)
        data = {
            "username": self.client_library.username,
            "password": self.client_library.password,
        }
        response = self.client_library._session.post(
            _AUTH_URL,
            json=data,
            auth=None,  # type: ignore[arg-type]
        )  # auth=None works but is missing from .post's type hint
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

        :param clear_all_sessions: Whether to clear all sessions.
        :returns: Whether the logout succeeded.
        """
        url = "logout" + ("?clear_all_sessions=true" if clear_all_sessions else "")
        return self.client_library._session.delete(url).json()


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
        300s read / 60s write / 10s pool budget. Pass a larger
        httpx.Timeout if you expect long-running synchronous lab
        operations. Disabling timeouts entirely is strongly discouraged
        as it lets a hostile or stalled controller pin the client
        indefinitely.
    :param send_client_uuid: When True (default), send an X-Client-UUID
        header on every request so the controller can correlate activity.
        Set to False in privacy-sensitive automation.
    :returns: The created httpx Client object.
    """
    headers = {"X-CML-CLIENT": "PCL" if client_type is None else client_type}
    if send_client_uuid:
        headers["X-Client-UUID"] = str(uuid4())
    return CustomClient(
        base_url=base_url,
        verify=ssl_verify,
        auth=BlankAuth(),
        follow_redirects=True,
        timeout=DEFAULT_TIMEOUT if timeout is None else timeout,
        headers=headers,
    )
