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

from virl2_client import ClientLibrary


@pytest.mark.integration
def test_start_stop_start_stop_cycle(client_library: ClientLibrary):
    """we need to test if the entire lifecycle works... e.g.
    - define
    - start
    - queued
    - booted
    - stopped
    - queued
    - start
    - stopped
    - ...
    """
    lab = client_library.import_sample_lab("server-triangle.yaml")

    lab.start()
    lab.stop()
    lab.start()
    lab.stop()
    lab.wipe()
