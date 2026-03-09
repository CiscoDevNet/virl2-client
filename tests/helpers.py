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
"""Shared test helpers: lab factory, topology builder, and resource-pool mock.

None of the names in this module are pytest fixtures.  Import them directly:

    from helpers import make_lab, make_lab_with_topology, RESOURCE_POOL_MANAGER
"""

from __future__ import annotations

from typing import NamedTuple
from unittest.mock import MagicMock, Mock

from virl2_client.models import Lab
from virl2_client.models.interface import Interface
from virl2_client.models.link import Link
from virl2_client.models.node import Node

# ---------------------------------------------------------------------------
# Resource-pool manager mock
# ---------------------------------------------------------------------------

# Tests that do not assert on the resource-pool manager itself can reference
# this constant.  Tests that need to observe calls should pass their own
# Mock() to make_lab(resource_pool_manager=...).
RESOURCE_POOL_MANAGER: Mock = Mock()


# ---------------------------------------------------------------------------
# Lab factory
# ---------------------------------------------------------------------------


def make_lab(
    session: MagicMock | None = None,
    wait: bool = False,
    resource_pool_manager: Mock | None = None,
) -> Lab:
    """Create a Lab instance configured for unit testing.

    No real network connections are made.  A new MagicMock session is
    created internally if *session* is not provided, letting callers that
    need to assert on HTTP calls supply their own mock.

    :param session: Mocked HTTP session; a new MagicMock is created
        when None.
    :param wait: Default wait behaviour for lab operations.
    :param resource_pool_manager: Resource pool manager mock; uses the
        module-level RESOURCE_POOL_MANAGER when None.
    :returns: A Lab ready for unit testing.
    """
    return Lab(
        "lab",
        "l1",
        session if session is not None else MagicMock(),
        "user",
        "pass",
        auto_sync=False,
        wait=wait,
        resource_pool_manager=(
            resource_pool_manager
            if resource_pool_manager is not None
            else RESOURCE_POOL_MANAGER
        ),
    )


# ---------------------------------------------------------------------------
# Topology builder
# ---------------------------------------------------------------------------


class Topology(NamedTuple):
    """Lightweight container returned by :func:`make_lab_with_topology`."""

    lab: Lab
    nodes: tuple[Node, Node]
    interfaces: tuple[Interface, Interface]
    link: Link


def make_lab_with_topology(
    session: MagicMock | None = None,
) -> Topology:
    """Create a lab with two nodes connected by a single link.

    Covers the most common test-setup pattern:
    node_a(eth0) --link-- node_b(eth0).

    :param session: Mocked HTTP session; a new MagicMock is created
        when None.
    :returns: A :class:`Topology` containing the lab and its elements.
    """
    if session is None:
        session = MagicMock()
        session.base_url = "mock://mock"
    lab = make_lab(session=session)
    n1 = lab._create_node_local("n1", "n1", "iosv")
    n2 = lab._create_node_local("n2", "n2", "iosv")
    i1 = lab._create_interface_local("i1", "eth0", n1, 0)
    i2 = lab._create_interface_local("i2", "eth0", n2, 0)
    link = lab._create_link_local(i1, i2, "l1")
    return Topology(lab=lab, nodes=(n1, n2), interfaces=(i1, i2), link=link)
