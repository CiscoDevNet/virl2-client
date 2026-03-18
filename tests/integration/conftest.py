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

"""Fixtures for integration tests against a live CML server.

Environment variables:
    CML_HOST  (required): Server URL, e.g. https://10.0.0.1
    CML_PASS  (required): Password
    CML_USER  (optional): Username, defaults to "admin"
    CML_VERIFY (optional): SSL verification, defaults to "false"

Usage:
    CML_HOST=https://cml.local CML_PASS=secret pytest -m integration
"""

from __future__ import annotations

import logging
import os
import uuid

import pytest

from virl2_client import ClientLibrary

_LOGGER = logging.getLogger(__name__)

_SKIP_REASON = "CML_HOST environment variable not set; skipping integration tests"


def pytest_collection_modifyitems(config, items):
    """Skip integration tests when CML_HOST is not set."""
    if os.environ.get("CML_HOST"):
        return
    skip_marker = pytest.mark.skip(reason=_SKIP_REASON)
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_marker)


@pytest.fixture(scope="session")
def cml_client():
    """Session-scoped ClientLibrary connected to a real CML server.

    Authenticated once, reused across all integration tests.
    Logs out on teardown.
    """
    host = os.environ["CML_HOST"]
    user = os.environ.get("CML_USER", "admin")
    password = os.environ["CML_PASS"]
    ssl_verify = os.environ.get("CML_VERIFY", "false").lower() != "false"

    _LOGGER.info(f"Connecting to CML server at {host} as {user}")
    client = ClientLibrary(
        url=host,
        username=user,
        password=password,
        ssl_verify=ssl_verify,
        raise_for_auth_failure=True,
    )
    _LOGGER.info(f"Connected; server version: {client.system_info().get('version')}")
    yield client
    client.logout()
    _LOGGER.info("Logged out from CML server")


@pytest.fixture(scope="session")
def server_version(cml_client):
    """Return the server version string, e.g. '2.8.0'."""
    return cml_client.system_info()["version"]


@pytest.fixture
def temp_lab(cml_client):
    """Create a temporary lab for a single test, clean up afterwards.

    The lab is stopped, wiped, and removed on teardown regardless of
    test outcome.
    """
    unique_title = f"integ-test-{uuid.uuid4().hex[:8]}"
    _LOGGER.info(f"Creating temporary lab: {unique_title}")
    lab = cml_client.create_lab(title=unique_title)
    yield lab
    _LOGGER.info(f"Cleaning up lab: {unique_title} ({lab.id})")
    try:
        lab.stop(wait=True)
    except Exception:
        _LOGGER.debug("Lab stop failed (may already be stopped)", exc_info=True)
    try:
        lab.wipe(wait=True)
    except Exception:
        _LOGGER.debug("Lab wipe failed (may already be wiped)", exc_info=True)
    try:
        lab.remove()
    except Exception:
        _LOGGER.warning(f"Failed to remove lab {lab.id}", exc_info=True)


@pytest.fixture
def two_alpine_nodes(temp_lab):
    """Create two alpine nodes in a temporary lab, return (lab, node1, node2)."""
    n1 = temp_lab.create_node("alpine-1", "alpine", populate_interfaces=True)
    n2 = temp_lab.create_node("alpine-2", "alpine", populate_interfaces=True)
    return temp_lab, n1, n2
