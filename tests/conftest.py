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

import sys
from collections.abc import Iterator
from functools import partial
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest
from respx import MockRouter

from virl2_client.models import authentication
from virl2_client.virl2_client import ClientLibrary

# Patch sys.stdin.isatty to simulate an interactive terminal
sys.stdin.isatty = lambda: True

CURRENT_VERSION = ClientLibrary.VERSION.version_str
FAKE_HOST = "https://0.0.0.0"
FAKE_HOST_API = f"{FAKE_HOST}/api/v0/"


def client_library_patched_system_info(version: str) -> Iterator[MagicMock]:
    """Patch ClientLibrary.system_info to return a fixed version.

    :param version: Version string to return from system_info.
    :yields: The patch object for ClientLibrary.system_info.
    """
    with patch.object(
        ClientLibrary, "system_info", return_value={"version": version, "ready": True}
    ) as cl:
        yield cl


@pytest.fixture
def client_library_server_current() -> Iterator[MagicMock]:
    """Simulate a controller running the current CML version.

    :yields: The patch object for ClientLibrary.system_info.
    """
    yield from client_library_patched_system_info(version=CURRENT_VERSION)


@pytest.fixture
def client_library_server_2_0_0() -> Iterator[MagicMock]:
    """Simulate a controller running CML version 2.0.0.

    :yields: The patch object for ClientLibrary.system_info.
    """
    yield from client_library_patched_system_info(version="2.0.0")


@pytest.fixture
def client_library_server_2_19_0() -> Iterator[MagicMock]:
    """Simulate a controller running CML version 2.19.0.

    :yields: The patch object for ClientLibrary.system_info.
    """
    yield from client_library_patched_system_info(version="2.19.0")


@pytest.fixture
def client_library_server_2_9_0() -> Iterator[MagicMock]:
    """Simulate a controller running CML version 2.9.0.

    :yields: The patch object for ClientLibrary.system_info.
    """
    yield from client_library_patched_system_info(version="2.9.0")


@pytest.fixture
def mocked_session() -> Iterator[MagicMock]:
    """Patch authentication.CustomClient for tests that need a mock HTTP session.

    :yields: The patched CustomClient class (MagicMock).
    """
    with patch.object(authentication, "CustomClient", autospec=True) as session:
        yield session


@pytest.fixture(scope="session")
def test_data_dir() -> Path:
    """Path to the test_data directory containing JSON fixtures.

    :returns: Path to the test_data directory.
    """
    return Path(__file__).parent / "test_data"


def resp_body_from_file(test_data_dir: Path, request: httpx.Request) -> httpx.Response:
    """Return response body from a file based on the request URL path.

    :param test_data_dir: Directory containing JSON fixture files.
    :param request: The HTTP request; URL path determines which file to load.
    :returns: An httpx.Response with content set to the matching fixture file.
    """
    endpoint_parts = request.url.path.split("/")[3:]
    filename = "not initialized"
    if len(endpoint_parts) == 1:
        filename = endpoint_parts[0] + ".json"
    elif endpoint_parts[0] == "labs":
        lab_id = endpoint_parts[1]
        filename = "_".join(endpoint_parts[2:]) + "-" + lab_id + ".json"
    file_path = test_data_dir / filename
    return httpx.Response(200, text=file_path.read_text())


@pytest.fixture
def respx_mock_with_labs(respx_mock: MockRouter, test_data_dir: Path) -> None:
    """Provide basic lab data with respx_mock for unit tests.

    Enables tests to call ``client.all_labs`` or ``client.join_existing_lab``.
    Sample data includes runtime data (node states, simulation_statistics).

    :param respx_mock: The respx mock router to configure.
    :param test_data_dir: Directory containing JSON fixture files.
    """
    respx_mock.get(FAKE_HOST_API + "system_information").respond(
        json={"version": CURRENT_VERSION, "ready": True, "oui": "52:54:00:00:00:00"},
    )
    respx_mock.post(FAKE_HOST_API + "authenticate").respond(json="BOGUS_TOKEN")
    respx_mock.get(FAKE_HOST_API + "authentication").respond(
        json={
            "username": "username",
            "id": "6c7dd461-1cbe-428f-bdd5-545a0d766ed7",
            "token": "BOGUS_TOKEN",
            "admin": True,
            "error": None,
        }
    )
    respx_mock.get(
        FAKE_HOST_API + "labs/444a78d1-575c-4746-8469-696e580f17b6/resource_pools"
    ).respond(json=[])
    respx_mock.get(FAKE_HOST_API + "users").respond(json=[])
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
            + f"labs/444a78d1-575c-4746-8469-696e580f17b6/nodes/{node}/interfaces"
            + "?data=true&operational=true"
        ).respond(json=[])

    respx_mock.get(
        FAKE_HOST_API + "labs/444a78d1-575c-4746-8469-696e580f17b6/interfaces"
    ).respond(json=[])

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
    side_effect = partial(resp_body_from_file, test_data_dir)
    for api in resp_from_files:
        respx_mock.get(FAKE_HOST_API + api).mock(side_effect=side_effect)


@pytest.fixture
def client_library(respx_mock_with_labs: None) -> Iterator[ClientLibrary]:
    """Provide a ClientLibrary instance with mocked lab API responses.

    :param respx_mock_with_labs: Fixture that configures respx (consumed for setup).
    :yields: A ClientLibrary connected to FAKE_HOST with test credentials.
    """
    _ = respx_mock_with_labs
    client = ClientLibrary(url=FAKE_HOST, username="test", password="pa$$")
    yield client
