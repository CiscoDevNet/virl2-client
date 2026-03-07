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
"""This package contains the VIRL2 client library models for
labs, nodes, interfaces and links. It also contains classes for
node and image definition and helper classes for automation
and authentication."""

from virl2_client.models.annotation import Annotation
from virl2_client.models.auth_management import AuthManagement
from virl2_client.models.authentication import TokenAuth
from virl2_client.models.group import GroupManagement
from virl2_client.models.interface import Interface
from virl2_client.models.lab import Lab
from virl2_client.models.lab_repository import LabRepository, LabRepositoryManagement
from virl2_client.models.licensing import Licensing
from virl2_client.models.link import Link
from virl2_client.models.node import Node
from virl2_client.models.node_image_definition import NodeImageDefinitions
from virl2_client.models.resource_pool import ResourcePoolManagement
from virl2_client.models.smart_annotation import SmartAnnotation
from virl2_client.models.system import SystemManagement
from virl2_client.models.user import UserManagement

__all__ = (
    "Interface",
    "Lab",
    "LabRepository",
    "LabRepositoryManagement",
    "Link",
    "Node",
    "NodeImageDefinitions",
    "Licensing",
    "SystemManagement",
    "UserManagement",
    "GroupManagement",
    "TokenAuth",
    "ResourcePoolManagement",
    "AuthManagement",
    "Annotation",
    "SmartAnnotation",
)
