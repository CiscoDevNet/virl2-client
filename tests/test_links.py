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
"""Link-focused unit tests for link creation paths."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from helpers import RESOURCE_POOL_MANAGER, USER_MANAGEMENT
from respx import MockRouter

from virl2_client.models import Interface, Lab
from virl2_client.models.authentication import make_session


@pytest.mark.parametrize("connect_two_nodes", [True, False])
def test_create_link(respx_mock: MockRouter, connect_two_nodes: bool) -> None:
    """Create links via helper or explicit interface workflow.

    NOTE: LLM-generated test -- verify for correctness.

    :param respx_mock: HTTPX router fixture used to mock API requests.
    :param connect_two_nodes: Whether to use helper node-connect workflow.
    """
    respx_mock.post("mock://mock/labs/1/nodes").respond(json={"id": "n0"})
    respx_mock.post("mock://mock/labs/1/interfaces").respond(
        json={"id": "i0", "label": "eth0", "slot": 0}
    )
    respx_mock.post("mock://mock/labs/1/links").respond(
        json={"id": "l0", "label": "segment0"}
    )
    session = make_session("mock://mock")
    session.lock = MagicMock()
    lab = Lab(
        "laboratory",
        "1",
        session,
        "test",
        "test",
        auto_sync=False,
        wait=False,
        resource_pool_manager=RESOURCE_POOL_MANAGER,
        user_management=USER_MANAGEMENT,
    )
    node1 = lab.create_node("testnode", "server")
    node2 = lab.create_node("testnode", "server")
    if connect_two_nodes:
        link = lab.connect_two_nodes(node1, node2)
    else:
        node1_i1 = node1.create_interface()
        assert isinstance(node1_i1, Interface)
        node2_i1 = node2.create_interface()
        link = lab.create_link(node1_i1, node2_i1)

    assert link.as_dict() == {"id": "l0", "interface_a": "i0", "interface_b": "i0"}
    assert link.nodes[0].label == "testnode"
    assert link.nodes[1].label == "testnode"
    assert link.statistics == {
        "readbytes": 0,
        "readpackets": 0,
        "writebytes": 0,
        "writepackets": 0,
    }
    assert link.id == "l0"
    respx_mock.assert_all_called()


def test_link_wait_until_converged_timeout() -> None:
    """Raise RuntimeError when link convergence does not complete.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = Lab(
        "laboratory",
        "1",
        MagicMock(),
        "test",
        "test",
        auto_sync=False,
        resource_pool_manager=RESOURCE_POOL_MANAGER,
        user_management=USER_MANAGEMENT,
    )
    n1 = lab._create_node_local("n1", "n1", "iosv")
    n2 = lab._create_node_local("n2", "n2", "iosv")
    i1 = lab._create_interface_local("i1", "eth0", n1, 0)
    i2 = lab._create_interface_local("i2", "eth0", n2, 0)
    link = lab._create_link_local(i1, i2, "l1")

    with (
        patch.object(link, "has_converged", return_value=False),
        patch("virl2_client.models.link.time.sleep", return_value=None),
        pytest.raises(RuntimeError, match="maximum tries 1 exceeded"),
    ):
        link.wait_until_converged(max_iterations=1, wait_time=0)


def test_link_invalid_condition_name() -> None:
    """Raise ValueError for unknown named link condition.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = Lab(
        "laboratory",
        "1",
        MagicMock(),
        "test",
        "test",
        auto_sync=False,
        resource_pool_manager=RESOURCE_POOL_MANAGER,
        user_management=USER_MANAGEMENT,
    )
    n1 = lab._create_node_local("n1", "n1", "iosv")
    n2 = lab._create_node_local("n2", "n2", "iosv")
    i1 = lab._create_interface_local("i1", "eth0", n1, 0)
    i2 = lab._create_interface_local("i2", "eth0", n2, 0)
    link = lab._create_link_local(i1, i2, "l1")

    with pytest.raises(ValueError, match="Unknown condition name"):
        link.set_condition_by_name("unknown-speed")
