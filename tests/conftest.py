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

from pathlib import Path
import pytest
import requests

from unittest.mock import patch
from virl2_client.virl2_client import ClientLibrary

CURRENT_VERSION = ClientLibrary.VERSION.version_str

FAKE_HOST_API = "https://0.0.0.0/api/v0/"


def client_library_patched_system_info(version):
    with patch.object(
        ClientLibrary, "system_info", return_value={"version": version, "ready": True}
    ) as cl:
        yield cl


@pytest.fixture
def client_library_server_current():
    yield from client_library_patched_system_info(version=CURRENT_VERSION)


@pytest.fixture
def client_library_server_2_0_0():
    yield from client_library_patched_system_info(version="2.0.0")


@pytest.fixture
def client_library_server_1_0_0():
    yield from client_library_patched_system_info(version="1.0.0")


@pytest.fixture
def client_library_server_2_9_0():
    yield from client_library_patched_system_info(version="2.9.0")


@pytest.fixture
def client_library_server_2_19_0():
    yield from client_library_patched_system_info(version="2.19.0")


@pytest.fixture
def mocked_session():
    with patch.object(requests, "Session", autospec=True) as session:
        yield session


def resp_body_from_file(req, context):
    """
    A callback that returns the contents of a file based on the request.

    :param req: The title to search for
    :type req: An HTTP request (or proxy) object
    :param context: unused but required context parameter
    :type context: An HTTP response object
    :returns: A string, the contents of a file that corresponds to a response body for the request.
    :rtype: string
    """
    endpoint_parts = req.path.split("/")[3:]
    filename = "not initialized"
    if len(endpoint_parts) == 1:
        filename = endpoint_parts[0] + ".json"
    elif endpoint_parts[0] == "labs":
        lab_id = endpoint_parts[1]
        filename = "_".join(endpoint_parts[2:]) + "-" + lab_id + ".json"
    file_path = Path("test_data", filename)
    return file_path.read_text()


@pytest.fixture
def requests_mock_with_labs(requests_mock):
    """
    A test fixture that provides basic lab data with requests-mock so that unit tests can
    call ``client.all_labs`` or ``client.join_existing_lab``.  The sample data includes
    some runtime data, like node states and simulation_statistics.
    """
    requests_mock.get(
        FAKE_HOST_API + "system_information",
        json={"version": CURRENT_VERSION, "ready": True},
    )
    requests_mock.post(FAKE_HOST_API + "authenticate", json="BOGUS_TOKEN")
    requests_mock.get(FAKE_HOST_API + "authok", text=None)
    resp_from_files = (
        "labs",
        "populate_lab_tiles",
        "labs/444a78d1-575c-4746-8469-696e580f17b6/topology",
        "labs/444a78d1-575c-4746-8469-696e580f17b6/simulation_stats",
        "labs/444a78d1-575c-4746-8469-696e580f17b6/layer3_addresses",
        "labs/df76a038-076f-4744-85c0-b2e1daf1bc06/topology",
        "labs/df76a038-076f-4744-85c0-b2e1daf1bc06/simulation_stats",
        "labs/df76a038-076f-4744-85c0-b2e1daf1bc06/layer3_addresses",
        "labs/3031b614-0e76-4450-9fe0-6b3be0bc0bd2/topology",
        "labs/3031b614-0e76-4450-9fe0-6b3be0bc0bd2/simulation_stats",
        "labs/3031b614-0e76-4450-9fe0-6b3be0bc0bd2/layer3_addresses",
        "labs/863799a0-3d09-4af4-be26-cad997b6ab27/topology",
        "labs/863799a0-3d09-4af4-be26-cad997b6ab27/simulation_stats",
        "labs/863799a0-3d09-4af4-be26-cad997b6ab27/layer3_addresses",
    )
    for api in resp_from_files:
        requests_mock.get(FAKE_HOST_API + api, text=resp_body_from_file)
