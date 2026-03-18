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

"""Integration tests against a live CML server.

These tests verify that the v2.10 client works correctly against CML servers
of different versions (2.8, 2.9, 2.10). Each test exercises real HTTP calls
and requires a running CML instance.

Usage:
    CML_HOST=https://cml.local CML_PASS=secret pytest -m integration
    CML_HOST=https://cml.local CML_PASS=secret pytest -m integration -v \\
        --junitxml=pytest_integration.xml
"""

from __future__ import annotations

import json
import logging
import uuid

import pytest

from virl2_client import ClientLibrary
from virl2_client.virl2_client import Version

_LOGGER = logging.getLogger(__name__)

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Connection and authentication
# ---------------------------------------------------------------------------


class TestConnection:
    """Verify basic connectivity and authentication against the server."""

    def test_system_ready(self, cml_client):
        """Server reports system ready."""
        assert cml_client.is_system_ready() is True

    def test_system_info_has_version(self, cml_client):
        """system_info() returns a dict with a parseable version."""
        info = cml_client.system_info()
        assert "version" in info
        version = Version(info["version"])
        assert version.major == 2
        assert version.minor >= 8

    def test_system_info_has_ready_flag(self, cml_client):
        """system_info() includes the ready flag."""
        info = cml_client.system_info()
        assert "ready" in info
        assert info["ready"] is True

    def test_auth_token_acquired(self, cml_client):
        """Authentication succeeded and a bearer token is held."""
        assert cml_client._session.auth._token is not None


# ---------------------------------------------------------------------------
# Lab lifecycle (create, list, find, remove)
# ---------------------------------------------------------------------------


class TestLabLifecycle:
    """Verify lab CRUD operations."""

    def test_create_and_list(self, cml_client):
        """A newly created lab appears in all_labs()."""
        title = f"integ-lifecycle-{uuid.uuid4().hex[:8]}"
        lab = cml_client.create_lab(title=title)
        try:
            lab_ids = [l.id for l in cml_client.all_labs()]
            assert lab.id in lab_ids
        finally:
            lab.remove()

    def test_find_by_title(self, cml_client):
        """find_labs_by_title() returns labs matching the title."""
        title = f"integ-find-{uuid.uuid4().hex[:8]}"
        lab = cml_client.create_lab(title=title)
        try:
            found = cml_client.find_labs_by_title(title)
            assert len(found) == 1
            assert found[0].id == lab.id
        finally:
            lab.remove()

    def test_join_existing_lab(self, cml_client):
        """join_existing_lab() returns a usable Lab object."""
        lab = cml_client.create_lab(title="integ-join-test")
        try:
            joined = cml_client.join_existing_lab(lab.id)
            assert joined.id == lab.id
            assert joined.title == lab.title
        finally:
            lab.remove()

    def test_lab_details(self, temp_lab):
        """Lab.details() returns a dict with expected keys."""
        details = temp_lab.details()
        assert "state" in details
        assert "id" in details

    def test_empty_lab_has_no_nodes_or_links(self, temp_lab):
        """A freshly created lab has no nodes or links."""
        assert len(temp_lab.nodes()) == 0
        assert len(temp_lab.links()) == 0


# ---------------------------------------------------------------------------
# Topology: import, export, nodes, links
# ---------------------------------------------------------------------------


class TestTopology:
    """Verify topology creation and manipulation."""

    def test_create_nodes_and_link(self, two_alpine_nodes):
        """Create two nodes, connect them, verify the topology."""
        lab, n1, n2 = two_alpine_nodes
        link = lab.connect_two_nodes(n1, n2)
        assert len(lab.nodes()) == 2
        assert len(lab.links()) == 1
        assert link is not None

    def test_node_properties(self, two_alpine_nodes):
        """Created nodes have the expected definition and label."""
        lab, n1, n2 = two_alpine_nodes
        assert n1.node_definition == "alpine"
        assert n2.node_definition == "alpine"
        assert n1.label == "alpine-1"
        assert n2.label == "alpine-2"

    def test_create_interface(self, temp_lab):
        """Manually creating an interface on a node works."""
        node = temp_lab.create_node("iface-test", "alpine", populate_interfaces=True)
        initial_count = len(node.interfaces())
        node.create_interface()
        new_count = len(node.interfaces())
        assert new_count == initial_count + 1

    def test_import_topology(self, cml_client, test_dir):
        """import_lab() with a JSON topology string creates a synced lab."""
        topo_path = test_dir.parent / "test_data" / "sample_topology.json"
        topo_str = topo_path.read_text()
        lab = cml_client.import_lab(topo_str, title="integ-import-test")
        try:
            assert len(lab.nodes()) >= 1
            # The sample topology has an alpine node
            labels = [n.label for n in lab.nodes()]
            assert "alpine-0" in labels
        finally:
            lab.stop(wait=True)
            lab.wipe(wait=True)
            lab.remove()

    def test_export_topology(self, temp_lab):
        """download() returns a non-empty topology string."""
        temp_lab.create_node("export-node", "alpine", populate_interfaces=True)
        exported = temp_lab.download()
        assert len(exported) > 0
        # The download format is YAML; it should contain the node label
        assert "export-node" in exported

    def test_sync_topology(self, two_alpine_nodes):
        """sync() with topology_only=True succeeds without error."""
        lab, _, _ = two_alpine_nodes
        lab.connect_two_nodes(*two_alpine_nodes[1:])
        lab.sync(topology_only=True)
        assert len(lab.nodes()) == 2
        assert len(lab.links()) == 1


# ---------------------------------------------------------------------------
# Full node lifecycle: start, converge, stop, wipe
# ---------------------------------------------------------------------------


class TestNodeLifecycle:
    """Tests that start/stop nodes. These are slower due to boot times."""

    def test_start_lab_and_converge(self, two_alpine_nodes):
        """Starting a lab with alpine nodes reaches BOOTED state."""
        lab, n1, n2 = two_alpine_nodes
        lab.connect_two_nodes(n1, n2)
        lab.start(wait=True)
        # After convergence, nodes should be booted
        for node in lab.nodes():
            assert node.state() in ("BOOTED", "STARTED")

    def test_stop_lab(self, two_alpine_nodes):
        """Stopping a started lab transitions nodes to STOPPED."""
        lab, n1, n2 = two_alpine_nodes
        lab.connect_two_nodes(n1, n2)
        lab.start(wait=True)
        lab.stop(wait=True)
        for node in lab.nodes():
            assert node.state() == "STOPPED"

    def test_wipe_lab(self, two_alpine_nodes):
        """Wiping a stopped lab transitions the state to DEFINED_ON_CORE."""
        lab, n1, n2 = two_alpine_nodes
        lab.connect_two_nodes(n1, n2)
        lab.start(wait=True)
        lab.stop(wait=True)
        lab.wipe(wait=True)
        assert lab.state() == "DEFINED_ON_CORE"

    def test_node_start_stop_individual(self, two_alpine_nodes):
        """Starting and stopping individual nodes works."""
        lab, n1, n2 = two_alpine_nodes
        lab.connect_two_nodes(n1, n2)
        n1.start(wait=True)
        assert n1.state() in ("BOOTED", "STARTED")
        # n2 should still be stopped
        assert n2.state() in ("STOPPED", "DEFINED_ON_CORE")
        n1.stop(wait=True)
        assert n1.state() == "STOPPED"

    def test_lab_is_active_after_start(self, two_alpine_nodes):
        """Lab.is_active() returns True after start."""
        lab, n1, n2 = two_alpine_nodes
        lab.connect_two_nodes(n1, n2)
        lab.start(wait=True)
        assert lab.is_active() is True
        lab.stop(wait=True)
        assert lab.is_active() is False


# ---------------------------------------------------------------------------
# Operational data: stats, L3 addresses, sync
# ---------------------------------------------------------------------------


class TestOperationalData:
    """Tests that verify data retrieval from running nodes."""

    def test_sync_statistics(self, two_alpine_nodes):
        """sync_statistics() populates link statistics after boot."""
        lab, n1, n2 = two_alpine_nodes
        lab.connect_two_nodes(n1, n2)
        lab.start(wait=True)
        lab.sync_statistics()
        # After sync, link statistics should be accessible (may be zero)
        for link in lab.links():
            stats = link.statistics
            assert isinstance(stats, dict)

    def test_sync_layer3_addresses(self, two_alpine_nodes):
        """sync_layer3_addresses() runs without error after boot."""
        lab, n1, n2 = two_alpine_nodes
        lab.connect_two_nodes(n1, n2)
        lab.start(wait=True)
        lab.sync_layer3_addresses()
        # L3 addresses may or may not be populated depending on
        # node config, but the call should succeed

    def test_sync_operational(self, two_alpine_nodes):
        """sync_operational() populates compute_id on nodes."""
        lab, n1, n2 = two_alpine_nodes
        lab.connect_two_nodes(n1, n2)
        lab.start(wait=True)
        lab.sync_operational()
        for node in lab.nodes():
            # compute_id should be set for booted nodes
            assert node.compute_id is not None

    def test_full_sync(self, two_alpine_nodes):
        """sync(topology_only=False) runs all sub-syncs without error."""
        lab, n1, n2 = two_alpine_nodes
        lab.connect_two_nodes(n1, n2)
        lab.start(wait=True)
        lab.sync(topology_only=False)
        assert len(lab.nodes()) == 2
        assert len(lab.links()) == 1


# ---------------------------------------------------------------------------
# Node tags
# ---------------------------------------------------------------------------


class TestNodeTags:
    """Verify node tagging works across server versions."""

    def test_add_and_retrieve_tag(self, temp_lab):
        """Tags added to a node persist across sync."""
        node = temp_lab.create_node("tag-test", "alpine", populate_interfaces=True)
        node.add_tag("integ-tag-1")
        assert "integ-tag-1" in node.tags()

    def test_remove_tag(self, temp_lab):
        """Tags can be removed from a node."""
        node = temp_lab.create_node("tag-rm-test", "alpine", populate_interfaces=True)
        node.add_tag("to-remove")
        assert "to-remove" in node.tags()
        node.remove_tag("to-remove")
        assert "to-remove" not in node.tags()

    def test_find_nodes_by_tag(self, temp_lab):
        """Lab.find_nodes_by_tag() returns the correct nodes."""
        n1 = temp_lab.create_node("tagged-1", "alpine", populate_interfaces=True)
        temp_lab.create_node("tagged-2", "alpine", populate_interfaces=True)
        n1.add_tag("special")
        found = temp_lab.find_nodes_by_tag("special")
        assert len(found) == 1
        assert found[0].id == n1.id


# ---------------------------------------------------------------------------
# Version compatibility diagnostic
# ---------------------------------------------------------------------------


class TestVersionInfo:
    """Log server version info for diagnostic purposes."""

    def test_log_server_version(self, cml_client, server_version):
        """Log the server version being tested (always passes)."""
        _LOGGER.info(f"Server version under test: {server_version}")
        client_version = ClientLibrary.VERSION
        _LOGGER.info(f"Client library version: {client_version}")
        assert server_version is not None
