#
# Python bindings for the Cisco VIRL 2 Network Simulation Platform
#
# This file is part of VIRL 2
#
# Copyright 2020 Cisco Systems Inc.
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

import pytest
import requests.exceptions

from datetime import datetime
from time import sleep

from virl2_client import ClientLibrary

pytestmark = [pytest.mark.integration, pytest.mark.nomock]


def ensure_unregistered(client_library_session: ClientLibrary):
    """Make sure licensing is not registered."""
    status = client_library_session.licensing.status()

    if status["registration"]["status"] == "COMPLETED":
        client_library_session.licensing.deregister()


@pytest.fixture(autouse=True, scope="module")
def cleanup_registration(
    client_library_session: ClientLibrary,
    alpha_ssms_url,
    alpha_dev_ca,
    registration_token,
):
    """
    Make sure licensing is unregistered before starting tests.
    Register it back at the end of the test module.
    """
    ensure_unregistered(client_library_session)
    client_library_session.licensing.set_default_transport()
    ensure_no_certificate(client_library_session)
    yield
    client_library_session.licensing.set_transport(ssms=alpha_ssms_url)
    client_library_session.licensing.install_certificate(cert=alpha_dev_ca)
    client_library_session.licensing.register_wait(
        token=registration_token, reregister=True
    )


def ensure_no_certificate(client_library_session: ClientLibrary):
    cert = client_library_session.licensing.get_certificate()

    if cert is not None:
        client_library_session.licensing.remove_certificate()


@pytest.fixture(autouse=True, scope="function")
def cleanup_certificate(client_library_session: ClientLibrary):
    """Make sure there is no certificate before and after the test."""
    ensure_no_certificate(client_library_session)
    yield
    ensure_no_certificate(client_library_session)


@pytest.fixture(
    params=[
        "empty",
        "basic_string",
        "with_header_footer",
        "missing_header",
        "missing_footer",
        "missing_header_footer",
    ]
)
def certificate_invalid(request, alpha_dev_ca) -> str:
    certs = {
        "empty": "",
        "basic_string": "abc",
        "with_header_footer": "-----BEGIN CERTIFICATE-----abc-----END CERTIFICATE-----",
        "missing_header": alpha_dev_ca.replace("-----BEGIN CERTIFICATE-----", ""),
        "missing_footer": alpha_dev_ca.replace("-----END CERTIFICATE-----", ""),
        "missing_header_footer": alpha_dev_ca.replace(
            "-----BEGIN CERTIFICATE-----", ""
        ).replace("-----END CERTIFICATE-----", ""),
    }
    return certs[request.param]


def test_certificate_add_show_remove(
    client_library_session: ClientLibrary, alpha_dev_ca
):
    """Install a valid certificate, then remove it."""
    cl = client_library_session

    cl.licensing.install_certificate(alpha_dev_ca)
    assert cl.licensing.get_certificate() == alpha_dev_ca

    cl.licensing.remove_certificate()
    assert cl.licensing.get_certificate() is None


def test_certificate_invalid(
    client_library_session: ClientLibrary, certificate_invalid
):
    """Try installing an invalid certificate, expect to fail."""
    cl = client_library_session

    with pytest.raises(requests.exceptions.HTTPError) as exc:
        cl.licensing.install_certificate(certificate_invalid)
    exc.match("400 Client Error: Bad Request for url")


def test_set_transport(client_library_session: ClientLibrary, alpha_ssms_url):
    cl = client_library_session
    """Configure valid transport settings."""

    cl.licensing.set_transport(None)
    transport = cl.licensing.status()["transport"]
    assert transport["ssms"] == transport["default_ssms"]
    assert transport["proxy"]["server"] is None
    assert transport["proxy"]["port"] is None

    cl.licensing.set_transport(alpha_ssms_url)
    transport = cl.licensing.status()["transport"]
    assert transport["ssms"] == alpha_ssms_url
    assert transport["proxy"]["server"] is None
    assert transport["proxy"]["port"] is None

    cl.licensing.set_transport(
        alpha_ssms_url, proxy_server="127.0.0.1", proxy_port=49152
    )
    transport = cl.licensing.status()["transport"]
    assert transport["ssms"] == alpha_ssms_url
    assert transport["proxy"]["server"] == "127.0.0.1"
    assert transport["proxy"]["port"] == 49152


def test_registration_actions(
    client_library_session: ClientLibrary,
    alpha_dev_ca,
    alpha_ssms_url,
    registration_token,
):
    """
    Perform licensing actions:
      (registration, re-registration, de-registration, auth renewal, reg renewal)
    With valid certificate, transport settings and token.
    """
    cl = client_library_session

    cl.licensing.install_certificate(alpha_dev_ca)
    cl.licensing.set_transport(alpha_ssms_url)

    # Register
    cl.licensing.register_wait(token=registration_token)
    status = cl.licensing.status()
    assert status["registration"]["status"] == "COMPLETED"
    assert status["authorization"]["status"] == "IN_COMPLIANCE"

    # Re-register
    cl.licensing.register_wait(token=registration_token, reregister=True)
    status = cl.licensing.status()
    assert status["registration"]["status"] == "COMPLETED"
    assert status["authorization"]["status"] == "IN_COMPLIANCE"

    # Renew authorization
    auth_expiry = datetime.fromisoformat(
        cl.licensing.status()["authorization"]["expires"]
    )
    cl.licensing.renew_authorization()
    timeout = 20
    for x in range(timeout):
        auth_expiry_new = datetime.fromisoformat(
            cl.licensing.status()["authorization"]["expires"]
        )
        if auth_expiry_new > auth_expiry:
            break
        else:
            sleep(1)
            continue
    else:
        pytest.fail(
            f"Timed out waiting {timeout} secs for authorization renewal."
        )
    status = cl.licensing.status()
    assert status["registration"]["status"] == "COMPLETED"
    assert status["authorization"]["status"] == "IN_COMPLIANCE"

    # Renew registration
    reg_expiry = datetime.fromisoformat(
        cl.licensing.status()["registration"]["expires"]
    )
    cl.licensing.register_renew()
    timeout = 20
    for x in range(timeout):
        reg_expiry_new = datetime.fromisoformat(
            cl.licensing.status()["registration"]["expires"]
        )
        if reg_expiry_new > reg_expiry:
            break
        else:
            sleep(1)
            continue
    else:
        pytest.fail(
            f"Timed out waiting {timeout} secs for registration renewal."
        )
    status = cl.licensing.status()
    assert status["registration"]["status"] == "COMPLETED"
    assert status["authorization"]["status"] == "IN_COMPLIANCE"

    # Deregister
    cl.licensing.deregister()
    status = cl.licensing.status()
    assert status["registration"]["status"] == "NOT_REGISTERED"
    assert status["authorization"]["status"] == "EVAL"


# TODO: registration actions with invalid transport settings
# TODO: registration actions with invalid token
# TODO: min/max feature counts for every license type
# TODO: SLR - enable, disable, request reservation, cancel request
# TODO: SLR - mock server responses and test all functions
