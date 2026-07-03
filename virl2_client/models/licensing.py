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

import logging
import time
import warnings
from typing import TYPE_CHECKING, Any, ClassVar

from virl2_client.exceptions import APIError

from ..utils import get_url_from_template

if TYPE_CHECKING:
    import httpx

_LOGGER = logging.getLogger(__name__)

DEFAULT_PROXY_SERVER = None
DEFAULT_PROXY_PORT = None


class Licensing:
    _URL_TEMPLATES: ClassVar[dict[str, str]] = {
        "licensing": "licensing",
        "tech_support": "licensing/tech_support",
        "authorization_renew": "licensing/authorization/renew",
        "transport": "licensing/transport",
        "product_license": "licensing/product_license",
        "registration": "licensing/registration",
        "registration_renew": "licensing/registration/renew",
        "deregistration": "licensing/deregistration",
        "features": "licensing/features",
        "reservation_action": "licensing/reservation/{action}",
    }
    max_wait = 30
    wait_interval = 1.5

    def __init__(self, session: httpx.Client) -> None:
        """
        Manage licensing.

        :param session: The httpx-based HTTP client for this session with the server.
        """
        self._session = session

    def _url_for(self, endpoint: str, **kwargs: str) -> str:
        """
        Generate the URL for a given API endpoint.

        :param endpoint: The desired endpoint.
        :param kwargs: Keyword arguments used to format the URL.
        :returns: The formatted URL.
        """
        return get_url_from_template(endpoint, self._URL_TEMPLATES, kwargs)

    def status(self) -> dict[str, Any]:
        """Return current licensing configuration and status.

        :returns: Licensing configuration and status dictionary.
        """
        url = self._url_for("licensing")
        return self._session.get(url).json()

    def tech_support(self) -> str:
        """Return current licensing tech support.

        :returns: Tech support information as text.
        """
        url = self._url_for("tech_support")
        return self._session.get(url).text

    def renew_authorization(self) -> dict[str, Any]:
        """Renew licensing authorization with the backend.

        :returns: Effective licensing status snapshot after the renewal was scheduled.
        """
        url = self._url_for("authorization_renew")
        response = self._session.put(url)
        _LOGGER.info("The agent has scheduled an authorization renewal.")
        return self._status_response(response)

    def _status_response(self, response: httpx.Response) -> dict[str, Any]:
        """Return the effective licensing status from a mutation response.

        CML 2.11+ returns the effective ``LicensingStatus`` body on 200/202.
        Pre-2.11 controllers reply with 204 No Content and no body; in that
        case a follow-up ``GET /licensing`` is issued to preserve the return
        contract.
        """
        if response.status_code == 204:
            return self.status()
        return response.json()

    def set_transport(
        self,
        ssms: str | None,
        proxy_server: str | None = None,
        proxy_port: int | None = None,
    ) -> dict[str, Any]:
        """Partially update licensing transport configuration.

        :param ssms: The Smart Software Licensing server URL.
        :param proxy_server: Optional proxy server hostname.
        :param proxy_port: Optional proxy server port.
        :returns: Effective updated licensing status.
        """
        url = self._url_for("transport")
        data = {"ssms": ssms, "proxy": {"server": proxy_server, "port": proxy_port}}
        try:
            response = self._session.patch(url, json=data)
        except APIError as error:
            # PATCH /licensing/transport was added in 2.11; pre-2.11 only supports PUT.
            if error.response.status_code != 405:
                raise
            response = self._session.put(url, json=data)
        _LOGGER.info("The transport configuration has been updated. Config: %s.", data)
        return self._status_response(response)

    def set_default_transport(self) -> dict[str, Any]:
        """Setup licensing transport configuration to default values.

        :returns: Effective updated licensing status.
        """
        default_ssms = self.status()["transport"]["default_ssms"]
        return self.set_transport(
            ssms=default_ssms,
            proxy_server=DEFAULT_PROXY_SERVER,
            proxy_port=DEFAULT_PROXY_PORT,
        )

    def set_product_license(self, product_license: str) -> dict[str, Any]:
        """Setup a product license.

        :param product_license: The product license string to install.
        :returns: Effective updated licensing status.
        """
        url = self._url_for("product_license")
        response = self._session.put(url, json=product_license)
        _LOGGER.info("Product license was accepted by the agent.")
        return self._status_response(response)

    def register(self, token: str, reregister: bool = False) -> dict[str, Any]:
        """Setup licensing registration.

        :param token: The registration token.
        :param reregister: Whether to re-register if already registered.
        :returns: Effective licensing status snapshot after the request was
            accepted (registration is typically still IN_PROGRESS or
            RETRY_IN_PROGRESS).
        """
        url = self._url_for("registration")
        response = self._session.post(
            url, json={"token": token, "reregister": reregister}
        )
        _LOGGER.info("Registration request was accepted by the agent.")
        return self._status_response(response)

    def register_renew(self) -> dict[str, Any]:
        """Request a renewal of licensing registration against current SSMS.

        :returns: Effective licensing status snapshot after the renewal request
            was accepted.
        """
        url = self._url_for("registration_renew")
        response = self._session.put(url)
        _LOGGER.info("The renewal request was accepted by the agent.")
        return self._status_response(response)

    def register_wait(self, token: str, reregister: bool = False) -> dict[str, Any]:
        """
        Setup licensing registration and wait for registration status to be
        COMPLETED and authorization status to be IN_COMPLIANCE.

        The initial registration response carries the post-mutation snapshot;
        the polling loops are skipped if the snapshot already reports the
        target state.

        :param token: The registration token.
        :param reregister: Whether to re-register if already registered.
        :returns: Effective licensing status snapshot once both registration and
            authorization have reached their target states.
        :raises RuntimeError: If the status does not reach the target within timeout.
        """
        status = self.register(token=token, reregister=reregister)
        if status.get("registration", {}).get("status") != "COMPLETED":
            self.wait_for_status("registration", "COMPLETED")
        if status.get("authorization", {}).get("status") != "IN_COMPLIANCE":
            self.wait_for_status("authorization", "IN_COMPLIANCE")
        return self.status()

    def deregister(self) -> dict[str, Any]:
        """Request deregistration from the current SSMS.

        On the manual-deregistration branch (HTTP 202) the Product Instance has
        been deregistered locally, but the client was unable to contact Smart
        Software Licensing to complete the remote removal; a warning is logged
        so operators can clean up the Product Instance in SSMS manually.

        :returns: Effective licensing status snapshot after deregistration.
        """
        url = self._url_for("deregistration")
        response = self._session.delete(url)
        if response.status_code == 202:
            _LOGGER.warning(
                "Deregistration has been completed on the Product Instance but was "
                "unable to deregister from Smart Software Licensing due to a "
                "communication timeout."
            )
        else:
            _LOGGER.info(
                "The Product Instance was successfully deregistered from Smart "
                "Software Licensing."
            )
        return self._status_response(response)

    def features(self) -> list[dict[str, str | int]] | None:
        """
        DEPRECATED: Use .status() instead.
        (Reason: dropped in favor of single call to get the whole licensing status)

        Get current licensing features.

        :returns: List of feature definitions from the licensing status.
        """
        warnings.warn(
            "'Licensing.features()' is deprecated. "
            "Use '.status()[\"features\"]' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.status().get("features")

    def update_features(self, features: list[dict[str, str | int]]) -> dict[str, Any]:
        """Update licensing feature's explicit count in reservation mode.

        :param features: List of {"id": "<feature>", "count": <int>} objects.
        :returns: Effective updated licensing status.
        """
        url = self._url_for("features")
        response = self._session.patch(url, json=features)
        return self._status_response(response)

    def reservation_mode(self, data: bool) -> dict[str, Any]:
        """Enable or disable reservation mode in unregistered agent.

        :param data: True to enable, False to disable.
        :returns: Effective updated licensing status.
        """
        url = self._url_for("reservation_action", action="mode")
        response = self._session.put(url, json=data)
        msg = "enabled" if data else "disabled"
        _LOGGER.info("The reservation mode has been %s.", msg)
        return self._status_response(response)

    def enable_reservation_mode(self) -> dict[str, Any]:
        """Enable reservation mode in unregistered agent."""
        return self.reservation_mode(data=True)

    def disable_reservation_mode(self) -> dict[str, Any]:
        """Disable reservation mode in unregistered agent."""
        return self.reservation_mode(data=False)

    def request_reservation(self) -> Any:
        """Initiate reservation by generating request code and message to the user.

        :returns: The reservation request code and message from the server.
        """
        url = self._url_for("reservation_action", action="request")
        response = self._session.post(url)
        _LOGGER.info("Reservation request code received.")
        return response.json()

    def complete_reservation(self, authorization_code: str) -> Any:
        """Complete reservation by installing authorization code from SSMS.

        :param authorization_code: The authorization code from SSMS.
        :returns: The confirmation code from the server.
        """
        url = self._url_for("reservation_action", action="complete")
        response = self._session.post(url, json=authorization_code)
        _LOGGER.info("The confirmation code of completed reservation received.")
        return response.json()

    def cancel_reservation(self) -> dict[str, Any]:
        """Cancel reservation request without completing it.

        :returns: Effective licensing status snapshot after the cancellation.
        """
        url = self._url_for("reservation_action", action="cancel")
        response = self._session.delete(url)
        _LOGGER.info("The reservation request has been cancelled.")
        return self._status_response(response)

    def release_reservation(self) -> Any:
        """Return a completed reservation.

        :returns: The return code from the server.
        """
        url = self._url_for("reservation_action", action="release")
        response = self._session.delete(url)
        _LOGGER.info("The return code of the released reservation received.")
        return response.json()

    def discard_reservation(self, data: str) -> Any:
        """
        Discard a reservation authorization code for an already cancelled
        reservation request.

        :param data: The discard code or data to submit.
        :returns: The response from the server.
        """
        url = self._url_for("reservation_action", action="discard")
        response = self._session.post(url, json=data)
        _LOGGER.info(
            "The discard code for an already cancelled reservation request received."
        )
        return response.json()

    def get_reservation_confirmation_code(self) -> Any:
        """Get the reservation confirmation code.

        :returns: The confirmation code from the server.
        """
        url = self._url_for("reservation_action", action="confirmation_code")
        response = self._session.get(url)
        _LOGGER.info("The confirmation code of the completed reservation received.")
        return response.json()

    def delete_reservation_confirmation_code(self) -> dict[str, Any]:
        """Remove the reservation confirmation code.

        :returns: Effective licensing status snapshot after removal.
        """
        url = self._url_for("reservation_action", action="confirmation_code")
        response = self._session.delete(url)
        _LOGGER.info("The confirmation code has been removed.")
        return self._status_response(response)

    def get_reservation_return_code(self) -> Any:
        """Get the reservation return code.

        :returns: The return code from the server.
        """
        url = self._url_for("reservation_action", action="return_code")
        response = self._session.get(url)
        _LOGGER.info("The return code of the released reservation received.")
        return response.json()

    def delete_reservation_return_code(self) -> dict[str, Any]:
        """Remove the reservation return code.

        :returns: Effective licensing status snapshot after removal.
        """
        url = self._url_for("reservation_action", action="return_code")
        response = self._session.delete(url)
        _LOGGER.info("The return code has been removed.")
        return self._status_response(response)

    def wait_for_status(self, what: str, *target_status: str) -> None:
        """
        Repeatedly check licensing registration or authorization status,
        until status matches one of the expected statuses or timeout is reached.

        :param what: "registration", "authorization" or other status in licensing API.
        :param target_status: One or more expected statuses.
        :raises RuntimeError: When timeout is reached.
        """
        count = 0
        status = self.status().get(what, {}).get("status")
        while status not in target_status:
            time.sleep(self.wait_interval)
            if count > self.max_wait:
                timeout = self.max_wait * self.wait_interval
                raise RuntimeError(
                    f"Timeout: licensing {what} did not reach {target_status} status "
                    f"after {timeout} secs. Last status was {status}"
                )
            status = self.status()[what]["status"]
            _LOGGER.debug("%s status: %s", what, status)
            count += 1
