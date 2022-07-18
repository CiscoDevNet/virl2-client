#
# Python bindings for the Cisco VIRL 2 Network Simulation Platform
#
# This file is part of VIRL 2
#
# Copyright 2020-2022 Cisco Systems Inc.
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

import os
import pytest


def pytest_addoption(parser, pluginmanager):
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


@pytest.fixture(scope="function")
def change_test_dir(request):
    os.chdir(request.fspath.dirname)
    yield
    os.chdir(request.config.invocation_dir)
