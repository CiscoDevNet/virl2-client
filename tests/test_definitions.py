#
# This file is part of VIRL 2
# Copyright (c) 2019-2023, Cisco Systems, Inc.
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

from virl2_client.exceptions import InvalidContentType
from virl2_client.virl2_client import ClientLibrary

# everything except str or dict is invalid
INVALID_DEFINITIONS = {
    "none": None,
    "bool": True,
    "int": 22,
    "float": 1.0,
    "complex": 1 + 2j,
    "list": ["test"],
    "tuple": ("test",),
    "range": range(2),
    "set": {"test"},
    "bytes": b"test",
    "bytearray": bytearray(2),
    "object": object(),
}


@pytest.fixture(params=list(INVALID_DEFINITIONS))
def invalid_definition(request):
    return INVALID_DEFINITIONS[request.param]


def test_upload_node_definition_invalid_body(
    client_library: ClientLibrary, invalid_definition
):
    """Try adding an invalid Node Definition"""
    with pytest.raises(InvalidContentType):
        client_library.definitions.upload_node_definition(invalid_definition)


def test_upload_image_definition_invalid_body(
    client_library: ClientLibrary, invalid_definition
):
    """Try adding an invalid Image Definition"""
    with pytest.raises(InvalidContentType):
        client_library.definitions.upload_image_definition(invalid_definition)
