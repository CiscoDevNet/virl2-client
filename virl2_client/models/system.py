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


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class SystemManagement(object):
    def __init__(self, context):
        self.ctx = context

    @property
    def base_url(self):
        return self.ctx.base_url

    def get_web_session_timeout(self):
        """
        Get the web session timeout in seconds.

        :return: web session timeout
        :rtype:  int
        """
        url = self.base_url + "/web_session_timeout"
        response = self.ctx.session.get(url)
        response.raise_for_status()
        return response.json()

    def set_web_session_timeout(self, timeout):
        """
        Set the web session timeout in seconds.

        :return: 'OK'
        :rtype: str
        """

        url = self.ctx.base_url + "/web_session_timeout/{}".format(timeout)
        response = self.ctx.session.patch(url)
        response.raise_for_status()
        return response.json()

    def get_mac_address_block(self):
        """
        Get mac address block.

        :return: mac address block
        :rtype:  int
        """
        url = self.base_url + "/mac_address_block"
        response = self.ctx.session.get(url)
        response.raise_for_status()
        return response.json()

    def _set_mac_address_block(self, block):
        url = self.ctx.base_url + "/mac_address_block/{}".format(block)
        response = self.ctx.session.patch(url)
        response.raise_for_status()
        return response.json()

    def set_mac_address_block(self, block):
        """
        Set mac address block.

        :return: 'OK'
        :rtype: str
        """
        if block < 0 or block > 7:
            raise ValueError("MAC address block has to be in range 0-7.")
        return self._set_mac_address_block(block=block)
