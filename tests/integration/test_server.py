#
# This file is part of CML 2
#
# Copyright 2021 Cisco Systems Inc.
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

"""Tests for the server connection and configuration."""

import pytest
import requests
import random
import string

from virl2_client import ClientConfig, ClientLibrary

pytestmark = [pytest.mark.integration]

LIMITED_ENDPOINTS = ["/api/v0/authenticate", "/api/v0/auth_extended"]


def test_webtoken_config(client_library_session: ClientLibrary):
    """Configure web session timeout, verify the setting was saved."""
    # TODO: can we set this to just a few seconds and verify the timeout?
    orig = client_library_session.system_management.get_web_session_timeout()

    client_library_session.system_management.set_web_session_timeout(3600)
    res = client_library_session.system_management.get_web_session_timeout()
    assert res == 3600
    client_library_session.system_management.set_web_session_timeout(orig)
    res = client_library_session.system_management.get_web_session_timeout()
    assert res == orig


def test_mac_addr_block_config(client_library_session: ClientLibrary):
    """Configure MAC address block, verify the setting was saved."""
    # TODO: revert config in pytest fixture
    orig = client_library_session.system_management.get_mac_address_block()

    client_library_session.system_management.set_mac_address_block(7)
    res = client_library_session.system_management.get_mac_address_block()
    assert res == 7

    client_library_session.system_management.set_mac_address_block(orig)
    res = client_library_session.system_management.get_mac_address_block()
    assert res == orig


@pytest.mark.parametrize(argnames="address_block", argvalues=[8, -1])
def test_mac_addr_block_negative(address_block, client_library_session: ClientLibrary):
    """Configure MAC address block to an invalid value, expect code 400."""
    # TODO: move client-side validation out of integration tests
    # validated client-side
    with pytest.raises(ValueError):
        client_library_session.system_management.set_mac_address_block(address_block)

    # validated server-side
    with pytest.raises(requests.exceptions.HTTPError) as err:
        client_library_session.system_management._set_mac_address_block(address_block)
    assert err.value.response.status_code == 400


@pytest.mark.nomock
def test_server_tokens_off(client_config: ClientConfig):
    """Send a GET request to the base URL and verify server header in the response."""
    resp = requests.get(client_config.url, verify=client_config.ssl_verify)
    headers = resp.headers
    # has to equal 'nginx' without version
    assert headers["Server"] == "nginx"


def test_sending_requests_without_auth_token(client_config: ClientConfig):
    """Send a request without auth token, expect 401."""
    client_library = client_config.make_client()
    # it probably won't be a common case to override `auth` by ClientLibrary users
    # but missing auth token may happen when using API directly via HTTP:
    client_library.session.auth = None
    with pytest.raises(requests.exceptions.HTTPError) as exc:
        client_library.create_lab()
    exc.match("401 Client Error: Unauthorized for url")


@pytest.mark.nomock
def test_rate_limit(client_config: ClientConfig):
    """Send a number of bad auth requests, but not enough to trigger the limit."""
    # TODO: somehow test the rate limit without breaking the remaining tests
    for endpoint in LIMITED_ENDPOINTS:
        for i in range(30):
            r = requests.post(
                client_config.url + endpoint,
                json={"username": client_config.username, "password": "incorrect_pwd"},
                verify=False,
            )
            assert r.status_code != 429


@pytest.mark.parametrize("size", (20_000_000, 20_999_999))
@pytest.mark.nomock
def test_max_client_body_size(cleanup_test_labs, client_library_session: ClientLibrary, size: int):
    """
    Test nginx configuration.
    Currently we have all endpoints limited to 100K (CSDL) in http block
    of nginx configuration.
    Then some specific locations are allowed greater request body size:
        /api/v0/images/upload                         16GB
        /api/v0/labs/{lab_id}/nodes/{node_id}/config  20MB
        /api/v0/labs/{lab_id}/nodes                   20MB
        /api/v0/labs/{lab_id}/nodes/{node_id}         20MB
        /api/v0/import                                20MB
        /api/v0/import/virl-1x                        20MB

    """
    max_size = 20_000_000  # 20MB
    lab = client_library_session.create_lab("lab_space")

    data = "".join(random.choice(string.ascii_lowercase) for _ in range(size))
    # POST /api/v0/labs/{lab_id}/nodes
    try:
        server = lab.create_node("s1", "server", 100, 100, configuration=data)
    except requests.exceptions.HTTPError as err:
        assert "413 Client Error: Request Entity Too Large" in err.args[0]
        server = lab.create_node("s1", "server", 100, 100)

    # DEPRECATED PUT /api/v0/labs/{lab_id}/nodes/{node_id}/config
    try:
        # deprecated API is no longer supported in client library
        url = server._base_url + "/config"
        response = client_library_session.session.put(url=url, data=data)
        response.raise_for_status()
        if size > max_size:
            assert False, "Server config accepted!"
    except requests.exceptions.HTTPError as err:
        assert "413 Client Error: Request Entity Too Large" in err.args[0]

    # PATCH /api/v0/labs/{lab_id}/nodes/{node_id}
    try:
        server.config = data
        if size > max_size:
            assert False, "Server config accepted!"
    except requests.exceptions.HTTPError as err:
        assert "413 Client Error: Request Entity Too Large" in err.args[0]

    # POST /api/v0/import(/virl-1x)?
    for title in ("test.virl", "test.yaml"):
        with pytest.raises(requests.exceptions.HTTPError) as exc_info:
            client_library_session.import_lab(data, title)
            message = exc_info.value.args[0]
            if size > max_size:
                assert "413 Client Error: Request Entity Too Large" in message
            else:
                assert "400 Client Error: Bad Request" in message

    client_library_session.remove_lab(lab.id)
