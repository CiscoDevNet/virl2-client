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

"""Public API contract tests.

These tests verify that the client library's public API surface remains
backward-compatible. They run without a live server and catch accidental
removals of classes, methods, or changes to method signatures that would
break user code written against v2.8 or v2.9.
"""

from __future__ import annotations

import inspect

import pytest

# ---------------------------------------------------------------------------
# Top-level package exports
# ---------------------------------------------------------------------------

TOP_LEVEL_EXPORTS = [
    "ClientConfig",
    "ClientLibrary",
    "InitializationError",
    "InterfaceNotFound",
    "LabNotFound",
    "LinkNotFound",
    "NodeNotFound",
]


@pytest.mark.parametrize("name", TOP_LEVEL_EXPORTS)
def test_top_level_exports(name):
    """All expected names are importable from virl2_client."""
    import virl2_client

    assert hasattr(virl2_client, name), f"virl2_client.{name} missing"


def test_top_level_all_matches():
    """__all__ contains at least the expected exports."""
    import virl2_client

    for name in TOP_LEVEL_EXPORTS:
        assert name in virl2_client.__all__


# ---------------------------------------------------------------------------
# Models sub-package exports
# ---------------------------------------------------------------------------

MODEL_EXPORTS = [
    "Annotation",
    "AuthManagement",
    "GroupManagement",
    "Interface",
    "Lab",
    "LabRepository",
    "LabRepositoryManagement",
    "Licensing",
    "Link",
    "Node",
    "NodeImageDefinitions",
    "ResourcePoolManagement",
    "SmartAnnotation",
    "SystemManagement",
    "TokenAuth",
    "UserManagement",
]


@pytest.mark.parametrize("name", MODEL_EXPORTS)
def test_model_exports(name):
    """All expected model classes are importable from virl2_client.models."""
    from virl2_client import models

    assert hasattr(models, name), f"virl2_client.models.{name} missing"


def test_model_all_matches():
    """models.__all__ contains at least the expected exports."""
    from virl2_client import models

    for name in MODEL_EXPORTS:
        assert name in models.__all__


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


def test_exception_hierarchy_element_not_found():
    """ElementNotFound is a subclass of both VirlException and KeyError."""
    from virl2_client.exceptions import ElementNotFound, VirlException

    assert issubclass(ElementNotFound, VirlException)
    assert issubclass(ElementNotFound, KeyError)


def test_exception_hierarchy_specific_not_found():
    """Each model-specific NotFound inherits from ElementNotFound."""
    from virl2_client.exceptions import (
        AnnotationNotFound,
        ElementNotFound,
        InterfaceNotFound,
        LabNotFound,
        LinkNotFound,
        NodeNotFound,
        SmartAnnotationNotFound,
    )

    for exc_cls in (
        LabNotFound,
        NodeNotFound,
        InterfaceNotFound,
        LinkNotFound,
        AnnotationNotFound,
        SmartAnnotationNotFound,
    ):
        assert issubclass(exc_cls, ElementNotFound), f"{exc_cls.__name__} hierarchy"


def test_exception_hierarchy_element_already_exists():
    """ElementAlreadyExists is a subclass of both VirlException and FileExistsError."""
    from virl2_client.exceptions import ElementAlreadyExists, VirlException

    assert issubclass(ElementAlreadyExists, VirlException)
    assert issubclass(ElementAlreadyExists, FileExistsError)


def test_exception_hierarchy_api_error():
    """APIError inherits from both VirlException and httpx.HTTPStatusError."""
    import httpx

    from virl2_client.exceptions import APIError, VirlException

    assert issubclass(APIError, VirlException)
    assert issubclass(APIError, httpx.HTTPStatusError)


def test_exception_hierarchy_feature_not_supported():
    """FeatureNotSupported inherits from VirlException."""
    from virl2_client.exceptions import FeatureNotSupported, VirlException

    assert issubclass(FeatureNotSupported, VirlException)


# ---------------------------------------------------------------------------
# Method signature stability
#
# These tests verify that key methods retain their expected parameters.
# New parameters may be added, but existing ones must not be removed.
# ---------------------------------------------------------------------------

# Format: ("module_path", "class.method", [required_params])
# "self" is included to verify it's a regular method (not static/class).
EXPECTED_SIGNATURES = [
    (
        "virl2_client.virl2_client",
        "ClientLibrary.__init__",
        ["self", "url", "username", "password", "ssl_verify"],
    ),
    (
        "virl2_client.virl2_client",
        "ClientLibrary.is_system_ready",
        ["self", "wait"],
    ),
    (
        "virl2_client.virl2_client",
        "ClientLibrary.import_lab",
        ["self", "topology", "title"],
    ),
    (
        "virl2_client.virl2_client",
        "ClientLibrary.all_labs",
        ["self", "show_all"],
    ),
    (
        "virl2_client.virl2_client",
        "ClientLibrary.find_labs_by_title",
        ["self", "title"],
    ),
    (
        "virl2_client.virl2_client",
        "ClientLibrary.create_lab",
        ["self", "title"],
    ),
    (
        "virl2_client.virl2_client",
        "ClientLibrary.join_existing_lab",
        ["self", "lab_id"],
    ),
    (
        "virl2_client.virl2_client",
        "ClientLibrary.get_diagnostics",
        ["self"],
    ),
    (
        "virl2_client.models.lab",
        "Lab.start",
        ["self", "wait"],
    ),
    (
        "virl2_client.models.lab",
        "Lab.stop",
        ["self", "wait"],
    ),
    (
        "virl2_client.models.lab",
        "Lab.wipe",
        ["self", "wait"],
    ),
    (
        "virl2_client.models.lab",
        "Lab.remove",
        ["self"],
    ),
    (
        "virl2_client.models.lab",
        "Lab.create_node",
        ["self", "label", "node_definition"],
    ),
    (
        "virl2_client.models.lab",
        "Lab.connect_two_nodes",
        ["self", "node1", "node2"],
    ),
    (
        "virl2_client.models.lab",
        "Lab.create_link",
        ["self", "i1", "i2"],
    ),
    (
        "virl2_client.models.lab",
        "Lab.sync",
        ["self", "topology_only"],
    ),
    (
        "virl2_client.models.lab",
        "Lab.download",
        ["self"],
    ),
    (
        "virl2_client.models.node",
        "Node.start",
        ["self", "wait"],
    ),
    (
        "virl2_client.models.node",
        "Node.stop",
        ["self", "wait"],
    ),
    (
        "virl2_client.models.node",
        "Node.create_interface",
        ["self"],
    ),
    (
        "virl2_client.models.node",
        "Node.add_tag",
        ["self", "tag"],
    ),
    (
        "virl2_client.models.node",
        "Node.remove_tag",
        ["self", "tag"],
    ),
    (
        "virl2_client.models.node",
        "Node.clone_image",
        ["self"],
    ),
    (
        "virl2_client.models.system",
        "SystemManagement.sync_compute_hosts",
        ["self"],
    ),
    (
        "virl2_client.models.system",
        "SystemManagement.sync_system_notices",
        ["self"],
    ),
    (
        "virl2_client.models.auth_management",
        "AuthManagement.sync_if_outdated",
        ["self"],
    ),
    (
        "virl2_client.models.lab_repository",
        "LabRepositoryManagement.sync_lab_repositories",
        ["self"],
    ),
    (
        "virl2_client.models.lab_repository",
        "LabRepositoryManagement.add_lab_repository",
        ["self", "url", "name", "folder"],
    ),
]


def _resolve_method(module_path, class_method):
    """Import and resolve a 'Class.method' string to the actual callable."""
    import importlib

    cls_name, method_name = class_method.split(".")
    mod = importlib.import_module(module_path)
    cls = getattr(mod, cls_name)
    return getattr(cls, method_name)


@pytest.mark.parametrize(
    "module_path,class_method,required_params",
    EXPECTED_SIGNATURES,
    ids=[f"{m}.{cm}" for m, cm, _ in EXPECTED_SIGNATURES],
)
def test_method_signatures(module_path, class_method, required_params):
    """Critical method signatures retain their expected parameters."""
    method = _resolve_method(module_path, class_method)
    func = method
    if isinstance(method, property):
        func = method.fget
    while hasattr(func, "__wrapped__"):
        func = func.__wrapped__
    sig = inspect.signature(func)
    actual_params = list(sig.parameters.keys())
    for param in required_params:
        assert param in actual_params, (
            f"{module_path}.{class_method} missing parameter '{param}'; "
            f"actual params: {actual_params}"
        )


# ---------------------------------------------------------------------------
# URL template stability
#
# The client's _URL_TEMPLATES dict defines the REST endpoints it depends on.
# Removing a key would silently break any code path that calls _url_for()
# with that endpoint name.
# ---------------------------------------------------------------------------

CLIENT_LIBRARY_URL_TEMPLATES = [
    "auth",
    "old_auth",
    "system_info",
    "import",
    "import_1x",
    "sample_labs",
    "labs",
    "lab",
    "lab_topology",
    "diagnostics",
    "system_health",
    "system_stats",
    "populate_lab_tiles",
]

LAB_URL_TEMPLATES = [
    "lab",
    "nodes",
    "links",
    "interfaces",
    "start",
    "stop",
    "state",
    "wipe",
    "events",
    "topology",
    "download",
    "associations",
    "connector_mappings",
    "resource_pools",
    "annotations",
]

NODE_URL_TEMPLATES = [
    "node",
    "state",
    "start",
    "stop",
    "wipe_disks",
    "clone_image",
    "extract_configuration",
    "console_log",
    "console_key",
    "vnc_key",
    "layer3_addresses",
]


@pytest.mark.parametrize("key", CLIENT_LIBRARY_URL_TEMPLATES)
def test_client_library_url_templates(key):
    """ClientLibrary._URL_TEMPLATES contains all expected keys."""
    from virl2_client.virl2_client import ClientLibrary

    assert key in ClientLibrary._URL_TEMPLATES


@pytest.mark.parametrize("key", LAB_URL_TEMPLATES)
def test_lab_url_templates(key):
    """Lab._URL_TEMPLATES contains all expected keys."""
    from virl2_client.models.lab import Lab

    assert key in Lab._URL_TEMPLATES


@pytest.mark.parametrize("key", NODE_URL_TEMPLATES)
def test_node_url_templates(key):
    """Node._URL_TEMPLATES contains all expected keys."""
    from virl2_client.models.node import Node

    assert key in Node._URL_TEMPLATES


# ---------------------------------------------------------------------------
# New in 2.10: Version importable from utils
# ---------------------------------------------------------------------------


def test_version_importable_from_utils():
    """Version class is importable from virl2_client.utils."""
    from virl2_client.utils import Version

    v = Version("2.10.0")
    assert v.major == 2 and v.minor == 10 and v.patch == 0
