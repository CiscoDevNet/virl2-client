#
# This file is part of VIRL 2
# Copyright (c) 2019-2025, Cisco Systems, Inc.
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

from .annotation import Annotation
from .auth_management import AuthManagement
from .authentication import TokenAuth
from .group import GroupManagement
from .interface import Interface
from .lab import Lab
from .licensing import Licensing
from .link import Link
from .node import Node
from .node_image_definition import NodeImageDefinitions
from .resource_pool import ResourcePoolManagement
from .smart_annotation import SmartAnnotation
from .system import SystemManagement
from .user import UserManagement

__all__ = (
    "Interface",
    "Lab",
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
