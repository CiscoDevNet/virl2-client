#
# This file is part of VIRL 2
# Copyright (c) 2019-2023, Cisco Systems, Inc.
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
from typing import TYPE_CHECKING, Generator, Optional

import httpx

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ..virl2_client import ClientLibrary


class TokenAuth(httpx.Auth):
    """
    Initially inspired by:
    https://requests.readthedocs.io/en/v2.9.1/user/authentication/?highlight=AuthBase#new-forms-of-authentication
    and modified for httpx based on:
    https://www.python-httpx.org/advanced/#customizing-authentication
    """

    requires_response_body = True

    def __init__(self, client_library: ClientLibrary):
        self.client_library = client_library
        self._token: Optional[str] = None

    @property
    def token(self) -> Optional[str]:
        if self._token is not None:
            return self._token

        auth_url = "authenticate"
        base_url = self.client_library.session.base_url
        if base_url.port is not None and base_url.port != 443:
            _LOGGER.warning("Not using SSL port of 443: %d", base_url.port)
        if base_url.scheme != "https":
            _LOGGER.warning("Not using https scheme: %s", base_url.scheme)
        data = {
            "username": self.client_library.username,
            "password": self.client_library.password,
        }
        response = self.client_library.session.post(
            auth_url, json=data, auth=None  # type: ignore
        )  # auth=None works but is missing from .post's type hint
        response_raise(response)
        self._token = response.json()
        return self._token

    @token.setter
    def token(self, value: Optional[str]):
        self._token = value

    def auth_flow(
        self, request: httpx.Request
    ) -> Generator[httpx.Request, httpx.Response, None]:

        request.headers["Authorization"] = "Bearer {}".format(self.token)
        response = yield request

        if response.status_code == 401:
            _LOGGER.warning("re-auth called on 401 unauthorized")
            self.token = None
            request.headers["Authorization"] = "Bearer {}".format(self.token)
            response = yield request

        response_raise(response)

    def logout(self, clear_all_sessions=False):
        url = "logout" + ("?clear_all_sessions=true" if clear_all_sessions else "")
        return self.client_library.session.delete(url).json()


class BlankAuth(httpx.Auth):
    def auth_flow(
        self, request: httpx.Request
    ) -> Generator[httpx.Request, httpx.Response, None]:
        response = yield request
        response_raise(response)


def response_raise(response: httpx.Response) -> None:
    """Replaces the useless link to httpstatuses.com with error description."""
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        error.response.read()
        try:
            error_msg = json.loads(error.response.text)["description"]
        except (json.JSONDecodeError, IndexError, TypeError):
            error_msg = error.response.text
        error_text: str = error.args[0].split("\n")[0]
        error_text += "\n" + error_msg
        error.args = (error_text,)
        raise error


def make_session(base_url: str, ssl_verify: bool = True) -> httpx.Client:
    return httpx.Client(
        base_url=base_url,
        verify=ssl_verify,
        auth=BlankAuth(),
        follow_redirects=True,
        timeout=None,
    )
