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
"""Tests for node and image definition upload validation."""

from typing import Any

import pytest

from virl2_client.exceptions import InvalidContentType
from virl2_client.virl2_client import ClientLibrary

# everything except str or dict is invalid
INVALID_DEFINITIONS: dict[str, Any] = {
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
def invalid_definition(request: pytest.FixtureRequest) -> Any:
    """Provide an invalid definition value for parametrized tests.

    :param request: Pytest fixture request; param selects the invalid type.
    :returns: An invalid value (not str or dict) for definition upload.
    """
    return INVALID_DEFINITIONS[request.param]


@pytest.mark.parametrize(
    "upload_method",
    ["upload_node_definition", "upload_image_definition"],
)
def test_upload_definition_invalid_body(
    client_library: ClientLibrary, invalid_definition: Any, upload_method: str
) -> None:
    """Upload rejects non-str/dict definition bodies with InvalidContentType.

    NOTE: LLM-generated test -- verify for correctness.

    :param client_library: Client library fixture.
    :param invalid_definition: Invalid definition value (parametrized).
    :param upload_method: Upload method name to call.
    """
    with pytest.raises(InvalidContentType):
        getattr(client_library.definitions, upload_method)(invalid_definition)
