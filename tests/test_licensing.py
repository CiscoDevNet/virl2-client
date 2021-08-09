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
