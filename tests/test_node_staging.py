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


def conditional_side_effect(*args, **kwargs):
    _ = args
    resp = kwargs.get("json", {})
    if node_staging := resp.get("node_staging"):
        if not isinstance(node_staging.get("enabled", False), bool):
            raise ValueError("Invalid value for enabled")
        if not isinstance(node_staging.get("abort_on_failure", False), bool):
            raise ValueError("Invalid value for abort_on_failure")
        if not isinstance(node_staging.get("start_remaining", True), bool):
            raise ValueError("Invalid value for start_remaining")
    elif priority := resp.get("priority"):
        if not isinstance(priority, int) or not 0 <= priority <= 10000:
            raise ValueError("Invalid value for priority")


def test_node_staging_initial_values():
    """Test that new lab has correct initial node staging values."""
    session = MagicMock()
    lab = Lab(
        "test_lab",
        "1",
        session,
        "user",
        "pass",
        auto_sync=False,
        resource_pool_manager=RESOURCE_POOL_MANAGER,
    )
    node = Node(
        lab,
        "node-id",
        "node1",
        "node-type",
    )

    assert lab._node_staging == {
        "enabled": False,
        "abort_on_failure": False,
        "start_remaining": True,
    }
    assert lab.node_staging == {
        "enabled": False,
        "abort_on_failure": False,
        "start_remaining": True,
    }
    assert node._priority is None
    assert node.priority is None


def test_lab_node_staging_setter():
    """Test setting the node_staging parameter on a Lab instance."""
    session = MagicMock()

    lab = Lab(
        title="Test Lab",
        lab_id="lab-id",
        session=session,
        username="user",
        password="pass",
        auto_sync=False,
        resource_pool_manager=RESOURCE_POOL_MANAGER,
    )
    node = Node(
        lab,
        "node-id",
        "node1",
        "node-type",
    )

    lab.set_node_staging(enabled=True, abort_on_failure=True, start_remaining=False)
    assert lab.node_staging == {
        "enabled": True,
        "abort_on_failure": True,
        "start_remaining": False,
    }
    session.patch.assert_called_once_with(
        "labs/lab-id",
        json={
            "node_staging": {
                "enabled": True,
                "abort_on_failure": True,
                "start_remaining": False,
            }
        },
    )
    session.patch.reset_mock()

    node.priority = 5
    session.patch.assert_called_once_with(
        "labs/lab-id/nodes/node-id?exclude_configurations=false",
        json={"priority": 5},
    )
    assert node.priority == 5


def test_lab_node_staging_setter_invalid():
    """Test setting invalid node_staging parameters raises ValueError."""
    session = MagicMock()
    session.patch.side_effect = conditional_side_effect
    lab = Lab(
        title="Test Lab",
        lab_id="lab-id",
        session=session,
        username="user",
        password="pass",
        auto_sync=False,
        resource_pool_manager=RESOURCE_POOL_MANAGER,
    )
    node = Node(
        lab,
        "node-id",
        "node1",
        "node-type",
    )

    with pytest.raises(ValueError):
        lab.set_node_staging(enabled="yes", abort_on_failure=True, start_remaining=True)
    with pytest.raises(ValueError):
        lab.set_node_staging(enabled=True, abort_on_failure="yes", start_remaining=True)
    with pytest.raises(ValueError):
        lab.set_node_staging(enabled=True, abort_on_failure=True, start_remaining="yes")
    with pytest.raises(ValueError):
        node.priority = "yes"
    with pytest.raises(ValueError):
        node.priority = -1
    with pytest.raises(ValueError):
        node.priority = 10001


def test_lab_node_staging_setter_no_change():
    """Test that setting node_staging to the same value does not trigger an API call."""
    session = MagicMock()
    lab = Lab(
        title="Test Lab",
        lab_id="lab-id",
        session=session,
        username="user",
        password="pass",
        auto_sync=False,
        resource_pool_manager=RESOURCE_POOL_MANAGER,
    )
    lab._node_staging = {
        "enabled": True,
        "abort_on_failure": True,
        "start_remaining": False,
    }
    node = Node(
        lab,
        "node-id",
        "node1",
        "node-type",
    )
    node._priority = 5

    lab.set_node_staging()
    session.patch.assert_not_called()

    lab.set_node_staging(enabled=False, abort_on_failure=False, start_remaining=True)
    session.patch.assert_called_once_with(
        "labs/lab-id",
        json={
            "node_staging": {
                "enabled": False,
                "abort_on_failure": False,
                "start_remaining": True,
            }
        },
    )
    session.patch.reset_mock()

    node.priority = 5
    session.patch.assert_called_once_with(
        "labs/lab-id/nodes/node-id?exclude_configurations=false",
        json={"priority": 5},
    )
    session.patch.reset_mock()

    node.priority = 10
    session.patch.assert_called_once_with(
        "labs/lab-id/nodes/node-id?exclude_configurations=false",
        json={"priority": 10},
    )


def test_lab_node_staging_setter_partial_update():
    """Test that setting only some node_staging parameters updates correctly."""
    session = MagicMock()
    lab = Lab(
        title="Test Lab",
        lab_id="lab-id",
        session=session,
        username="user",
        password="pass",
        auto_sync=False,
        resource_pool_manager=RESOURCE_POOL_MANAGER,
    )

    lab.set_node_staging(enabled=True)
    assert lab.node_staging == {
        "enabled": True,
        "abort_on_failure": False,
        "start_remaining": True,
    }
    session.patch.assert_called_with(
        "labs/lab-id",
        json={
            "node_staging": {
                "enabled": True,
                "abort_on_failure": False,
                "start_remaining": True,
            }
        },
    )

    lab.set_node_staging(abort_on_failure=True)
    assert lab.node_staging == {
        "enabled": True,
        "abort_on_failure": True,
        "start_remaining": True,
    }
    session.patch.assert_called_with(
        "labs/lab-id",
        json={
            "node_staging": {
                "enabled": True,
                "abort_on_failure": True,
                "start_remaining": True,
            }
        },
    )

    lab.set_node_staging(start_remaining=False)
    assert lab.node_staging == {
        "enabled": True,
        "abort_on_failure": True,
        "start_remaining": False,
    }
    session.patch.assert_called_with(
        "labs/lab-id",
        json={
            "node_staging": {
                "enabled": True,
                "abort_on_failure": True,
                "start_remaining": False,
            }
        },
    )
