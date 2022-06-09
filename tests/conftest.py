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

import pytest
import requests

from unittest.mock import patch
from virl2_client.virl2_client import ClientLibrary

CURRENT_VERSION = ClientLibrary.VERSION.version_str


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
