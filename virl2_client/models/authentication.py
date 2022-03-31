#
# This file is part of VIRL 2
# Copyright (c) 2019-2022, Cisco Systems, Inc.
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

import logging
from urllib.parse import urljoin, urlparse

import requests

logger = logging.getLogger(__name__)


class TokenAuth(requests.auth.AuthBase):
    """
    Inspired by:
    http://docs.python-requests.org/en/v2.9.1/user/authentication/?highlight=AuthBase#new-forms-of-authentication
    """

    def __init__(self, client_library):
        self.client_library = client_library
        self.token = None

    def __call__(self, request):
        token = self.authenticate()
        request.headers["Authorization"] = "Bearer {}".format(token)
        request.register_hook("response", self.handle_401_unauthorized)
        return request

    def handle_401_unauthorized(self, resp, **kwargs):  # pylint: disable=W0613
        # ensure that we print the result from the API if something goes wrong.
        # As almost every library call uses "raise_for_status()"
        if resp.status_code != 401:
            if not resp.ok:
                logger.error("API Error: %s", resp.text)
            return resp

        # reset existing token:
        self.token = None
        # repeat last request that has failed
        token = self.authenticate()
        logger.warning("re-auth called on 401 unauthorized")
        request = resp.request.copy()
        request.headers["Authorization"] = "Bearer {}".format(token)
        request.deregister_hook("response", self.handle_401_unauthorized)
        new_resp = resp.connection.send(request)
        new_resp.history.append(resp)
        return new_resp

    def authenticate(self):
        if self.token is not None:
            return self.token
        url = urljoin(
            self.client_library._base_url, "authenticate"
        )  # pylint: disable=W0212
        parsed_url = urlparse(url)
        if parsed_url.port is not None and parsed_url.port != 443:
            logger.warning("Not using SSL port of 443: %d", parsed_url.port)
        if parsed_url.scheme != "https":
            logger.warning("Not using https scheme: %s", parsed_url.scheme)
        data = {
            "username": self.client_library.username,
            "password": self.client_library.password,
        }
        response = self.client_library.session.post(url, json=data, auth=False)
        response.raise_for_status()
        self.token = response.json()
        return self.token

    def logout(self, clear_all_sessions=False):
        url = urljoin(self.client_library._base_url, "logout")
        if clear_all_sessions:
            url = url + "?clear_all_sessions=true"
        response = self.client_library.session.delete(url)
        response.raise_for_status()
        return response.json()


class Context:
    def __init__(self, base_url, requests_session=None):
        self._base_url = base_url
        if requests_session is None:
            self._requests_session = requests.Session()
        else:
            self._requests_session = requests_session

    def __repr__(self):
        return "{}({!r}, {!r}".format(
            self.__class__.__name__,
            self._base_url,
            self._requests_session,
        )

    @property
    def base_url(self):
        return self._base_url

    @property
    def session(self):
        return self._requests_session
