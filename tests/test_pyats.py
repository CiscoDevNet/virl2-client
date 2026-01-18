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

from unittest.mock import MagicMock, Mock

import pytest

from virl2_client.models import Lab
from virl2_client.models.node import Node

RESOURCE_POOL_MANAGER = Mock()


@pytest.fixture
def session() -> MagicMock:
    """Mocked HTTP session used by Lab/Node instances."""
    return MagicMock()


@pytest.fixture
def node(request: pytest.FixtureRequest, session: MagicMock) -> Node:
    """Create a Node (and Lab) for a given initial pyATS mapping.

    The parametrized value for this fixture (via ``indirect=["node"]``)
    is interpreted as the initial ``pyats`` dict or ``None``.
    """

    initial_pyats: dict | None = getattr(request, "param", None)
    lab = Lab(
        "test_lab",
        "lab-id",
        session,
        "user",
        "pass",
        auto_sync=False,
        resource_pool_manager=RESOURCE_POOL_MANAGER,
    )
    node_kwargs = {"pyats": initial_pyats} if initial_pyats is not None else {}
    return Node(
        lab,
        "node-id",
        "node1",
        "node-type",
        **node_kwargs,
    )


@pytest.mark.parametrize(
    "node, initial_pyats, expected_pyats",
    [
        # default: nothing set
        (None, {}, {"username": None, "password": None}),
        # set only username from default
        (None, {"username": "pyuser"}, {"username": "pyuser", "password": None}),
        # set only password from default
        (None, {"password": "pypass"}, {"username": None, "password": "pypass"}),
        # set both from default
        (
            None,
            {"username": "pyuser", "password": "pypass"},
            {"username": "pyuser", "password": "pypass"},
        ),
        # explicitly clear username and password back to None
        (
            {"username": "u", "password": "p"},
            {"username": None, "password": None},
            {"username": None, "password": None},
        ),
        # change only username, leaving password as-is (non-None)
        (
            {"username": "old", "password": "p"},
            {"username": "new"},
            {"username": "new", "password": "p"},
        ),
        # change only password, leaving username as-is (non-None)
        (
            {"username": "u", "password": "old"},
            {"password": "new"},
            {"username": "u", "password": "new"},
        ),
        # set username to None while keeping existing password
        (
            {"username": "u", "password": "p"},
            {"username": None},
            {"username": None, "password": "p"},
        ),
        # set password to None while keeping existing username
        (
            {"username": "u", "password": "p"},
            {"password": None},
            {"username": "u", "password": None},
        ),
    ],
    ids=[
        "default",
        "set_username_only",
        "set_password_only",
        "set_both",
        "clear_both",
        "change_username_only",
        "change_password_only",
        "set_username_none",
        "set_password_none",
    ],
    indirect=["node"],
)
def test_node_pyats_credentials_parametrized(
    session: MagicMock,
    node: Node,
    initial_pyats: dict[str, str | None],
    expected_pyats: dict[str, str | None],
) -> None:
    """Verify pyATS credential updates, including None handling, in one place."""
    if initial_pyats:
        node.set_pyats_credentials(**initial_pyats)

    assert node.pyats_credentials == expected_pyats

    # Default case (no kwargs) should not call the API at all.
    if not initial_pyats:
        session.patch.assert_not_called()
        return

    # For updates, ensure the correct payload goes out.
    session.patch.assert_called_once_with(
        "labs/lab-id/nodes/node-id?exclude_configurations=false",
        json={"pyats": expected_pyats},
    )
