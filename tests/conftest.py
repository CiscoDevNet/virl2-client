#
# This file is part of VIRL 2
# Copyright (c) 2019-2024, Cisco Systems, Inc.
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
from unittest.mock import patch

import httpx
import pytest

from virl2_client.virl2_client import ClientLibrary

CURRENT_VERSION = ClientLibrary.VERSION.version_str
FAKE_HOST = "https://0.0.0.0"
FAKE_HOST_API = f"{FAKE_HOST}/api/v0/"


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
def client_library_server_3_9_0():
    yield from client_library_patched_system_info(version="3.9.0")


@pytest.fixture
def client_library_server_3_19_0():
    yield from client_library_patched_system_info(version="3.19.0")


@pytest.fixture
def mocked_session():
    with patch.object(httpx, "Client", autospec=True) as session:
        yield session


def resp_body_from_file(request: httpx.Request) -> httpx.Response:
    """
    A callback that returns the contents of a file based on the request.

    :param request: The request that contains the title to search for
    :returns: A Response that has `content` set to the contents of a file
        that corresponds to a response body for the request.
    """
    endpoint_parts = request.url.path.split("/")[3:]
    filename = "not initialized"
    if len(endpoint_parts) == 1:
        filename = endpoint_parts[0] + ".json"
    elif endpoint_parts[0] == "labs":
        lab_id = endpoint_parts[1]
        filename = "_".join(endpoint_parts[2:]) + "-" + lab_id + ".json"
    test_dir = Path(__file__).parent.resolve()
    file_path = test_dir / "test_data" / filename
    return httpx.Response(200, text=file_path.read_text())


@pytest.fixture
def respx_mock_with_labs(respx_mock):
    """
    A test fixture that provides basic lab data with respx_mock so that unit tests can
    call ``client.all_labs`` or ``client.join_existing_lab``.  The sample data includes
    some runtime data, like node states and simulation_statistics.
    """
    respx_mock.get(FAKE_HOST_API + "system_information").respond(
        json={"version": CURRENT_VERSION, "ready": True},
    )
    respx_mock.post(FAKE_HOST_API + "authenticate").respond(json="BOGUS_TOKEN")
    respx_mock.get(FAKE_HOST_API + "authok")
    respx_mock.get(
        FAKE_HOST_API + "labs/444a78d1-575c-4746-8469-696e580f17b6/resource_pools"
    ).respond(json=[])
    respx_mock.get(FAKE_HOST_API + "resource_pools?data=true").respond(json=[])
    nodes = [
        "99cda47a-ecb2-4d31-86c4-74e7a8201958",
        "913e62a7-e096-4ed9-bb9f-03ae13106fc5",
        "0f9565f7-4fa3-4312-8dda-1db183a55950",
        "56c875d9-4f2a-4688-9fba-660716cff4cb",
        "aa51eca6-ae81-40fc-a713-e1a168280d21",
        "e5222bd8-52ff-4e1d-b6c9-89241132fb13",
        "004c00c9-2606-485c-8ff9-d698e430fa6a",
    ]
    for node in nodes:
        respx_mock.get(
            FAKE_HOST_API
            + f"labs/444a78d1-575c-4746-8469-696e580f17b6/nodes/{node}?operational=true"
            f"&exclude_configurations=true"
        ).respond(
            json={"operational": {"compute_id": "99c887f5-052e-4864-a583-49fa7c4b68a9"}}
        )
    respx_mock.get(
        FAKE_HOST_API
        + "labs/444a78d1-575c-4746-8469-696e580f17b6/nodes?data=true&operational=true&"
        "exclude_configurations=true"
    ).respond(
        json=[
            {
                "id": node,
                "operational": {"compute_id": "99c887f5-052e-4864-a583-49fa7c4b68a9"},
            }
            for node in nodes
        ]
    )
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
        respx_mock.get(FAKE_HOST_API + api).mock(side_effect=resp_body_from_file)


@pytest.fixture
def client_library(respx_mock_with_labs):
    client = ClientLibrary(url=FAKE_HOST, username="test", password="pa$$")
    yield client
