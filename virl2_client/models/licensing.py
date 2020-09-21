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

import time
import logging


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

DEFAULT_SSMS = "https://tools.cisco.com/its/service/oddce/services/DDCEService"
DEFAULT_PROXY_SERVER = None
DEFAULT_PROXY_PORT = None


class Licensing(object):

    max_wait = 30
    wait_interval = 1.5

    def __init__(self, context):
        self.ctx = context

    @property
    def base_url(self):
        return self.ctx.base_url + "licensing"

    def status(self):
        """
        Get current licensing configuration and status.
        """
        response = self.ctx.session.get(self.base_url)
        response.raise_for_status()
        return response.json()

    def tech_support(self):
        """
        Get current licensing tech support.
        """
        url = self.base_url + "/tech_support"
        response = self.ctx.session.get(url)
        response.raise_for_status()
        return response.text

    def renew_authorization(self):
        """
        Renew licensing authorization with the backend.
        """
        url = self.base_url + "/authorization/renew"
        response = self.ctx.session.put(url)
        response.raise_for_status()
        logger.info("The agent has scheduled an authorization renewal.")
        return response.status_code == 204

    def set_transport(self, ssms, proxy_server=None, proxy_port=None):
        """
        Setup licensing transport configuration.
        """
        url = self.base_url + "/transport"
        data = {"ssms": ssms, "proxy": {"server": proxy_server, "port": proxy_port}}
        response = self.ctx.session.put(url, json=data)
        response.raise_for_status()
        logger.info("The transport configuration has been accepted. Config: %s.", data)
        return response.status_code == 204

    def set_default_transport(self):
        """
        Setup licensing transport configuration to default values.
        """
        return self.set_transport(
            ssms=DEFAULT_SSMS,
            proxy_server=DEFAULT_PROXY_SERVER,
            proxy_port=DEFAULT_PROXY_PORT,
        )

    def get_certificate(self):
        """
        Setup a licensing public certificate for internal deployment
        of an unregistered product instance.
        """
        url = self.base_url + "/certificate"
        response = self.ctx.session.get(url)
        response.raise_for_status()
        logger.info("Certificate was accepted by the agent.")
        if response:
            return response.json()

    def install_certificate(self, cert):
        """
        Setup a licensing public certificate for internal deployment
        of an unregistered product instance.
        """
        url = self.base_url + "/certificate"
        response = self.ctx.session.post(url, data=cert)
        response.raise_for_status()
        logger.info("Certificate was accepted by the agent.")
        return response.status_code == 204

    def remove_certificate(self):
        """
        Clear any licensing public certificate for internal deployment
        of an unregistered product instance.
        """
        url = self.base_url + "/certificate"
        response = self.ctx.session.delete(url)
        response.raise_for_status()
        logger.info("Certificate was removed.")
        return response.status_code == 204

    def register(self, token, reregister=False):
        """
        Setup licensing registration.
        """
        url = self.base_url + "/registration"
        response = self.ctx.session.post(
            url, json={"token": token, "reregister": reregister}
        )
        response.raise_for_status()
        logger.info("Registration request was accepted by the agent.")
        return response.status_code == 204

    def register_renew(self):
        """
        Request a renewal of licensing registration against current SSMS.
        """
        url = self.base_url + "/registration/renew"
        response = self.ctx.session.put(url)
        response.raise_for_status()
        logger.info("The renewal request was accepted by the agent.")
        return response.status_code == 204

    def register_wait(self, token, reregister=False):
        """
        Setup licensing registrations and wait for registration status
        to be COMPLETED and authorization status to be IN_COMPLIANCE.
        """
        res = self.register(token=token, reregister=reregister)
        self.wait_for_completed_registration()
        self.wait_for_completed_authorization()
        return res

    def deregister(self):
        """
        Request deregistration from the current SSMS.
        """
        url = self.base_url + "/deregistration"
        response = self.ctx.session.delete(url)
        response.raise_for_status()
        if response.status_code == 202:
            logger.warning(
                "Deregistration has been completed on the Product Instance but was "
                "unable to deregister from Smart Software Licensing due to a "
                "communication timeout."
            )
            # TODO try to register agsain and unregister
        if response.status_code == 204:
            logger.info(
                "The Product Instance was successfully deregistered from Smart "
                "Software Licensing."
            )
        return response.status_code

    def features(self):
        """
        Get current licensing features.
        """
        url = self.base_url + "/features"
        response = self.ctx.session.get(url)
        response.raise_for_status()
        return response.json()

    def update_features(self, feature_dict):
        """
        Update current licensing feature(s).
        """
        url = self.base_url + "/features"
        response = self.ctx.session.patch(url, json=feature_dict)
        response.raise_for_status()
        return response.json()

    def reservation_mode(self, data):
        """
        Enable or disable reservation mode in unregistered agent.
        """
        url = self.base_url + "/reservation/mode"
        response = self.ctx.session.put(url, json=data)
        response.raise_for_status()
        msg = "enabled" if data else "disabled"
        logger.info("The reservation mode has been %s.", msg)
        return response.json()

    def enable_reservation_mode(self):
        """
        Enable reservation mode in unregistered agent.
        """
        return self.reservation_mode(data=True)

    def disable_reservation_mode(self):
        """
        Disable reservation mode in unregistered agent.
        """
        return self.reservation_mode(data=False)

    def request_reservation(self):
        """
        Initiate reservation by generating request code and message to the user.
        """
        url = self.base_url + "/reservation/request"
        response = self.ctx.session.post(url)
        response.raise_for_status()
        logger.info("The reservation request code received.")
        return response.json()

    def complete_reservation(self, authorization_code):
        """
        Complete reservation by installing authorization code from CSSM.
        """
        # TODO
        url = self.base_url + "/reservation/complete"
        response = self.ctx.session.post(url, json=authorization_code)
        response.raise_for_status()
        logger.info("The confirmation code of completed reservation received.")
        return response.json()

    def cancel_reservation(self):
        """
        Cancel reservation request without completing it.
        """
        url = self.base_url + "/reservation/cancel"
        response = self.ctx.session.delete(url)
        response.raise_for_status()
        logger.info("The reservation request has been cancelled.")
        return response.status_code == 204

    def release_reservation(self):
        """
        Return a completed reservation.
        """
        # TODO
        url = self.base_url + "/reservation/release"
        response = self.ctx.session.delete(url)
        response.raise_for_status()
        logger.info("The return code of the released reservation received.")
        return response.json()

    def discard_reservation(self, data):
        """
        Discard a reservation authorization code for an already cancelled
        reservation request.
        """
        # TODO
        url = self.base_url + "/reservation/discard"
        response = self.ctx.session.delete(url, json=data)
        response.raise_for_status()
        logger.info(
            "The discard code for an already cancelled reservation request received."
        )
        return response.json()

    def get_reservation_confirmation_code(self):
        """
        Get the confirmation code.
        """
        url = self.base_url + "/reservation/confirmation_code"
        response = self.ctx.session.get(url)
        response.raise_for_status()
        logger.info("The confirmation code of the completed reservation received.")
        return response.json()

    def delete_reservation_confirmation_code(self):
        """
        Remove the confirmation code.
        """
        url = self.base_url + "/reservation/confirmation_code"
        response = self.ctx.session.delete(url)
        response.raise_for_status()
        logger.info("The confirmation code has been removed.")
        return response.status_code == 204

    def get_reservation_return_code(self):
        """
        Get the return code.
        """
        url = self.base_url + "/reservation/return_code"
        response = self.ctx.session.get(url)
        response.raise_for_status()
        logger.info("The return code of the released reservation received.")
        return response.json()

    def delete_reservation_return_code(self):
        """
        Remove the return code.
        """
        url = self.base_url + "/reservation/return_code"
        response = self.ctx.session.delete(url)
        response.raise_for_status()
        logger.info("The return code has been removed.")
        return response.status_code == 204

    def _wait_for_status(self, what, target_status):
        count = 0
        status = self.status()[what]["status"]
        while status != target_status:
            time.sleep(self.wait_interval)
            if count > self.max_wait:
                logger.error(
                    "%s timeout: status %s after %d sec of waiting",
                    what,
                    status,
                    self.max_wait * self.wait_interval,
                )
                break
            status = self.status()[what]["status"]
            logger.debug("%s status: %s", what, status)
            count += 1

    def wait_for_completed_registration(self):
        self._wait_for_status(what="registration", target_status="COMPLETED")

    def wait_for_completed_authorization(self):
        self._wait_for_status(what="authorization", target_status="IN_COMPLIANCE")
