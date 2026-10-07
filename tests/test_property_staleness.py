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

import inspect

import pytest

from virl2_client.exceptions import LabNotFound
from virl2_client.models.lab import Lab
from virl2_client.utils import property_s


def test_class_property_access():
    assert isinstance(Lab.id, property_s)
    assert dict(inspect.getmembers(Lab))["id"] is Lab.id


def test_inherited_property_access():
    class CustomLab(Lab):
        pass

    assert CustomLab.id is Lab.id


def test_instance_property_staleness():
    lab = Lab.__new__(Lab)
    lab._id = "123abc"
    lab._stale = False
    assert lab.id == "123abc"
    lab._stale = True
    with pytest.raises(LabNotFound):
        _ = lab.id
