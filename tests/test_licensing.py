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


@pytest.fixture
def ensure_certificate(client_library_session: ClientLibrary, alpha_dev_ca):
    """Make sure certificate is installed after the test."""

    yield

    cert = client_library_session.licensing.get_certificate()

    if cert is not alpha_dev_ca:
        if cert is not None:
            client_library_session.licensing.remove_certificate()
        client_library_session.licensing.install_certificate(alpha_dev_ca)


@pytest.fixture
def ensure_transport(client_library_session: ClientLibrary, alpha_ssms_url):
    """Make sure transport is set to test gateway server after the test."""

    yield
    client_library_session.licensing.set_transport(alpha_ssms_url)


def ensure_unregistered(client_library_session: ClientLibrary):
    """Make sure licensing is not registered."""
    status = client_library_session.licensing.status()

    if status["registration"]["status"] == "COMPLETED":
        deregister_wait(client_library_session)


def ensure_default_features(client_library_session: ClientLibrary):
    """
    Make sure product type is set to Enterprise
    and license counts are at default: 1 base, 0 expansion nodes
    """
    status = client_library_session.licensing.status()
    if status["product_license"]["active"] != "CML_Enterprise":
        client_library_session.licensing.set_product_license("CML_Enterprise")
    features = client_library_session.licensing.features()
    if features[0]["in_use"] != 1 or features[1]["in_use"] != 0:
        client_library_session.licensing.update_features(
            {
                features[0]["id"]: 1,
                features[1]["id"]: 0,
            }
        )


@pytest.fixture(scope="module", autouse=True)
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
    if client_library_session.licensing.status()["reservation_mode"] is True:
        client_library_session.licensing.disable_reservation_mode()
    ensure_default_features(client_library_session)
    yield
    ensure_default_features(client_library_session)
    client_library_session.licensing.register_wait(
        token=registration_token, reregister=True
    )


@pytest.fixture(scope="function", autouse=True)
def cleanup_licensing(
    client_library_session: ClientLibrary,
    alpha_ssms_url,
    ensure_certificate,
    ensure_transport,
):
    """Reset registration, transport settings and certificate after every test."""
    yield
    ensure_unregistered(client_library_session)
    ensure_default_features(client_library_session)


@pytest.fixture()
def cleanup_reservation_mode(
    client_library_session: ClientLibrary,
):
    yield
    client_library_session.licensing.disable_reservation_mode()


def register_wait_fail(client_library_session: ClientLibrary, token, reregister=False):
    client_library_session.licensing.register(token, reregister)
    client_library_session.licensing.wait_for_status(
        "registration", "FAILED", "RETRY_IN_PROGRESS"
    )
    client_library_session.licensing.wait_for_status("authorization", "EVAL")


def deregister_wait(client_library_session: ClientLibrary):
    """Request deregistration from the current SSMS
    and wait for registration status to be NOT_REGISTERED
    and authorization status to be INIT or EVAL
    """
    client_library_session.licensing.deregister()
    client_library_session.licensing.wait_for_status("registration", "NOT_REGISTERED")
    client_library_session.licensing.wait_for_status("authorization", "INIT", "EVAL")


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


@pytest.fixture(
    params=[
        "personal20",
        "personal40",
        "enterprise",
        "educational",
        "internal",
        "notForResale",
    ]
)
def license_types(request):
    licenses = {
        "personal20": "CML_Personal",
        "personal40": "CML_Personal40",
        "enterprise": "CML_Enterprise",
        "educational": "CML_Education",
        "internal": "CML_Internal",
        "notForResale": "CML_NotForResale",
    }
    return licenses[request.param]


def test_certificate_add_show_remove(
    client_library_session: ClientLibrary, alpha_dev_ca
):
    """Install a valid certificate, then remove it."""
    cl = client_library_session

    if cl.licensing.get_certificate() is not None:
        cl.licensing.remove_certificate()

    cl.licensing.install_certificate(alpha_dev_ca)
    assert cl.licensing.get_certificate() == alpha_dev_ca

    cl.licensing.remove_certificate()
    assert cl.licensing.get_certificate() is None


@pytest.mark.skip(reason="rejected certificate breaks test_license_count")
def test_certificate_invalid(
    client_library_session: ClientLibrary, certificate_invalid
):
    """Try installing an invalid certificate, expect to fail."""
    cl = client_library_session

    if cl.licensing.get_certificate() is not None:
        cl.licensing.remove_certificate()

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
    registration_token,
):
    """
    Perform licensing actions:
      (registration, re-registration, de-registration, auth renewal, reg renewal)
    With valid certificate, transport settings and token.
    """
    cl = client_library_session

    # Register
    cl.licensing.register_wait(token=registration_token)

    # Re-register
    cl.licensing.register_wait(token=registration_token, reregister=True)

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
        pytest.fail(f"Timed out waiting {timeout} secs for authorization renewal.")
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
        pytest.fail(f"Timed out waiting {timeout} secs for registration renewal.")
    status = cl.licensing.status()
    assert status["registration"]["status"] == "COMPLETED"
    assert status["authorization"]["status"] == "IN_COMPLIANCE"

    # Deregister
    deregister_wait(client_library_session)
    status = cl.licensing.status()
    assert status["registration"]["status"] == "NOT_REGISTERED"
    assert status["authorization"]["status"] == "EVAL"


@pytest.mark.skip(
    reason="trying to register with invalid transport breaks test_license_count"
)
def test_registration_invalid_transport(
    client_library_session: ClientLibrary,
    alpha_ssms_url,
    registration_token,
):
    cl = client_library_session

    cl.licensing.set_transport("127.0.0.1")

    register_wait_fail(cl, token=registration_token)

    register_wait_fail(cl, token=registration_token, reregister=True)

    # Register properly so we can try renewals with bad transport
    cl.licensing.set_transport(alpha_ssms_url)
    cl.licensing.register_wait(token=registration_token)
    cl.licensing.set_transport("127.0.0.1")

    cl.licensing.renew_authorization()
    timeout = 20
    for x in range(timeout):
        status = cl.licensing.status()["authorization"]["renew_time"]["success"]
        if status == "FAILED":
            break
        else:
            sleep(1)
            continue
    else:
        pytest.fail(
            "Timed out waiting {0} secs for authorization renewal to fail.".format(
                timeout
            )
        )

    cl.licensing.register_renew()
    timeout = 20
    for x in range(timeout):
        status = cl.licensing.status()["registration"]["renew_time"]["success"]
        if status == "FAILED":
            break
        else:
            sleep(1)
            continue
    else:
        pytest.fail(
            "Timed out waiting {0} secs for registration renewal to fail.".format(
                timeout
            )
        )

    cl.licensing.set_transport(alpha_ssms_url)
    deregister_wait(client_library_session)
    status = cl.licensing.status()
    assert status["registration"]["status"] == "NOT_REGISTERED"
    assert status["authorization"]["status"] == "EVAL"


def test_registration_invalid_token(
    client_library_session: ClientLibrary,
):

    cl = client_library_session
    bad_token = "BadRegistrationToken"

    register_wait_fail(cl, token=bad_token)

    status = cl.licensing.status()
    assert (
        f"{bad_token}' is not valid"
        in status["registration"]["register_time"]["failure"]
    )

    register_wait_fail(cl, token=bad_token, reregister=True)

    status = cl.licensing.status()
    assert (
        f"{bad_token}' is not valid"
        in status["registration"]["register_time"]["failure"]
    )


def test_license_count(
    client_library_session: ClientLibrary,
    registration_token,
    license_types,
):

    cl = client_library_session
    license_string = license_types

    status = cl.licensing.status()
    if status["product_license"]["active"] == license_string:
        # Trying to set the current license type results in code 400
        pass
    else:
        cl.licensing.set_product_license(license_string)
        assert cl.licensing.status()["product_license"]["active"] == license_string

    cl.licensing.register_wait(token=registration_token, reregister=True)
    # Check if we successfully registered this product license
    status = cl.licensing.status()
    assert status["registration"]["status"] == "COMPLETED"
    assert status["authorization"]["status"] == "IN_COMPLIANCE"

    features = cl.licensing.features()

    # Set every feature to its maximum value
    max_features = {}
    for feature in features:
        max_features[feature["id"]] = feature["max"]
    cl.licensing.update_features(max_features)
    status = cl.licensing.status()
    assert status["registration"]["status"] == "COMPLETED"
    assert status["authorization"]["status"] == "IN_COMPLIANCE"
    # Check that the new values were set
    features = cl.licensing.features()
    for feature in features:
        assert feature["in_use"] == feature["max"]

    # Set every feature to its minimum value
    min_features = {}
    for feature in features:
        min_features[feature["id"]] = 0
    cl.licensing.update_features(min_features)
    status = cl.licensing.status()
    assert status["registration"]["status"] == "COMPLETED"
    assert status["authorization"]["status"] == "IN_COMPLIANCE"
    # Check that the new values were set
    features = cl.licensing.features()
    for feature in features:
        assert feature["in_use"] == feature["min"]

    # Try some bad values
    def check_bad_values(bad_features):
        """
        Helper function. Try updating features with the ones provided. Check that the request fails,
        feature counts are still within expected ranges and licensing is IN_COMPLIANCE.
        """
        features_before = cl.licensing.features()

        with pytest.raises(requests.exceptions.HTTPError) as exc:
            cl.licensing.update_features(bad_features)
        exc.match("400 Client Error: Bad Request for url")

        # Check that feature counts have not changed
        features_after = cl.licensing.features()
        assert len(features_before) == len(features_after)
        for feature_before, feature_after in zip(features_before, features_after):
            assert feature_before["in_use"] == feature_after["in_use"]

        # Check that licensing is still in compliance
        licensing_status = cl.licensing.status()
        assert licensing_status["registration"]["status"] == "COMPLETED"
        assert licensing_status["authorization"]["status"] == "IN_COMPLIANCE"

    # Below minimum feature count
    bad_features_min = {}
    for feature in features:
        bad_features_min[feature["id"]] = int(feature["min"] - 1)
    check_bad_values(bad_features_min)

    # Above maximum feature count
    bad_features_max = {}
    for feature in features:
        bad_features_max[feature["id"]] = int(feature["max"]) + 1
    check_bad_values(bad_features_max)

    # Negative count
    bad_features_negative = {}
    for feature in features:
        bad_features_negative[feature["id"]] = -1
    check_bad_values(bad_features_negative)


def test_slr_basic_actions(
    client_library_session: ClientLibrary, cleanup_reservation_mode
):

    cl = client_library_session

    # Enable reservation mode
    cl.licensing.enable_reservation_mode()
    status = cl.licensing.status()
    assert status["reservation_mode"] is True
    assert status["registration"]["status"] == "NOT_REGISTERED"
    assert status["authorization"]["status"] in ("INIT", "EVAL")

    # Request reservation
    reservation_code = cl.licensing.request_reservation()
    assert len(reservation_code) > 0
    status = cl.licensing.status()
    assert status["reservation_mode"] is True
    assert status["registration"]["status"] == "RESERVATION_IN_PROGRESS"
    assert status["authorization"]["status"] in ("INIT", "EVAL")

    # Cancel reservation request
    cl.licensing.cancel_reservation()
    status = cl.licensing.status()
    assert status["reservation_mode"] is True
    assert status["registration"]["status"] == "NOT_REGISTERED"
    assert status["authorization"]["status"] in ("INIT", "EVAL")

    # Disable reservation mode
    cl.licensing.disable_reservation_mode()
    status = cl.licensing.status()
    assert status["reservation_mode"] is False
    assert status["registration"]["status"] == "NOT_REGISTERED"
    assert status["authorization"]["status"] in ("INIT", "EVAL")


def test_slr_negatives(client_library_session: ClientLibrary, cleanup_reservation_mode):

    cl = client_library_session

    # Enable reservation mode when already enabled
    cl.licensing.enable_reservation_mode()
    cl.licensing.enable_reservation_mode()
    status = cl.licensing.status()
    assert status["reservation_mode"] is True
    assert status["registration"]["status"] == "NOT_REGISTERED"
    assert status["authorization"]["status"] in ("INIT", "EVAL")

    # Cancel reservation when no reservation request has been made
    cl.licensing.cancel_reservation()
    status = cl.licensing.status()
    assert status["reservation_mode"] is True
    assert status["registration"]["status"] == "NOT_REGISTERED"
    assert status["authorization"]["status"] in ("INIT", "EVAL")

    # Disable reservation mode when already disabled
    cl.licensing.disable_reservation_mode()
    cl.licensing.disable_reservation_mode()
    status = cl.licensing.status()
    assert status["reservation_mode"] is False
    assert status["registration"]["status"] == "NOT_REGISTERED"
    assert status["authorization"]["status"] in ("INIT", "EVAL")

    # Generate reservation request when not in reservation mode
    with pytest.raises(requests.exceptions.HTTPError) as exc:
        reservation_code = cl.licensing.request_reservation()
    exc.match("400 Client Error: Bad Request for url*")
    status = cl.licensing.status()
    assert status["reservation_mode"] is False
    assert status["registration"]["status"] == "NOT_REGISTERED"
    assert status["authorization"]["status"] in ("INIT", "EVAL")

    # Cancel reservation request when not in reservation mode
    with pytest.raises(requests.exceptions.HTTPError) as exc:
        cl.licensing.cancel_reservation()
    exc.match("400 Client Error: Bad Request for url*")
    status = cl.licensing.status()
    assert status["reservation_mode"] is False
    assert status["registration"]["status"] == "NOT_REGISTERED"
    assert status["authorization"]["status"] in ("INIT", "EVAL")


# TODO: SLR - mock server responses and test all functions
