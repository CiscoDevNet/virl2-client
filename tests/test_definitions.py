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

import requests

import pytest
import requests
from virl2_client.virl2_client import Context

from virl2_client.models import NodeImageDefinitions

def test_upload_image_files(requests_mock):
    adapter = requests_mock.post('mock://images/upload')
    session = requests.Session()
    context = Context("mock://", requests_session=session)
    definitions = NodeImageDefinitions(context)
    image_file_path = "tests/test_data/dummy.qcow2"
    definitions.upload_image_file(image_file_path)

    assert adapter.called
