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
"""Exception hierarchy for the virl2_client package."""

import httpx


class VirlException(Exception):
    """Base exception for all virl2_client errors."""


class InitializationError(VirlException):
    """Raised when the client library cannot be initialized."""


class ElementAlreadyExists(VirlException, FileExistsError):
    """Raised when attempting to create an element that already exists."""


class ElementNotFound(VirlException, KeyError):
    """Raised when a requested element does not exist."""


class AnnotationNotFound(ElementNotFound):
    """Raised when a requested annotation does not exist."""


class SmartAnnotationNotFound(ElementNotFound):
    """Raised when a requested smart annotation does not exist."""


class NodeNotFound(ElementNotFound):
    """Raised when a requested node does not exist."""


class LinkNotFound(ElementNotFound):
    """Raised when a requested link does not exist."""


class InterfaceNotFound(ElementNotFound):
    """Raised when a requested interface does not exist."""


class LabNotFound(ElementNotFound):
    """Raised when a requested lab does not exist."""


class LabRepositoryNotFound(ElementNotFound):
    """Raised when a requested lab repository does not exist."""


class InvalidContentType(VirlException):
    """Raised when an unsupported content type is encountered."""


class InvalidImageFile(VirlException):
    """Raised when an image file is invalid or has an unsupported format."""


class InvalidAnnotationType(VirlException):
    """Raised when an unsupported annotation type is used."""


class InvalidProperty(VirlException):
    """Raised when an invalid property is set on a model object."""


class InvalidTopologySchema(VirlException):
    """Raised when a topology definition does not match the expected schema."""


class MethodNotActive(VirlException):
    """Raised when a method is called that is not currently active or enabled."""


class PyatsException(VirlException):
    """Base exception for pyATS integration errors."""


class PyatsNotInstalled(PyatsException):
    """Raised when pyATS is required but not installed."""


class PyatsDeviceNotFound(PyatsException):
    """Raised when a requested pyATS device does not exist."""


class ControllerNotFound(VirlException):
    """Raised when no CML controller node is found in the topology."""

    def __init__(self) -> None:
        super().__init__("Controller not found")


class APIError(VirlException, httpx.HTTPStatusError):
    """Raised when the CML REST API returns an HTTP error response."""


class FeatureNotSupported(VirlException):
    pass
