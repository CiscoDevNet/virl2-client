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

"""Backward compatibility tests for virl2_client 2.10.

These tests verify that the v2.10 client works correctly against older
CML servers (2.8, 2.9) by mocking server responses with ``respx``.

Tests cover:
- Auth flow branching (authok vs authentication endpoint)
- Version guard enforcement for new-in-2.9+ features
- Graceful handling of 404s for endpoints missing on older servers
- Old response shape tolerance (ComputeHost with nodes list, etc.)
- Diagnostics endpoint compatibility
- Controller version property availability
"""

from __future__ import annotations

import httpx
import pytest
import respx

from virl2_client.exceptions import FeatureNotSupported
from virl2_client.models import Lab
from virl2_client.models.lab_repository import LabRepositoryManagement
from virl2_client.models.resource_pool import ResourcePoolManagement
from virl2_client.models.system import SystemManagement
from virl2_client.models.user import UserManagement
from virl2_client.virl2_client import ClientLibrary, Version

FAKE_HOST = "https://0.0.0.0"
FAKE_HOST_API = f"{FAKE_HOST}/api/v0/"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client(respx_mock, version: str) -> ClientLibrary:
    """Create a ClientLibrary connected to a fake server reporting *version*."""
    respx_mock.get(FAKE_HOST_API + "system_information").respond(
        json={"version": version, "ready": True},
    )
    respx_mock.post(FAKE_HOST_API + "authenticate").respond(json="BOGUS_TOKEN")
    if Version(version) >= Version("2.10.0"):
        respx_mock.get(FAKE_HOST_API + "authentication").respond(
            json={
                "username": "admin",
                "id": "00000000-0000-4000-a000-000000000000",
                "token": "BOGUS_TOKEN",
                "admin": True,
            }
        )
    else:
        respx_mock.get(FAKE_HOST_API + "authok").respond(text="OK")
    return ClientLibrary(
        url=FAKE_HOST,
        username="test",
        password="pa$$",
        check_version=False,
    )


def _make_lab(client: ClientLibrary, lab_id: str = "lab-id") -> Lab:
    """Create a Lab wired to *client* with mock dependencies."""
    rpm = ResourcePoolManagement(client._session, auto_sync=False)
    um = UserManagement(client._session, auto_sync=False)
    return Lab(
        "test",
        lab_id,
        client._session,
        "u",
        "p",
        auto_sync=False,
        resource_pool_manager=rpm,
        user_management=um,
    )


# ---------------------------------------------------------------------------
# Controller version property
# ---------------------------------------------------------------------------


class TestControllerVersionOnSession:
    """Verify that controller_version is stored on the session."""

    @respx.mock
    def test_version_stored_for_2_10(self):
        client = _make_client(respx.mock, "2.10.0")
        assert client._session.controller_version == Version("2.10.0")

    @respx.mock
    def test_version_stored_for_2_9(self):
        client = _make_client(respx.mock, "2.9.0")
        assert client._session.controller_version == Version("2.9.0")

    @respx.mock
    def test_version_stored_for_2_8(self):
        client = _make_client(respx.mock, "2.8.0")
        assert client._session.controller_version == Version("2.8.0")


# ---------------------------------------------------------------------------
# Auth flow branching
# ---------------------------------------------------------------------------


class TestAuthFlowBranching:
    """Verify that the correct auth endpoint is used based on server version."""

    @respx.mock
    def test_2_10_uses_authentication_endpoint(self):
        """CML 2.10 should GET /authentication and extract user info."""
        auth_route = respx.get(FAKE_HOST_API + "authentication").respond(
            json={
                "username": "admin",
                "id": "00000000-0000-4000-a000-000000000000",
                "token": "T",
                "admin": True,
            }
        )
        respx.get(FAKE_HOST_API + "system_information").respond(
            json={"version": "2.10.0", "ready": True},
        )
        respx.post(FAKE_HOST_API + "authenticate").respond(json="T")

        client = ClientLibrary(url=FAKE_HOST, username="test", password="pa$$")
        assert auth_route.called
        assert client.username == "admin"
        assert client.admin is True

    @respx.mock
    def test_2_9_uses_authok_endpoint(self):
        """CML 2.9 should GET /authok (legacy path)."""
        authok_route = respx.get(FAKE_HOST_API + "authok").respond(text="OK")
        respx.get(FAKE_HOST_API + "system_information").respond(
            json={"version": "2.9.0", "ready": True},
        )
        respx.post(FAKE_HOST_API + "authenticate").respond(json="T")

        ClientLibrary(url=FAKE_HOST, username="test", password="pa$$")
        assert authok_route.called

    @respx.mock
    def test_2_8_uses_authok_endpoint(self):
        """CML 2.8 should GET /authok (legacy path)."""
        authok_route = respx.get(FAKE_HOST_API + "authok").respond(text="OK")
        respx.get(FAKE_HOST_API + "system_information").respond(
            json={"version": "2.8.0", "ready": True},
        )
        respx.post(FAKE_HOST_API + "authenticate").respond(json="T")

        ClientLibrary(
            url=FAKE_HOST,
            username="test",
            password="pa$$",
            check_version=False,
        )
        assert authok_route.called

    @respx.mock
    def test_unparseable_version_raises(self):
        """If the controller returns a garbled version, raise InitializationError."""
        from virl2_client.virl2_client import InitializationError

        respx.get(FAKE_HOST_API + "system_information").respond(
            json={"version": "not-a-version", "ready": True},
        )
        respx.post(FAKE_HOST_API + "authenticate").respond(json="T")

        with pytest.raises(InitializationError, match="invalid version"):
            ClientLibrary(url=FAKE_HOST, username="test", password="pa$$")


# ---------------------------------------------------------------------------
# Version guard enforcement
# ---------------------------------------------------------------------------


class TestVersionGuardCloneImage:
    """Node.clone_image() requires CML >= 2.9."""

    @respx.mock
    def test_clone_image_blocked_on_2_8(self):
        """clone_image() raises FeatureNotSupported against a 2.8 server."""
        client = _make_client(respx.mock, "2.8.0")
        lab = _make_lab(client)
        from virl2_client.models.node import Node

        node = Node(lab, "n1", "mynode", "alpine")
        with pytest.raises(FeatureNotSupported, match="2.9.0"):
            node.clone_image()

    @respx.mock
    def test_clone_image_allowed_on_2_9(self):
        """clone_image() proceeds on a 2.9 server (HTTP call is made)."""
        client = _make_client(respx.mock, "2.9.0")
        lab = _make_lab(client)
        from virl2_client.models.node import Node

        node = Node(lab, "n1", "mynode", "alpine")
        respx.put(FAKE_HOST_API + "labs/lab-id/nodes/n1/clone_image").respond(
            json={"image_id": "new-image"}
        )
        result = node.clone_image()
        assert result == {"image_id": "new-image"}

    @respx.mock
    def test_clone_image_allowed_on_2_10(self):
        """clone_image() proceeds on a 2.10 server."""
        client = _make_client(respx.mock, "2.10.0")
        lab = _make_lab(client)
        from virl2_client.models.node import Node

        node = Node(lab, "n1", "mynode", "alpine")
        respx.put(FAKE_HOST_API + "labs/lab-id/nodes/n1/clone_image").respond(
            json={"image_id": "img-123"}
        )
        result = node.clone_image()
        assert result == {"image_id": "img-123"}


class TestVersionGuardLabRepositories:
    """LabRepositoryManagement methods require CML >= 2.9."""

    @respx.mock
    def test_sync_lab_repos_blocked_on_2_8(self):
        client = _make_client(respx.mock, "2.8.0")
        system = SystemManagement(client._session, auto_sync=False)
        mgmt = LabRepositoryManagement(system, client._session, auto_sync=False)
        with pytest.raises(FeatureNotSupported, match="2.9.0"):
            mgmt.sync_lab_repositories()

    @respx.mock
    def test_get_lab_repos_blocked_on_2_8(self):
        client = _make_client(respx.mock, "2.8.0")
        system = SystemManagement(client._session, auto_sync=False)
        mgmt = LabRepositoryManagement(system, client._session, auto_sync=False)
        with pytest.raises(FeatureNotSupported, match="2.9.0"):
            mgmt.get_lab_repositories()

    @respx.mock
    def test_add_lab_repo_blocked_on_2_8(self):
        client = _make_client(respx.mock, "2.8.0")
        system = SystemManagement(client._session, auto_sync=False)
        mgmt = LabRepositoryManagement(system, client._session, auto_sync=False)
        with pytest.raises(FeatureNotSupported, match="2.9.0"):
            mgmt.add_lab_repository("https://example.com/repo.git", "test", "folder")

    @respx.mock
    def test_refresh_lab_repos_blocked_on_2_8(self):
        client = _make_client(respx.mock, "2.8.0")
        system = SystemManagement(client._session, auto_sync=False)
        mgmt = LabRepositoryManagement(system, client._session, auto_sync=False)
        with pytest.raises(FeatureNotSupported, match="2.9.0"):
            mgmt.refresh_lab_repositories()

    @respx.mock
    def test_sync_lab_repos_allowed_on_2_9(self):
        client = _make_client(respx.mock, "2.9.0")
        system = SystemManagement(client._session, auto_sync=False)
        mgmt = LabRepositoryManagement(system, client._session, auto_sync=False)
        respx.get(FAKE_HOST_API + "lab_repos").respond(json=[])
        mgmt.sync_lab_repositories()


# ---------------------------------------------------------------------------
# ComputeHost response shape tolerance
# ---------------------------------------------------------------------------


class TestComputeHostResponseShapes:
    """sync_compute_hosts handles both old (with nodes list) and new (with
    node_counts) response shapes."""

    @respx.mock
    def test_v2_8_response_with_nodes_list(self):
        """v2.8 includes a 'nodes' list and no 'node_counts'."""
        client = _make_client(respx.mock, "2.8.0")
        system = SystemManagement(client._session, auto_sync=False)
        respx.get(FAKE_HOST_API + "system/compute_hosts").respond(
            json=[
                {
                    "id": "compute-1",
                    "hostname": "host1",
                    "server_address": "10.0.0.1",
                    "is_connector": False,
                    "is_simulator": True,
                    "is_connected": True,
                    "is_synced": True,
                    "admission_state": "ADMITTED",
                    "nodes": ["node-a", "node-b"],
                }
            ]
        )
        system.sync_compute_hosts()
        assert "compute-1" in system._compute_hosts
        host = system._compute_hosts["compute-1"]
        assert host._node_counts == {}

    @respx.mock
    def test_v2_10_response_with_node_counts(self):
        """v2.10 includes 'node_counts' and no 'nodes'."""
        client = _make_client(respx.mock, "2.10.0")
        system = SystemManagement(client._session, auto_sync=False)
        respx.get(FAKE_HOST_API + "system/compute_hosts").respond(
            json=[
                {
                    "id": "compute-2",
                    "hostname": "host2",
                    "server_address": "10.0.0.2",
                    "is_connector": False,
                    "is_simulator": True,
                    "is_connected": True,
                    "is_synced": True,
                    "admission_state": "ADMITTED",
                    "node_counts": {"deployed": 5, "running": 3, "orphans": 0},
                }
            ]
        )
        system.sync_compute_hosts()
        host = system._compute_hosts["compute-2"]
        assert host._node_counts == {"deployed": 5, "running": 3, "orphans": 0}

    @respx.mock
    def test_v2_9_response_with_both_nodes_and_node_counts(self):
        """v2.9 may include both fields; client should handle gracefully."""
        client = _make_client(respx.mock, "2.9.0")
        system = SystemManagement(client._session, auto_sync=False)
        respx.get(FAKE_HOST_API + "system/compute_hosts").respond(
            json=[
                {
                    "id": "compute-3",
                    "hostname": "host3",
                    "server_address": "10.0.0.3",
                    "is_connector": False,
                    "is_simulator": True,
                    "is_connected": True,
                    "is_synced": True,
                    "admission_state": "ADMITTED",
                    "nodes": ["node-x"],
                    "node_counts": {"deployed": 1, "running": 1, "orphans": 0},
                }
            ]
        )
        system.sync_compute_hosts()
        host = system._compute_hosts["compute-3"]
        assert host._node_counts == {"deployed": 1, "running": 1, "orphans": 0}


# ---------------------------------------------------------------------------
# Diagnostics endpoint compatibility
# ---------------------------------------------------------------------------


class TestDiagnosticsCompat:
    """get_diagnostics uses /diagnostics/{category} which exists on all versions."""

    @respx.mock
    def test_diagnostics_soft_fail_on_missing_category(self):
        """If a category endpoint returns an error, diagnostics records it
        rather than raising."""
        client = _make_client(respx.mock, "2.8.0")
        from virl2_client.virl2_client import DiagnosticsCategory

        respx.get(FAKE_HOST_API + "diagnostics/computes").respond(
            status_code=404,
            json={"description": "Not Found"},
        )
        result = client.get_diagnostics(DiagnosticsCategory.COMPUTES)
        assert "computes" in result
        assert "error" in result["computes"]

    @respx.mock
    def test_diagnostics_success(self):
        """Normal diagnostics fetch returns the data."""
        client = _make_client(respx.mock, "2.10.0")
        from virl2_client.virl2_client import DiagnosticsCategory

        respx.get(FAKE_HOST_API + "diagnostics/labs").respond(json={"active_labs": 3})
        result = client.get_diagnostics(DiagnosticsCategory.LABS)
        assert result == {"labs": {"active_labs": 3}}


# ---------------------------------------------------------------------------
# Missing endpoint 404 handling (features that exist only on newer servers)
# ---------------------------------------------------------------------------


class TestMissingEndpoint404:
    """When the client calls an endpoint that does not exist on the server,
    the server returns 404 and the client should raise APIError."""

    @respx.mock
    def test_404_on_associations_raises_api_error(self):
        """Lab associations endpoint missing on v2.8 gives a clean APIError."""
        client = _make_client(respx.mock, "2.8.0")
        lab = _make_lab(client)
        respx.get(FAKE_HOST_API + "labs/lab-id/associations").respond(
            status_code=404, json={"description": "Not Found"}
        )

        with pytest.raises(httpx.HTTPStatusError):
            lab._session.get(lab._url_for("associations"))


# ---------------------------------------------------------------------------
# Version comparison edge cases
# ---------------------------------------------------------------------------


class TestVersionComparison:
    """Verify Version comparison used in auth branching and guards."""

    def test_version_equality(self):
        assert Version("2.10.0") == Version("2.10.0")

    def test_version_less_than(self):
        assert Version("2.8.0") < Version("2.9.0")
        assert Version("2.9.0") < Version("2.10.0")

    def test_version_greater_equal(self):
        assert Version("2.10.0") >= Version("2.10.0")
        assert Version("2.10.0") >= Version("2.9.0")

    def test_version_with_patch(self):
        assert Version("2.8.1") >= Version("2.8.0")
        assert Version("2.8.1") < Version("2.9.0")

    def test_version_hashable(self):
        versions = {Version("2.8.0"), Version("2.9.0"), Version("2.8.0")}
        assert len(versions) == 2


# ---------------------------------------------------------------------------
# Version enforcement (check_controller_version)
# ---------------------------------------------------------------------------


class TestVersionEnforcement:
    """check_controller_version rejects controllers too old or too new."""

    @respx.mock
    def test_accepts_2_9_server(self):
        """Client should accept a server within the 3-minor support window."""
        client = _make_client(respx.mock, "2.9.0")
        assert client._session.controller_version == Version("2.9.0")

    @respx.mock
    def test_accepts_2_10_server(self):
        client = _make_client(respx.mock, "2.10.0")
        assert client._session.controller_version == Version("2.10.0")

    @respx.mock
    def test_rejects_too_old_server(self):
        """Client should reject a server outside the 3-minor support window."""
        from virl2_client.virl2_client import ClientLibrary as CL
        from virl2_client.virl2_client import InitializationError

        too_old = str(CL.VERSION.minor - 3)
        old_version = f"2.{too_old}.0"

        respx.get(FAKE_HOST_API + "system_information").respond(
            json={"version": old_version, "ready": True},
        )
        respx.post(FAKE_HOST_API + "authenticate").respond(json="T")

        with pytest.raises(InitializationError, match="Unsupported minor version"):
            ClientLibrary(url=FAKE_HOST, username="test", password="pa$$")


# ---------------------------------------------------------------------------
# Session carries controller version for models
# ---------------------------------------------------------------------------


class TestSessionControllerVersion:
    """The session object carries controller_version so models can access it."""

    @respx.mock
    def test_session_has_version(self):
        client = _make_client(respx.mock, "2.9.0")
        assert client._session.controller_version == Version("2.9.0")

    @respx.mock
    def test_model_can_read_version_via_session(self):
        client = _make_client(respx.mock, "2.8.0")
        system = SystemManagement(client._session, auto_sync=False)
        assert system._session.controller_version == Version("2.8.0")
