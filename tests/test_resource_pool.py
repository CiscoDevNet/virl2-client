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
"""Tests for ResourcePool property setters, usage payloads, and sync."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from virl2_client.exceptions import InvalidProperty
from virl2_client.models.resource_pool import ResourcePool, ResourcePoolManagement


def test_rp_property_setters() -> None:
    """Property setters update label, description, licenses, ram, cpus, disk_space, external_connectors.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    manager = ResourcePoolManagement(session, auto_sync=False)
    pool = ResourcePool(
        manager,
        "p1",
        "pool1",
        "desc",
        None,
        10,
        1024,
        2,
        20,
        ["ec1"],
        None,
        [],
    )

    session.patch.return_value.json.return_value = {}
    pool.label = "pool2"
    pool.description = "desc2"
    pool.licenses = 20
    pool.ram = 2048
    pool.cpus = 4
    pool.disk_space = 40
    pool.external_connectors = ["ec2"]

    assert pool.label == "pool2"
    assert pool.description == "desc2"
    assert pool.licenses == 20
    assert pool.ram == 2048
    assert pool.cpus == 4
    assert pool.disk_space == 40
    assert pool.external_connectors == ["ec2"]


def test_rp_get_usage() -> None:
    """get_usage returns limit and usage payload mapping.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    manager = ResourcePoolManagement(session, auto_sync=False)
    pool = ResourcePool(
        manager,
        "p1",
        "pool1",
        "desc",
        None,
        10,
        1024,
        2,
        20,
        ["ec1"],
        None,
        [],
    )

    session.get.return_value.json.return_value = {
        "limit": {
            "licenses": 20,
            "cpus": 4,
            "ram": 2048,
            "disk_space": 40,
            "external_connectors": ["ec2"],
        },
        "usage": {
            "licenses": 1,
            "cpus": 1,
            "ram": 512,
            "disk_space": 3,
            "external_connectors": [],
        },
    }
    usage = pool.get_usage()
    assert usage.limit.licenses == 20
    assert usage.usage.ram == 512


def test_rp_sync() -> None:
    """sync_resource_pools updates manager from server and removes stale pools.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    manager = ResourcePoolManagement(session, auto_sync=False)
    manager._resource_pools = {
        "keep": ResourcePool(
            manager, "keep", "old", "d", None, 1, 2, 3, 4, None, None, []
        ),
        "remove": ResourcePool(
            manager, "remove", "gone", "d", None, 1, 2, 3, 4, None, None, []
        ),
    }

    session.get.return_value.json.return_value = [
        {
            "id": "keep",
            "label": "new-label",
            "description": "d",
            "template": None,
            "licenses": 1,
            "ram": 2,
            "cpus": 3,
            "disk_space": 4,
            "external_connectors": None,
            "users": None,
            "user_pools": [],
        }
    ]
    manager.sync_resource_pools()
    assert "remove" not in manager._resource_pools
    assert manager._resource_pools["keep"].label == "new-label"


def test_rp_repr() -> None:
    """repr includes ResourcePool prefix.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    manager = ResourcePoolManagement(session, auto_sync=False)
    template_pool = ResourcePool(
        manager, "tpl", "tpl", "d", None, 1, 2, 3, 4, None, None, []
    )
    assert "ResourcePool(" in repr(template_pool)
    assert "Resource pool:" in str(template_pool)
    assert template_pool.template is None


@pytest.mark.parametrize(
    "pool_fixture,prop",
    [
        ("template_pool", "users"),
        ("user_pool", "user_pools"),
    ],
)
def test_rp_invalid_property(pool_fixture: str, prop: str) -> None:
    """Accessing users on template pool or user_pools on user pool raises InvalidProperty.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    manager = ResourcePoolManagement(session, auto_sync=False)
    if pool_fixture == "template_pool":
        pool = ResourcePool(
            manager, "tpl", "tpl", "d", None, 1, 2, 3, 4, None, None, []
        )
    else:
        pool = ResourcePool(
            manager, "u1", "u1", "d", "tpl", 1, 2, 3, 4, None, ["u"], []
        )

    with pytest.raises(InvalidProperty):
        _ = getattr(pool, prop)


def test_rp_users_user_pools() -> None:
    """users and user_pools return correct values on appropriate pool types.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    manager = ResourcePoolManagement(session, auto_sync=False)
    template_pool = ResourcePool(
        manager, "tpl", "tpl", "d", None, 1, 2, 3, 4, None, None, []
    )
    user_pool = ResourcePool(
        manager, "u1", "u1", "d", "tpl", 1, 2, 3, 4, None, ["u"], []
    )

    user_pool._users = ["alice"]
    template_pool._user_pools = ["u1"]
    assert user_pool.users == ["alice"]
    assert template_pool.user_pools == ["u1"]


def test_rp_remove() -> None:
    """remove calls session delete.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    manager = ResourcePoolManagement(session, auto_sync=False)
    user_pool = ResourcePool(
        manager, "u1", "u1", "d", "tpl", 1, 2, 3, 4, None, ["u"], []
    )
    user_pool.remove()
    user_pool._session.delete.assert_called()


def test_rp_update() -> None:
    """update applies local changes.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    manager = ResourcePoolManagement(session, auto_sync=False)
    user_pool = ResourcePool(
        manager, "u1", "u1", "d", "tpl", 1, 2, 3, 4, None, ["u"], []
    )
    user_pool.update({"label": "u2"})
    assert user_pool.label == "u2"


def test_rp_filters_blocked_keys() -> None:
    """Blocked keys are filtered from server update payload.

    NOTE: LLM-generated test -- verify for correctness.
    """
    manager = ResourcePoolManagement(MagicMock(), auto_sync=False)
    pool = ResourcePool(
        manager,
        pool_id="p1",
        label="pool",
        description=None,
        template=None,
        licenses=None,
        ram=None,
        cpus=None,
        disk_space=None,
        external_connectors=["ec1"],
        users=None,
        user_pools=None,
    )
    pool._set_resource_pool_properties(
        {
            "id": "blocked",
            "template": "blocked",
            "users": ["blocked"],
            "user_pools": ["blocked"],
            "label": "new-label",
        }
    )
    manager._session.patch.assert_called_with(
        "resource_pools/p1", json={"label": "new-label"}
    )


def test_rp_update_local_only() -> None:
    """_update with push_to_server=False updates local state only.

    NOTE: LLM-generated test -- verify for correctness.
    """
    manager = ResourcePoolManagement(MagicMock(), auto_sync=False)
    pool = ResourcePool(
        manager,
        pool_id="p1",
        label="pool",
        description=None,
        template=None,
        licenses=None,
        ram=None,
        cpus=None,
        disk_space=None,
        external_connectors=["ec1"],
        users=None,
        user_pools=None,
    )
    pool._update({"description": "desc"}, push_to_server=False)
    assert pool._description == "desc"


def test_rp_connectors_returns_copy() -> None:
    """external_connectors returns a copy; mutating it does not affect pool.

    NOTE: LLM-generated test -- verify for correctness.
    """
    manager = ResourcePoolManagement(MagicMock(), auto_sync=False)
    pool = ResourcePool(
        manager,
        pool_id="p1",
        label="pool",
        description=None,
        template=None,
        licenses=None,
        ram=None,
        cpus=None,
        disk_space=None,
        external_connectors=["ec1"],
        users=None,
        user_pools=None,
    )
    ext = pool.external_connectors
    assert ext == ["ec1"]
    ext.append("new")
    assert pool.external_connectors == ["ec1"]
