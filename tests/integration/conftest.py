#
# This file is part of CML 2
#
# Copyright 2021 Cisco Systems Inc.
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

"""Integration tests require access to a live CML2 instance."""

import pytest

from virl2_client import ClientLibrary


@pytest.fixture
def cleanup_test_labs(client_library_session: ClientLibrary):
    """Remove all labs created during the test.
    Keep labs that existed previously."""

    lab_list_original = client_library_session.get_lab_list()
    yield
    lab_list = client_library_session.get_lab_list()
    for lab_id in lab_list:
        if lab_id not in lab_list_original:
            lab = client_library_session.join_existing_lab(lab_id)
            lab.stop()
            lab.wipe()
            client_library_session.remove_lab(lab_id)
