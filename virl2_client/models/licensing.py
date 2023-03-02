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

import logging
import time
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    import httpx

_LOGGER = logging.getLogger(__name__)

DEFAULT_PROXY_SERVER = None
DEFAULT_PROXY_PORT = None


class Licensing:

    max_wait = 30
    wait_interval = 1.5

    def __init__(self, session: httpx.Client) -> None:
        self._session = session

    @property
    def base_url(self) -> str:
        return "licensing"

    def status(self) -> dict[str, Any]:
        """
        Get current licensing configuration and status.
        """
        return self._session.get(self.base_url).json()

    def tech_support(self) -> str:
        """
        Get current licensing tech support.
        """
        url = self.base_url + "/tech_support"
        return self._session.get(url).text

    def renew_authorization(self) -> bool:
        """
        Renew licensing authorization with the backend.
        """
        url = self.base_url + "/authorization/renew"
        response = self._session.put(url)
        _LOGGER.info("The agent has scheduled an authorization renewal.")
        return response.status_code == 204

    def set_transport(
        self,
        ssms: str,
        proxy_server: Optional[str] = None,
        proxy_port: Optional[int] = None,
    ) -> bool:
        """
        Setup licensing transport configuration.
        """
        url = self.base_url + "/transport"
        data = {"ssms": ssms, "proxy": {"server": proxy_server, "port": proxy_port}}
        response = self._session.put(url, json=data)
        _LOGGER.info("The transport configuration has been accepted. Config: %s.", data)
        return response.status_code == 204

    def set_default_transport(self) -> bool:
        """
        Setup licensing transport configuration to default values.
        """
        default_ssms = self.status()["transport"]["default_ssms"]
        return self.set_transport(
            ssms=default_ssms,
            proxy_server=DEFAULT_PROXY_SERVER,
            proxy_port=DEFAULT_PROXY_PORT,
        )

    def set_product_license(self, product_license: str) -> bool:
        """
        Setup a product license.
        """
        url = self.base_url + "/product_license"
        response = self._session.put(url, json=product_license)
        _LOGGER.info("Product license was accepted by the agent.")
        return response.status_code == 204

    def get_certificate(self) -> Optional[str]:
        """
        Get the currently installed licensing public certificate.
        """
        url = self.base_url + "/certificate"
        response = self._session.get(url)
        if response.is_success:
            _LOGGER.info("Certificate received.")
            return response.json()
        return None

    def install_certificate(self, cert: str) -> bool:
        """
        Set up a licensing public certificate for internal deployment
        of an unregistered product instance.
        """
        url = self.base_url + "/certificate"
        response = self._session.post(url, content=cert)
        _LOGGER.info("Certificate was accepted by the agent.")
        return response.status_code == 204

    def remove_certificate(self) -> bool:
        """
        Clear any licensing public certificate for internal deployment
        of an unregistered product instance.
        """
        url = self.base_url + "/certificate"
        response = self._session.delete(url)
        _LOGGER.info("Certificate was removed.")
        return response.status_code == 204

    def register(self, token: str, reregister=False) -> bool:
        """
        Setup licensing registration.
        """
        url = self.base_url + "/registration"
        response = self._session.post(
            url, json={"token": token, "reregister": reregister}
        )
        _LOGGER.info("Registration request was accepted by the agent.")
        return response.status_code == 204

    def register_renew(self) -> bool:
        """
        Request a renewal of licensing registration against current SSMS.
        """
        url = self.base_url + "/registration/renew"
        response = self._session.put(url)
        _LOGGER.info("The renewal request was accepted by the agent.")
        return response.status_code == 204

    def register_wait(self, token: str, reregister=False) -> bool:
        """
        Setup licensing registrations and wait for registration status
        to be COMPLETED and authorization status to be IN_COMPLIANCE.
        """
        res = self.register(token=token, reregister=reregister)
        self.wait_for_status("registration", "COMPLETED")
        self.wait_for_status("authorization", "IN_COMPLIANCE")
        return res

    def deregister(self) -> int:
        """
        Request deregistration from the current SSMS.
        """
        url = self.base_url + "/deregistration"
        response = self._session.delete(url)
        if response.status_code == 202:
            _LOGGER.warning(
                "Deregistration has been completed on the Product Instance but was "
                "unable to deregister from Smart Software Licensing due to a "
                "communication timeout."
            )
            # TODO try to register again and unregister
        if response.status_code == 204:
            _LOGGER.info(
                "The Product Instance was successfully deregistered from Smart "
                "Software Licensing."
            )
        return response.status_code

    def features(self) -> list[dict[str, str | int]]:
        """
        Get current licensing features.
        """
        url = self.base_url + "/features"
        return self._session.get(url).json()

    def update_features(self, features: dict[str, int] | list[dict[str, int]]) -> None:
        """
        Update licensing feature's explicit count in reservation mode.
        """
        url = self.base_url + "/features"
        self._session.patch(url, json=features)

    def reservation_mode(self, data: bool) -> None:
        """
        Enable or disable reservation mode in unregistered agent.
        """
        url = self.base_url + "/reservation/mode"
        self._session.put(url, json=data)
        msg = "enabled" if data else "disabled"
        _LOGGER.info("The reservation mode has been %s.", msg)

    def enable_reservation_mode(self) -> None:
        """
        Enable reservation mode in unregistered agent.
        """
        return self.reservation_mode(data=True)

    def disable_reservation_mode(self) -> None:
        """
        Disable reservation mode in unregistered agent.
        """
        return self.reservation_mode(data=False)

    def request_reservation(self) -> str:
        """
        Initiate reservation by generating request code and message to the user.
        """
        url = self.base_url + "/reservation/request"
        response = self._session.post(url)
        _LOGGER.info("Reservation request code received.")
        return response.json()

    def complete_reservation(self, authorization_code: str) -> str:
        """
        Complete reservation by installing authorization code from SSMS.
        """
        # TODO
        url = self.base_url + "/reservation/complete"
        response = self._session.post(url, json=authorization_code)
        _LOGGER.info("The confirmation code of completed reservation received.")
        return response.json()

    def cancel_reservation(self) -> bool:
        """
        Cancel reservation request without completing it.
        """
        url = self.base_url + "/reservation/cancel"
        response = self._session.delete(url)
        _LOGGER.info("The reservation request has been cancelled.")
        return response.status_code == 204

    def release_reservation(self) -> str:
        """
        Return a completed reservation.
        """
        # TODO
        url = self.base_url + "/reservation/release"
        response = self._session.delete(url)
        _LOGGER.info("The return code of the released reservation received.")
        return response.json()

    def discard_reservation(self, data: str) -> str:
        """
        Discard a reservation authorization code for an already cancelled
        reservation request.
        """
        # TODO
        url = self.base_url + "/reservation/discard"
        response = self._session.post(url, json=data)
        _LOGGER.info(
            "The discard code for an already cancelled reservation request received."
        )
        return response.json()

    def get_reservation_confirmation_code(self) -> str:
        """
        Get the confirmation code.
        """
        url = self.base_url + "/reservation/confirmation_code"
        response = self._session.get(url)
        _LOGGER.info("The confirmation code of the completed reservation received.")
        return response.json()

    def delete_reservation_confirmation_code(self) -> bool:
        """
        Remove the confirmation code.
        """
        url = self.base_url + "/reservation/confirmation_code"
        response = self._session.delete(url)
        _LOGGER.info("The confirmation code has been removed.")
        return response.status_code == 204

    def get_reservation_return_code(self) -> str:
        """
        Get the return code.
        """
        url = self.base_url + "/reservation/return_code"
        response = self._session.get(url)
        _LOGGER.info("The return code of the released reservation received.")
        return response.json()

    def delete_reservation_return_code(self) -> bool:
        """
        Remove the return code.
        """
        url = self.base_url + "/reservation/return_code"
        response = self._session.delete(url)
        _LOGGER.info("The return code has been removed.")
        return response.status_code == 204

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
                    "Timeout: licensing {} did not reach {} status after {} secs. "
                    "Last status was {}".format(what, target_status, timeout, status)
                )
            status = self.status()[what]["status"]
            _LOGGER.debug("%s status: %s", what, status)
            count += 1
