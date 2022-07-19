#
# This file is part of VIRL 2
# Copyright (c) 2019-2022, Cisco Systems, Inc.
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


class VirlException(Exception):
    pass


class InitializationError(VirlException):
    pass


class ElementAlreadyExists(VirlException, FileExistsError):
    pass


class ElementNotFound(VirlException, KeyError):
    pass


class NodeNotFound(ElementNotFound):
    pass


class LinkNotFound(ElementNotFound):
    pass


class InterfaceNotFound(ElementNotFound):
    pass


class LabNotFound(ElementNotFound):
    pass


class DesynchronizedError(VirlException):
    pass
