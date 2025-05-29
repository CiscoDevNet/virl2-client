#
# This file is part of VIRL 2
# Copyright (c) 2019-2025, Cisco Systems, Inc.
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
from typing import TYPE_CHECKING, Generator
from uuid import uuid4

import httpx

from ..exceptions import APIError

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ..virl2_client import ClientLibrary


_AUTH_URL = "authenticate"


def raise_for_status(response: httpx.Response):
    """
    https://github.com/encode/httpx/discussions/2224#discussioncomment-2732372

    When raising for status from certain places, if response is unread, the stream is
    automatically closed, and we then cannot read the response in later error handling.
    We thus need to check if the response is 4/500 and read it preemptively if so.
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

    requires_response_body = True

    def __init__(self, client_library: ClientLibrary):
        """
        Initialize the TokenAuth object with a client library instance.

        :param client_library: A client library instance.
        """
        self.client_library = client_library
        self._token: str | None = None

    @property
    def token(self) -> str | None:
        """
        Return the authentication token. If the token has not been set, it is obtained
        from the server.
        """
        if self._token is not None:
            return self._token

        base_url = self.client_library._session.base_url
        if base_url.port is not None and base_url.port != 443:
            _LOGGER.warning(f"Not using SSL port of 443: {base_url.port:d}")
        if base_url.scheme != "https":
            _LOGGER.warning(f"Not using https scheme: {base_url.scheme}")
        data = {
            "username": self.client_library.username,
            "password": self.client_library.password,
        }
        response = self.client_library._session.post(
            _AUTH_URL,
            json=data,
            auth=None,  # type: ignore
        )  # auth=None works but is missing from .post's type hint
        raise_for_status(response)
        self._token = response.json()
        return self._token

    @token.setter
    def token(self, value: str | None) -> None:
        """
        Set the authentication token to the specified value.

        :param value: The value to set as the authentication token.
        """
        self._token = value

    def auth_flow(
        self, request: httpx.Request
    ) -> Generator[httpx.Request, httpx.Response, None]:
        """
        Implement the authentication flow for the token-based authentication.

        :param request: The request object to authenticate.
        :returns: A generator of the authenticated request and response objects.
        """
        request.headers["Authorization"] = f"Bearer {self.token}"
        response = yield request

        if response.status_code == 401:
            _LOGGER.warning("re-auth called on 401 unauthorized")
            self.token = None
            request.headers["Authorization"] = f"Bearer {self.token}"
            response = yield request

        raise_for_status(response)

    def logout(self, clear_all_sessions=False) -> bool:
        """
        Log out the user (invalidate the current token).

        :param clear_all_sessions: Whether to clear all sessions.
        :returns: Whether the logout succeeded.
        """
        url = "logout" + ("?clear_all_sessions=true" if clear_all_sessions else "")
        return self.client_library._session.delete(url).json()


class BlankAuth(httpx.Auth):
    """A class that implements an httpx Auth object that does nothing."""

    def auth_flow(
        self, request: httpx.Request
    ) -> Generator[httpx.Request, httpx.Response, None]:
        response = yield request
        raise_for_status(response)


class CustomClient(httpx.Client):
    _ERROR_PREFIX = {4: "Client error - ", 5: "Server error - "}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_request = self.request
        self.request = self._request

    def _request(self, *args, **kwargs):
        """
        httpx.Client.request modified to raise an exception if the response
        has an HTTP status error and replace the useless link
        to httpstatuses.com with error description.

        :raises APIError: If the response has an HTTP status error.
        """
        try:
            return self._original_request(*args, **kwargs)
        except httpx.HTTPStatusError as error:
            try:
                error_detail = json.loads(error.response.text)["description"]
            except (json.JSONDecodeError, IndexError, TypeError):
                error_detail = error.response.text
            prefix = self._ERROR_PREFIX.get(error.response.status_code // 100, "")
            api_error = APIError(
                f"{prefix}{error_detail or error}",
                request=error.request,
                response=error.response,
            )
            raise api_error from None


def make_session(
    base_url: str, ssl_verify: bool | str = True, client_type: str = None
) -> httpx.Client:
    """
    Create an httpx Client object with the specified base URL
    and SSL verification setting.

    Note: The base URL is automatically prepended to all HTTP calls. This means you
    should use ``_session.get("labs")`` rather than ``_session.get(base_url + "labs")``.

    :param base_url: The base URL for the client.
    :param ssl_verify: Whether to perform SSL verification.
    :param client_type: The client type identifier.
    :returns: The created httpx Client object.
    """
    return CustomClient(
        base_url=base_url,
        verify=ssl_verify,
        auth=BlankAuth(),
        follow_redirects=True,
        timeout=None,
        headers={
            "X-Client-UUID": str(uuid4()),
            "X-CML-CLIENT": "PCL" if client_type is None else client_type,
        },
    )
