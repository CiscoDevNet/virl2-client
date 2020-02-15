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


@pytest.mark.integration
def test_sending_requests_without_auth_token(controller_url: str):
    client_library = ClientLibrary(controller_url,
                                   username="virl2",
                                   password="virl2",
                                   ssl_verify=False,
                                   allow_http=True)

    # it probably won't be a common case to override `auth` by ClientLibrary users
    # but missing auth token may happen when using API directly via HTTP:
    client_library.session.auth = None
    with pytest.raises(requests.exceptions.HTTPError) as exc:
        client_library.create_lab()
    exc.match('401 Client Error: Unauthorized for url')
