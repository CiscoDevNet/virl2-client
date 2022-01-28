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

"""Tests for Licensing feature."""

import pytest
from datetime import datetime
from time import sleep

import requests.exceptions

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
            [
                {"id": features[0]["id"], "count": 1},
                {"id": features[1]["id"], "count": 0},
            ]
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
def cleanup_reservation_mode(client_library_session: ClientLibrary):
    """Make sure reservation mode is disabled after the test."""
    yield
    if client_library_session.licensing.status()["reservation_mode"]:
        client_library_session.licensing.disable_reservation_mode()


def register_wait_fail(client_library_session: ClientLibrary, token, reregister=False):
    """Wait for registration to enter a failed state."""
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


def assert_status(status, mode=False, reg="NOT_REGISTERED", auth=("INIT", "EVAL")):
    assert status["reservation_mode"] is mode
    assert status["registration"]["status"] == reg
    assert status["authorization"]["status"] in auth


def assert_features(features, base_use=1, expn_use=0):
    assert len(features) > 0
    assert features[0]["in_use"] == base_use
    if expn_use is None:
        assert len(features) == 1
    else:
        assert len(features) == 2
        assert features[1]["in_use"] == expn_use


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
    assert_status(cl.licensing.status(), reg="COMPLETED", auth=("IN_COMPLIANCE",))

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
    assert_status(cl.licensing.status(), reg="COMPLETED", auth=("IN_COMPLIANCE",))

    # Deregister
    deregister_wait(client_library_session)
    assert_status(cl.licensing.status())


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
    assert_status(cl.licensing.status(), reg="COMPLETED", auth=("IN_COMPLIANCE",))


def test_registration_invalid_token(
    client_library_session: ClientLibrary,
):
    """Attempt registration with invalid token."""
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


def test_invalid_inputs(client_library_session: ClientLibrary, alpha_ssms_url):
    cl = client_library_session
    base_url = cl.licensing.base_url

    # Empty inputs
    for bad_value in []:  # ""cannot-be-enforced-sadly"]:
        url = base_url + "/registration/renew"
        response = cl.session.put(url, data=bad_value)
        assert response.status_code == 400
        assert "Bad input" in response.text

        url = base_url + "/authorization/renew"
        response = cl.session.put(url, data=bad_value)
        assert response.status_code == 400
        assert "Bad input" in response.text

        url = base_url + "/reservation/request"
        response = cl.session.post(url, data=bad_value)
        assert response.status_code == 400
        assert "Bad input" in response.text

    # product license
    for bad_value in [1, None, "/bad"]:
        with pytest.raises(requests.exceptions.HTTPError) as exc:
            cl.licensing.set_product_license(bad_value)
        exc.match("400 Client Error: Bad Request for url")

    # certificate
    for bad_value in ["", "x" * 4097, "#!/bin/sh\ntouch /tmp/bad\n"]:
        with pytest.raises(requests.exceptions.HTTPError) as exc:
            cl.licensing.install_certificate(bad_value)
        exc.match("400 Client Error: Bad Request for url")

    # transport ssms url and proxy url
    for bad_value in [1, True, "", "x" * 257, "somehost\0badcode"]:
        with pytest.raises(requests.exceptions.HTTPError) as exc:
            cl.licensing.set_transport(bad_value)
        exc.match("400 Client Error: Bad Request for url")
        with pytest.raises(requests.exceptions.HTTPError) as exc:
            cl.licensing.set_transport(alpha_ssms_url, bad_value, 80)
        exc.match("400 Client Error: Bad Request for url")

    # transport port
    for bad_value in [-1, 66000, "123", 1.4, True]:
        with pytest.raises(requests.exceptions.HTTPError) as exc:
            cl.licensing.set_transport(alpha_ssms_url, "localhost", bad_value)
        exc.match("400 Client Error: Bad Request for url")

    # registration
    for bad_value in [-1, 66000, 1.4, None, "", "x" * 257, "token%a\0badcode"]:
        with pytest.raises(requests.exceptions.HTTPError) as exc:
            cl.licensing.register(bad_value)
        exc.match("400 Client Error: Bad Request for url")
        with pytest.raises(requests.exceptions.HTTPError) as exc:
            cl.licensing.register("atoken", bad_value)
        exc.match("400 Client Error: Bad Request for url")

    # reservation mode
    for bad_value in [-1, "false", 1.4, None, "", "none"]:
        with pytest.raises(requests.exceptions.HTTPError) as exc:
            cl.licensing.reservation_mode(bad_value)
        exc.match("400 Client Error: Bad Request for url")

    # reservation complete and discard
    for bad_value in [-1, 66000, 1.4, True, "", "x" * 8193, "token%a\0badcode"]:
        with pytest.raises(requests.exceptions.HTTPError) as exc:
            cl.licensing.complete_reservation(bad_value)
        exc.match("400 Client Error: Bad Request for url")
        assert "reservation mode is disabled" not in exc.value.response.text
        with pytest.raises(requests.exceptions.HTTPError) as exc:
            cl.licensing.discard_reservation(bad_value)
        exc.match("400 Client Error: Bad Request for url")
        assert "reservation mode is disabled" not in exc.value.response.text


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
    assert_status(cl.licensing.status(), reg="COMPLETED", auth=("IN_COMPLIANCE",))

    features = cl.licensing.features()

    # If there are more features, then more must be allowed to be updated
    assert 0 < len(features) <= 2

    # Set every feature to its maximum value
    # old-style map of features
    max_features = {}
    for feature in features:
        max_features[feature["id"]] = feature["max"]
    cl.licensing.update_features(max_features)
    assert_status(cl.licensing.status(), reg="COMPLETED", auth=("IN_COMPLIANCE",))
    # Check that the new values were set
    features = cl.licensing.features()
    for feature in features:
        assert feature["in_use"] == feature["max"]

    # Set every feature to its minimum value
    # new-style list of feature objects
    min_features = []
    for feature in features:
        min_features.append({"id": feature["id"], "count": feature["min"]})
    cl.licensing.update_features(min_features)
    assert_status(cl.licensing.status(), reg="COMPLETED", auth=("IN_COMPLIANCE",))
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
        assert_status(cl.licensing.status(), reg="COMPLETED", auth=("IN_COMPLIANCE",))

    def feature_count_map(feature_list):
        return {feature_obj["id"]: feature_obj["count"] for feature_obj in feature_list}

    def unused_value(feature_obj):
        in_use = feature_obj["in_use"]
        result = feature_obj["min"]
        if result == in_use:
            result += 1
        return result

    # At least one feature needs to change
    check_bad_values([])
    check_bad_values({})

    # Too many features
    feature = features[-1]
    bad_features_many = [
        {"id": features[0]["id"], "count": feature["max"]},
        {"id": features[0]["id"][1:], "count": feature["max"]},
        {"id": features[0]["id"][2:], "count": feature["max"]},
    ]
    check_bad_values(bad_features_many)
    bad_features_many = feature_count_map(bad_features_many)
    check_bad_values(bad_features_many)

    # Id value
    for bad_value in (1.3, None, '" ; bad code()'):
        bad_features_type = [{"id": bad_value, "count": 1}]
        check_bad_values(bad_features_type)

    # Unknown feature mixed in
    bad_features_unknown = [
        {"id": features[0]["id"], "count": unused_value(features[0])},
        {"id": "unknown", "count": 1},
    ]
    check_bad_values(bad_features_unknown)
    bad_features_unknown = feature_count_map(bad_features_unknown)
    check_bad_values(bad_features_unknown)

    # Count value type
    for bad_value in (1.3, None, "1", -1):
        bad_features_type = [{"id": features[0]["id"], "count": bad_value}]
        check_bad_values(bad_features_type)
        bad_features_type = feature_count_map(bad_features_type)
        check_bad_values(bad_features_type)

    bad_features_unused = [
        {"id": feature["id"], "count": unused_value(feature)} for feature in features
    ]
    # Below minimum feature count
    for idx, feature in enumerate(features):
        bad_features_min = list(bad_features_unused)
        bad_value = feature["min"] - 1
        if bad_value < 0:
            # negative check is in schema already
            continue
        bad_features_min[idx] = {"id": feature["id"], "count": bad_value}
        check_bad_values(bad_features_min)

    # Above maximum feature count
    for idx, feature in enumerate(features):
        bad_features_max = list(bad_features_unused)
        bad_value = feature["max"] + 1
        bad_features_max[idx] = {"id": feature["id"], "count": bad_value}
        check_bad_values(bad_features_max)


def test_slr_basic_actions(
    client_library_session: ClientLibrary, cleanup_reservation_mode
):
    cl = client_library_session
    # Enable reservation mode
    assert cl.licensing.enable_reservation_mode() is None
    assert_status(cl.licensing.status(), mode=True, auth=("NOT_AUTHORIZED",))
    # Request reservation
    request_code = cl.licensing.request_reservation()
    assert len(request_code) > 0
    assert_status(
        cl.licensing.status(),
        mode=True,
        reg="RESERVATION_IN_PROGRESS",
        auth=("NOT_AUTHORIZED",),
    )
    # Request code is remembered
    assert cl.licensing.request_reservation() == request_code
    # Feature counts are zeroed
    assert_features(cl.licensing.features(), 0, 0)
    # Cancel reservation request
    assert cl.licensing.cancel_reservation()
    assert_status(cl.licensing.status(), mode=True, auth=("NOT_AUTHORIZED",))
    assert_features(cl.licensing.features(), 0, 0)
    # Request reservation again
    request_code_2 = cl.licensing.request_reservation()
    assert len(request_code_2) > 0
    assert request_code_2 != request_code
    assert_status(
        cl.licensing.status(),
        mode=True,
        reg="RESERVATION_IN_PROGRESS",
        auth=("NOT_AUTHORIZED",),
    )
    # Cancel reservation request
    assert cl.licensing.cancel_reservation()
    assert_status(cl.licensing.status(), mode=True, auth=("NOT_AUTHORIZED",))
    # Disable reservation mode
    assert cl.licensing.disable_reservation_mode() is None
    assert_status(cl.licensing.status())
    # Features' explicit counts restored to defaults
    assert_features(cl.licensing.features(), 1, 0)


def test_slr_negatives(client_library_session: ClientLibrary, cleanup_reservation_mode):
    cl = client_library_session
    invalid_auth_code = """\
<specificPLR>\
  <authorizationCode>\
    <flag>A</flag>\
    <version>C</version>\
    <piid></piid>\
    <timestamp></timestamp>\
    <entitlements>\
      <entitlement>\
        <tag></tag>\
        <count>1</count>\
        <startDate></startDate>\
        <endDate></endDate>\
        <licenseType></licenseType>\
        <displayName></displayName>\
        <tagDescription></tagDescription>\
        <subscriptionID></subscriptionID>\
      </entitlement>\
    </entitlements>\
  </authorizationCode>\
  <signature></signature>\
  <udi></udi>\
</specificPLR>"""

    # Enable reservation mode when already enabled
    assert cl.licensing.enable_reservation_mode() is None
    with pytest.raises(requests.exceptions.HTTPError) as exc:
        cl.licensing.enable_reservation_mode()
    exc.match("400 Client Error: Bad Request for url*")
    assert_status(cl.licensing.status(), mode=True, auth=("NOT_AUTHORIZED",))

    # Complete reservation request with invalid reservation authorization code
    with pytest.raises(requests.exceptions.HTTPError) as exc:
        cl.licensing.complete_reservation(invalid_auth_code)
    exc.match("400 Client Error: Bad Request for url*")
    assert_status(cl.licensing.status(), mode=True, auth=("NOT_AUTHORIZED",))

    # Release reservation request when no reservation is complete
    with pytest.raises(requests.exceptions.HTTPError) as exc:
        cl.licensing.release_reservation()
    exc.match("400 Client Error: Bad Request for url*")
    assert_status(cl.licensing.status(), mode=True, auth=("NOT_AUTHORIZED",))

    # Discard reservation authorization code when requested code is present
    with pytest.raises(requests.exceptions.HTTPError) as exc:
        cl.licensing.discard_reservation(invalid_auth_code)
    exc.match("400 Client Error: Bad Request for url*")
    assert_status(cl.licensing.status(), mode=True, auth=("NOT_AUTHORIZED",))

    # Cancel reservation when no reservation request has been made
    assert cl.licensing.cancel_reservation()
    assert_status(cl.licensing.status(), mode=True, auth=("NOT_AUTHORIZED",))

    # Discard invalid reservation authorization code
    with pytest.raises(requests.exceptions.HTTPError) as exc:
        cl.licensing.discard_reservation(invalid_auth_code)
    exc.match("400 Client Error: Bad Request for url*")
    assert_status(cl.licensing.status(), mode=True, auth=("NOT_AUTHORIZED",))

    # Disable reservation mode when already disabled
    assert cl.licensing.disable_reservation_mode() is None
    assert_status(cl.licensing.status())
    with pytest.raises(requests.exceptions.HTTPError) as exc:
        cl.licensing.disable_reservation_mode()
    exc.match("400 Client Error: Bad Request for url*")
    assert_status(cl.licensing.status())

    # Generate reservation request when not in reservation mode
    with pytest.raises(requests.exceptions.HTTPError) as exc:
        cl.licensing.request_reservation()
    exc.match("400 Client Error: Bad Request for url*")
    assert_status(cl.licensing.status())

    # Complete reservation request when not in reservation mode
    with pytest.raises(requests.exceptions.HTTPError) as exc:
        cl.licensing.complete_reservation(invalid_auth_code)
    exc.match("400 Client Error: Bad Request for url*")
    assert_status(cl.licensing.status())

    # Release reservation request when not in reservation mode
    with pytest.raises(requests.exceptions.HTTPError) as exc:
        cl.licensing.release_reservation()
    exc.match("400 Client Error: Bad Request for url*")
    assert_status(cl.licensing.status())

    # Cancel reservation request when not in reservation mode
    with pytest.raises(requests.exceptions.HTTPError) as exc:
        cl.licensing.cancel_reservation()
    exc.match("400 Client Error: Bad Request for url*")
    assert_status(cl.licensing.status())

    # Discard reservation request when not in reservation mode
    with pytest.raises(requests.exceptions.HTTPError) as exc:
        cl.licensing.discard_reservation(invalid_auth_code)
    exc.match("400 Client Error: Bad Request for url*")
    assert_status(cl.licensing.status())

    # Delete non-existent confirmation code
    assert cl.licensing.get_reservation_confirmation_code() is None
    with pytest.raises(requests.exceptions.HTTPError) as exc:
        cl.licensing.delete_reservation_confirmation_code()
    exc.match("400 Client Error: Bad Request for url*")

    # Delete non-existent return code
    assert cl.licensing.get_reservation_return_code() is None
    with pytest.raises(requests.exceptions.HTTPError) as exc:
        cl.licensing.delete_reservation_return_code()
    exc.match("400 Client Error: Bad Request for url*")


# TODO: SLR - mock server responses and test all functions
