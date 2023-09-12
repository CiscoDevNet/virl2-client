#
# This file is part of VIRL 2
# Copyright (c) 2019-2023, Cisco Systems, Inc.
# All rights reserved.
#
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

from pathlib import Path

import pytest


def pytest_addoption(
    parser: pytest.Parser, pluginmanager: pytest.PytestPluginManager
) -> None:
    # Only add these options if the test is run inside the root virl2 repository
    # itself and not from outside
    root_dir = parser.extra_info.get("rootdir", "")
    if not root_dir.endswith("virl2-client"):
        return

    # The pytest.ini file has the "asyncio_mode=auto" set... pytest-asyncio
    # defaults to "strict" these days. However, if the option is set but the
    # plugin is not installed this ini file option will cause a warning.  Adding
    # the parser option here when the module is *not* installed will suppress
    # the warning.
    # Note: The virl2_client package by itself does *not* depend on
    # pytest-asycnio
    if pluginmanager.get_plugin("asyncio") is None:
        parser.addini("asyncio_mode", "suppress the warning")


@pytest.fixture
def test_dir(request: pytest.FixtureRequest) -> Path:
    return request.path.parent
