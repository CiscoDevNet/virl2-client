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
"""Tests for user and group CRUD, associations, and ID lookups."""

from unittest.mock import MagicMock

import pytest

from virl2_client.models.group import GroupManagement
from virl2_client.models.user import UserManagement
from virl2_client.utils import OptInStatus


def test_user_list() -> None:
    """users returns list from server.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    mgr = UserManagement(session)
    session.get.return_value.json.return_value = [{"id": "u1"}]
    assert mgr.users() == [{"id": "u1"}]


def test_user_create() -> None:
    """create_user creates user with optional fields.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    mgr = UserManagement(session)
    session.post.return_value.json.return_value = {"id": "u1"}
    created = mgr.create_user(
        "user1",
        "pwd",
        fullname="User One",
        admin=True,
        groups=["g1"],
        associations=[{"lab_id": "l1", "roles": ["owner"]}],
        resource_pool="pool-1",
        opt_in=OptInStatus.ACCEPTED,
    )
    assert created["id"] == "u1"
    session.post.assert_called_once()


def test_user_update() -> None:
    """update_user patches user with optional fields.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    mgr = UserManagement(session)
    session.patch.return_value.json.return_value = {"id": "u1", "fullname": "X"}
    updated = mgr.update_user(
        "u1",
        fullname="X",
        password_dict={"old": "a", "new": "b"},
        pubkey="ssh-rsa aaa",
        tour_version="2",
    )
    assert updated["fullname"] == "X"


def test_user_groups_assoc() -> None:
    """user_groups and associations return group and lab data.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    mgr = UserManagement(session)
    session.get.return_value.json.return_value = {
        "groups": ["g1"],
        "associations": [{"lab_id": "l1", "roles": ["owner"]}],
    }
    assert mgr.user_groups("u1") == ["g1"]
    assert mgr.associations("u1") == [{"lab_id": "l1", "roles": ["owner"]}]


def test_user_update_assoc() -> None:
    """update_associations patches user associations.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    mgr = UserManagement(session)
    session.patch.return_value.json.return_value = {"associations": []}
    assert mgr.update_associations("u1", []) == {"associations": []}


def test_user_id() -> None:
    """user_id returns id for username.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    mgr = UserManagement(session)
    session.get.return_value.json.return_value = "u1"
    assert mgr.user_id("user1") == "u1"


def test_user_delete() -> None:
    """delete_user calls session delete.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    mgr = UserManagement(session)
    mgr.delete_user("u1")
    session.delete.assert_called()


@pytest.mark.parametrize(
    "opt_in,expected",
    [
        (True, "accepted"),
        (False, "declined"),
        (None, "unset"),
    ],
)
def test_prepare_body_opt_in_legacy_warns(opt_in: bool | None, expected: str) -> None:
    """_prepare_body with legacy opt_in bool triggers deprecation warning.

    NOTE: LLM-generated test -- verify for correctness.
    """
    mgr = UserManagement(MagicMock())
    data = {}
    with pytest.deprecated_call():
        mgr._prepare_body(data, opt_in=opt_in)
    assert data["opt_in"] == expected


def test_group_list() -> None:
    """groups returns list from server.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    mgr = GroupManagement(session)
    session.get.return_value.json.return_value = [{"id": "g1"}]
    assert mgr.groups() == [{"id": "g1"}]


def test_group_create() -> None:
    """create_group creates group with optional fields.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    mgr = GroupManagement(session)
    session.post.return_value.json.return_value = {"id": "g1"}
    assert (
        mgr.create_group(
            "group1",
            description="desc",
            members=["u1"],
            associations=[{"lab_id": "l1", "roles": ["owner"]}],
        )["id"]
        == "g1"
    )


def test_group_update() -> None:
    """update_group patches group.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    mgr = GroupManagement(session)
    session.patch.return_value.json.return_value = {"id": "g1", "name": "g2"}
    assert mgr.update_group("g1", name="g2")["name"] == "g2"


def test_group_members() -> None:
    """group_members and associations return member and lab data.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    mgr = GroupManagement(session)
    session.get.return_value.json.return_value = {
        "members": ["u1", "u2"],
        "associations": [{"lab_id": "l1", "roles": ["owner"]}],
    }
    assert mgr.group_members("g1") == ["u1", "u2"]
    assert mgr.associations("g1") == [{"lab_id": "l1", "roles": ["owner"]}]


def test_group_update_assoc() -> None:
    """update_associations patches group associations.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    mgr = GroupManagement(session)
    session.patch.return_value.json.return_value = {"associations": []}
    mgr.update_associations("g1", [])


def test_group_id() -> None:
    """group_id returns id for group name.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    mgr = GroupManagement(session)
    session.get.return_value.json.return_value = "g1"
    assert mgr.group_id("group1") == "g1"


def test_group_delete() -> None:
    """delete_group calls session delete.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    mgr = GroupManagement(session)
    mgr.delete_group("g1")
    session.delete.assert_called()


def test_group_prepare_body_optional_fields() -> None:
    """Include supported optional group payload fields in _prepare_body.

    NOTE: LLM-generated test -- verify for correctness.
    """
    groups = GroupManagement(MagicMock())
    data: dict[str, str | list] = {}

    groups._prepare_body(
        data,
        description="d",
        associations=[{"lab_id": "lab-1", "roles": ["owner"]}],
    )

    assert data["description"] == "d"
    assert data["associations"] == [{"lab_id": "lab-1", "roles": ["owner"]}]


def test_user_prepare_body_sets_opt_in_and_pool() -> None:
    """Set opt-in enum, resource pool, and fullname in user payload.

    NOTE: LLM-generated test -- verify for correctness.
    """
    users = UserManagement(MagicMock())
    data: dict = {}

    users._prepare_body(
        data,
        opt_in=OptInStatus.ACCEPTED,
        resource_pool="pool-1",
        fullname="User Name",
    )

    assert data["opt_in"] == OptInStatus.ACCEPTED.value
    assert data["resource_pool"] == "pool-1"
    assert data["fullname"] == "User Name"
