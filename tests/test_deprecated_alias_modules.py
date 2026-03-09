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
"""Tests for deprecated alias modules and emitted warning categories."""

from __future__ import annotations

import importlib
import sys
import warnings

import pytest


@pytest.mark.parametrize(
    "module_name",
    [
        "virl2_client.models.groups",
        "virl2_client.models.users",
        "virl2_client.models.node_image_definitions",
        "virl2_client.models.resource_pools",
    ],
)
def test_deprecated_alias_warns(module_name: str) -> None:
    """Verify importing alias modules emits UserWarning (not DeprecationWarning).

    NOTE: LLM-generated test -- verify for correctness.

    :param module_name: Deprecated alias module path to import.
    """
    sys.modules.pop(module_name, None)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        importlib.import_module(module_name)
    assert caught, "Expected warning when importing deprecated alias module."
    assert all(issubclass(w.category, UserWarning) for w in caught)
    assert all(not issubclass(w.category, DeprecationWarning) for w in caught)
