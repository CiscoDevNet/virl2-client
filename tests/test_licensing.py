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
"""Tests for Licensing API wrappers."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from virl2_client.exceptions import APIError
from virl2_client.models import Licensing


def test_licensing_status() -> None:
    """status returns transport and registration info.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    lic = Licensing(session)
    session.get.return_value.json.return_value = {"transport": {"default_ssms": "x"}}
    assert lic.status()["transport"]["default_ssms"] == "x"


def test_licensing_tech_support() -> None:
    """tech_support returns support text.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    lic = Licensing(session)
    session.get.return_value.text = "support"
    assert lic.tech_support() == "support"


def test_licensing_renew_auth() -> None:
    """renew_authorization returns the licensing status snapshot.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    lic = Licensing(session)
    session.put.return_value.json.return_value = {
        "authorization": {"status": "IN_COMPLIANCE"}
    }
    assert lic.renew_authorization() == {"authorization": {"status": "IN_COMPLIANCE"}}


def test_licensing_set_transport() -> None:
    """set_transport calls patch with ssms and proxy params and returns body.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    lic = Licensing(session)
    session.patch.return_value.json.return_value = {"transport": {"ssms": "ssms"}}
    assert lic.set_transport("ssms", proxy_server="proxy", proxy_port=443) == {
        "transport": {"ssms": "ssms"}
    }
    session.patch.assert_called_once_with(
        "licensing/transport",
        json={"ssms": "ssms", "proxy": {"server": "proxy", "port": 443}},
    )


def test_licensing_set_transport_put_fallback() -> None:
    """Pre-2.11 controllers reject PATCH; fall back to PUT and status() on 204."""
    session = MagicMock()
    lic = Licensing(session)
    request = httpx.Request("PATCH", "https://controller/licensing/transport")
    patch_response = httpx.Response(405, request=request)
    put_response = MagicMock()
    put_response.status_code = 204
    lic.status = MagicMock(return_value={"transport": {"ssms": "legacy"}})

    session.patch.side_effect = APIError(
        "405", request=request, response=patch_response
    )
    session.put.return_value = put_response

    assert lic.set_transport("ssms") == {"transport": {"ssms": "legacy"}}
    session.put.assert_called_once_with(
        "licensing/transport",
        json={"ssms": "ssms", "proxy": {"server": None, "port": None}},
    )
    lic.status.assert_called_once()


def test_licensing_set_product_lic() -> None:
    """set_product_license calls put with product id and returns body.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    lic = Licensing(session)
    session.put.return_value.json.return_value = {"product_license": {"active": "prod"}}
    assert lic.set_product_license("prod") == {"product_license": {"active": "prod"}}


def test_licensing_set_product_license_204() -> None:
    """Pre-2.11 controllers returned 204 No Content; fall back to status()."""
    session = MagicMock()
    lic = Licensing(session)
    session.put.return_value.status_code = 204
    lic.status = MagicMock(return_value={"product_license": {"active": "prod"}})
    assert lic.set_product_license("prod") == {"product_license": {"active": "prod"}}
    lic.status.assert_called_once()


def test_licensing_register_renew() -> None:
    """register_renew calls put and returns licensing status snapshot.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    lic = Licensing(session)
    session.put.return_value.json.return_value = {
        "registration": {"status": "COMPLETED"}
    }
    assert lic.register_renew() == {"registration": {"status": "COMPLETED"}}


@pytest.mark.parametrize(
    "method",
    [
        "delete_reservation_confirmation_code",
        "delete_reservation_return_code",
    ],
)
def test_licensing_del_code_rt(method: str) -> None:
    """delete_reservation_*_code returns the licensing status snapshot.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    lic = Licensing(session)
    session.delete.return_value.json.return_value = {"reservation_mode": False}
    assert getattr(lic, method)() == {"reservation_mode": False}


def test_licensing_register() -> None:
    """register posts token and returns licensing status snapshot.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    lic = Licensing(session)
    session.post.return_value.json.return_value = {
        "registration": {"status": "IN_PROGRESS"}
    }
    assert lic.register("token") == {"registration": {"status": "IN_PROGRESS"}}


def test_licensing_cancel_reservation() -> None:
    """cancel_reservation deletes reservation and returns licensing status.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    lic = Licensing(session)
    session.delete.return_value.json.return_value = {"reservation_mode": True}
    assert lic.cancel_reservation() == {"reservation_mode": True}


def test_licensing_request_reservation() -> None:
    """request_reservation posts and returns code.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    lic = Licensing(session)
    session.post.return_value.json.return_value = {"code": "abc"}
    assert lic.request_reservation() == {"code": "abc"}


def test_licensing_complete_reservation() -> None:
    """complete_reservation posts auth and returns code.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    lic = Licensing(session)
    session.post.return_value.json.return_value = {"code": "abc"}
    assert lic.complete_reservation("auth") == {"code": "abc"}


def test_licensing_discard_reservation() -> None:
    """discard_reservation posts discard and returns code.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    lic = Licensing(session)
    session.post.return_value.json.return_value = {"code": "abc"}
    assert lic.discard_reservation("discard") == {"code": "abc"}


def test_licensing_release_reservation() -> None:
    """release_reservation deletes and returns code.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    lic = Licensing(session)
    session.delete.return_value.json.return_value = {"code": "xyz"}
    assert lic.release_reservation() == {"code": "xyz"}


@pytest.mark.parametrize(
    "method",
    [
        "get_reservation_confirmation_code",
        "get_reservation_return_code",
    ],
)
def test_licensing_get_code_rt(method: str) -> None:
    """get_reservation_*_code returns code dict.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    lic = Licensing(session)
    session.get.return_value.json.return_value = {"code": "ret"}
    assert getattr(lic, method)() == {"code": "ret"}


def test_licensing_deregister_success() -> None:
    """deregister returns the licensing status snapshot on the 200 path.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lic = Licensing(MagicMock())
    lic._session.delete.return_value.status_code = 200
    lic._session.delete.return_value.json.return_value = {
        "registration": {"status": "NOT_REGISTERED"}
    }
    assert lic.deregister() == {"registration": {"status": "NOT_REGISTERED"}}


def test_licensing_deregister_manual_required() -> None:
    """deregister tags the body with manual_deregistration_required on HTTP 202.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lic = Licensing(MagicMock())
    lic._session.delete.return_value.status_code = 202
    lic._session.delete.return_value.json.return_value = {
        "registration": {"status": "NOT_REGISTERED"}
    }
    result = lic.deregister()
    assert result["manual_deregistration_required"] is True
    assert result["registration"] == {"status": "NOT_REGISTERED"}


def test_licensing_features_deprecated() -> None:
    """features triggers deprecation warning.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lic = Licensing(MagicMock())
    with (
        patch.object(lic, "status", return_value={"features": []}),
        pytest.deprecated_call(),
    ):
        assert lic.features() == []


def test_licensing_register_wait_polls_when_in_progress() -> None:
    """register_wait polls when the initial snapshot is not at the target state.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    lic = Licensing(session)
    session.post.return_value.json.return_value = {
        "registration": {"status": "IN_PROGRESS"},
        "authorization": {"status": "EVAL"},
    }
    final_status = {
        "registration": {"status": "COMPLETED"},
        "authorization": {"status": "IN_COMPLIANCE"},
    }

    with (
        patch.object(lic, "wait_for_status", return_value=None) as wait_for_status,
        patch.object(lic, "status", return_value=final_status),
    ):
        assert lic.register_wait("token-1", reregister=True) == final_status
        wait_for_status.assert_any_call("registration", "COMPLETED")
        wait_for_status.assert_any_call("authorization", "IN_COMPLIANCE")


def test_licensing_register_wait_short_circuits_on_terminal_snapshot() -> None:
    """register_wait skips polling when the snapshot already reports target states.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    lic = Licensing(session)
    terminal = {
        "registration": {"status": "COMPLETED"},
        "authorization": {"status": "IN_COMPLIANCE"},
    }
    session.post.return_value.json.return_value = terminal

    with (
        patch.object(lic, "wait_for_status", return_value=None) as wait_for_status,
        patch.object(lic, "status", return_value=terminal),
    ):
        assert lic.register_wait("token-1") == terminal
        wait_for_status.assert_not_called()


def test_licensing_update_features() -> None:
    """update_features patches licensing features and returns body.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    lic = Licensing(session)
    features_payload = [{"id": "featureA", "count": 1}]
    session.patch.return_value.json.return_value = {"features": [{"id": "featureA"}]}
    assert lic.update_features(features_payload) == {"features": [{"id": "featureA"}]}
    session.patch.assert_called_with("licensing/features", json=features_payload)


def test_licensing_reservation_mode_set() -> None:
    """reservation_mode puts mode with json value and returns body.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    lic = Licensing(session)
    session.put.return_value.json.return_value = {"reservation_mode": True}
    assert lic.reservation_mode(True) == {"reservation_mode": True}
    session.put.assert_called_with("licensing/reservation/mode", json=True)


@pytest.mark.parametrize(
    ("method", "expected_json"),
    [
        ("enable_reservation_mode", True),
        ("disable_reservation_mode", False),
    ],
)
def test_licensing_reservation_mode_rt(method: str, expected_json: bool) -> None:
    """enable/disable_reservation_mode puts mode with json value and returns body.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    lic = Licensing(session)
    session.put.return_value.json.return_value = {"reservation_mode": expected_json}
    assert getattr(lic, method)() == {"reservation_mode": expected_json}
    session.put.assert_called_with("licensing/reservation/mode", json=expected_json)


def test_licensing_wait_status_ok() -> None:
    """wait_for_status succeeds when status matches.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    lic = Licensing(session)

    with (
        patch.object(
            lic,
            "status",
            side_effect=[
                {"registration": {"status": "PENDING"}},
                {"registration": {"status": "COMPLETED"}},
            ],
        ),
        patch("virl2_client.models.licensing.time.sleep", return_value=None),
    ):
        lic.wait_for_status("registration", "COMPLETED")


def test_licensing_wait_status_timeout() -> None:
    """wait_for_status raises RuntimeError on timeout.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    lic = Licensing(session)
    lic.max_wait = 1
    lic.wait_interval = 0

    with (
        patch.object(
            lic, "status", return_value={"registration": {"status": "PENDING"}}
        ),
        patch("virl2_client.models.licensing.time.sleep", return_value=None),
        pytest.raises(RuntimeError, match="Timeout: licensing registration"),
    ):
        lic.wait_for_status("registration", "COMPLETED")


def test_licensing_default_transport() -> None:
    """set_default_transport uses status transport and set_transport.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    lic = Licensing(session)

    with (
        patch.object(
            lic, "status", return_value={"transport": {"default_ssms": "https://ssms"}}
        ),
        patch.object(lic, "set_transport", return_value={"ok": True}) as set_transport,
    ):
        assert lic.set_default_transport() == {"ok": True}
        set_transport.assert_called_once_with(
            ssms="https://ssms", proxy_server=None, proxy_port=None
        )
