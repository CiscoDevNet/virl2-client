#
# This file is part of VIRL 2
# Copyright (c) 2019-2022, Cisco Systems, Inc.
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

"""Tests for Groups feature."""

import uuid
import pytest
import requests

from virl2_client import ClientConfig, ClientLibrary, LabNotFound

pytestmark = [pytest.mark.integration]

test_group_name = "integration_test_group"
test_username = "integration_test_user_groups"
test_username2 = "integration_test_user_groups_2"
test_password = "whatev3r"
test_lab_name = "integration_test_lab_groups"

groups_invalid = {
    "empty_name": {"name": ""},
    "name_not_string": {"name": 458},
    "bad_description": {"name": test_group_name, "description": [{}]},
    "bad_member_field_id": {"name": test_group_name, "members": ["Joe"]},
    "bad_labs_field_dict": {"name": test_group_name, "labs": [{}]},
    "bad_labs_field_string": {"name": test_group_name, "labs": ["abc"]},
    "bad_labs_field_id": {"name": test_group_name, "labs": [{"id": "abc"}]},
    "bad_labs_field_missing_id": {
        "name": test_group_name,
        "labs": [{"permissions": "read_only"}],
    },
}

users_invalid = {
    "id_not_string": 123,
    "invalid_id_format": "abc123-def456",
    "non_existent_group": "8ee2051d-3adb-4e76-9e51-ae63238f15bc",
}

labs_invalid = {
    "missing_permissions": [{"id": "8ee2051d-3adb-4e76-9e51-ae63238f15bc"}],
    "bad_permissions": [
        {"id": "8ee2051d-3adb-4e76-9e51-ae63238f15bc", "permission": "whatever"}
    ],
    "id_not_string": [{"id": 123, "permission": "red-only"}],
    "invalid_id_format": [{"id": "abc123-def456", "permission": "read_only"}],
}


@pytest.fixture(params=groups_invalid.keys())
def invalid_group_data(request):
    return groups_invalid[request.param]


@pytest.fixture(params=users_invalid.keys())
def invalid_user_data(request):
    return users_invalid[request.param]


@pytest.fixture(params=labs_invalid.keys())
def invalid_lab_data(request):
    return labs_invalid[request.param]


def test_create_group(cleanup_test_groups, client_library_session: ClientLibrary):
    """Create a valid group."""

    test_group1 = client_library_session.group_management.create_group(
        name=test_group_name
    )
    assert isinstance(test_group1, dict)
    assert "id" in test_group1 and uuid.UUID(test_group1["id"], version=4)
    assert test_group1["description"] == ""
    assert test_group1["members"] == [] and test_group1["labs"] == []
    assert test_group1["id"] in [
        group["id"] for group in client_library_session.group_management.groups()
    ]

    assert test_group1 == client_library_session.group_management.get_group(
        test_group1["id"]
    )


def test_update_group_description(
    cleanup_test_groups, client_library_session: ClientLibrary
):
    """Create a group, then update its description and verify."""

    description = "integration test group"

    test_group1 = client_library_session.group_management.create_group(
        name=test_group_name
    )
    group1_id = test_group1["id"]

    client_library_session.group_management.update_group(
        group_id=group1_id, description=description
    )

    test_group1 = client_library_session.group_management.get_group(group_id=group1_id)
    assert test_group1["name"] == test_group_name
    assert test_group1["description"] == description


def test_rename_group(cleanup_test_groups, client_library_session: ClientLibrary):
    """Create a group, rename it and verify."""

    modified_name = "integration_test_group_renamed"

    test_group1 = client_library_session.group_management.create_group(
        name=test_group_name
    )
    group1_id = test_group1["id"]

    client_library_session.group_management.update_group(
        group_id=group1_id, name=modified_name
    )

    test_group1 = client_library_session.group_management.get_group(group_id=group1_id)
    assert test_group1["name"] == modified_name


def test_update_nonexistent_group(client_library_session: ClientLibrary):
    """Try to update a group that does not exist, expect to fail."""

    with pytest.raises(requests.exceptions.HTTPError) as err:
        client_library_session.group_management.update_group(
            group_id="8ee2051d-3adb-4e76-9e51-ae63238f15bc",
            description="non existent group",
        )
    assert err.value.response.status_code == 404


def test_delete_group(cleanup_test_groups, client_library_session: ClientLibrary):
    """Create a group, remove it and verify it is removed."""

    test_group1 = client_library_session.group_management.create_group(
        name=test_group_name
    )
    group1_id = test_group1["id"]

    client_library_session.group_management.delete_group(group_id=group1_id)

    with pytest.raises(requests.exceptions.HTTPError) as err:
        client_library_session.group_management.get_group(group_id=group1_id)
    assert err.value.response.status_code == 404


def test_delete_nonexistent_group(client_library_session: ClientLibrary):
    """Try to delete a group that does not exit, expect to fail."""

    with pytest.raises(requests.exceptions.HTTPError) as err:
        client_library_session.group_management.delete_group(
            group_id="8ee2051d-3adb-4e76-9e51-ae63238f15bc"
        )
    assert err.value.response.status_code == 404


def test_create_group_duplicate(
    cleanup_test_groups, client_library_session: ClientLibrary
):
    """Create a valid group, then try to create another with the same name and expect to fail."""

    client_library_session.group_management.create_group(name=test_group_name)
    with pytest.raises(requests.exceptions.HTTPError) as err:
        client_library_session.group_management.create_group(name=test_group_name)
    assert err.value.response.status_code == 422
    assert "Group already exists" in err.value.response.text


def test_create_group_invalid_data(
    invalid_group_data, cleanup_test_groups, client_library_session: ClientLibrary
):
    """Try creating group with some invalid data, expect to fail."""

    with pytest.raises(requests.exceptions.HTTPError) as err:
        client_library_session.group_management.create_group(**invalid_group_data)
    assert err.value.response.status_code == 400


def test_add_user_to_group(
    cleanup_test_users, cleanup_test_groups, client_library_session: ClientLibrary
):
    """Create a group, create a user and add the user to the group through group endpoint."""

    test_group1 = client_library_session.group_management.create_group(
        name=test_group_name
    )
    group1_id = test_group1["id"]

    test_user1 = client_library_session.user_management.create_user(
        username=test_username, pwd=test_password
    )
    user1_id = test_user1["id"]

    client_library_session.group_management.update_group(
        group_id=group1_id, members=[user1_id]
    )

    assert user1_id in client_library_session.group_management.group_members(
        group_id=group1_id
    )
    assert group1_id in client_library_session.user_management.user_groups(
        user_id=user1_id
    )


def test_add_group_to_user(
    cleanup_test_users, cleanup_test_groups, client_library_session: ClientLibrary
):
    """Create a group, create a user and add the user to the group through user endpoint."""

    test_group1 = client_library_session.group_management.create_group(
        name=test_group_name
    )
    group1_id = test_group1["id"]

    test_user1 = client_library_session.user_management.create_user(
        username=test_username, pwd=test_password
    )
    user1_id = test_user1["id"]

    client_library_session.user_management.update_user(
        user_id=user1_id, groups=[group1_id]
    )

    assert user1_id in client_library_session.group_management.group_members(
        group_id=group1_id
    )
    assert group1_id in client_library_session.user_management.user_groups(
        user_id=user1_id
    )


def test_add_lab_to_group(
    cleanup_test_labs, cleanup_test_groups, client_library_session: ClientLibrary
):
    """Create a group, create a lab and add the lab to the group through group endpoint."""

    test_group1 = client_library_session.group_management.create_group(
        name=test_group_name
    )
    group1_id = test_group1["id"]

    test_lab1 = client_library_session.create_lab(title=test_lab_name)
    lab_id = test_lab1.id

    lab_entry = {"id": lab_id, "permission": "read_only"}
    group_entry = {"id": group1_id, "permission": "read_only"}

    client_library_session.group_management.update_group(
        group_id=group1_id, labs=[lab_entry]
    )

    assert lab_id in client_library_session.group_management.group_labs(
        group_id=group1_id
    )
    assert group_entry in test_lab1.groups


def test_add_group_to_lab(
    cleanup_test_labs, cleanup_test_groups, client_library_session: ClientLibrary
):
    """Create a group, create a lab and add the lab to the group through lab endpoint."""

    test_group1 = client_library_session.group_management.create_group(
        name=test_group_name
    )
    group1_id = test_group1["id"]

    test_lab1 = client_library_session.create_lab(title=test_lab_name)
    lab_id = test_lab1.id

    group_entry = {"id": group1_id, "permission": "read_only"}

    test_lab1.update_lab_groups([group_entry])

    assert lab_id in client_library_session.group_management.group_labs(
        group_id=group1_id
    )
    assert group_entry in test_lab1.groups


def test_update_group_invalid_data(
    invalid_group_data, cleanup_test_groups, client_library_session: ClientLibrary
):
    """Create a group, try updating it with some invalid data, expect to fail."""

    test_group1 = client_library_session.group_management.create_group(
        name=test_group_name
    )
    with pytest.raises(requests.exceptions.HTTPError) as err:
        client_library_session.group_management.update_group(
            group_id=test_group1["id"], **invalid_group_data
        )
    assert err.value.response.status_code == 400


def test_get_non_existent_group(client_library_session: ClientLibrary):
    """Try to get a group that doesn't exist, expect a clean failure."""

    with pytest.raises(requests.exceptions.HTTPError) as err:
        client_library_session.group_management.get_group(
            group_id="8ee2051d-3adb-4e76-9e51-ae63238f15bc"
        )
    assert err.value.response.status_code == 404


def test_get_users_of_non_existent_group(client_library_session: ClientLibrary):
    """Try to get users of a group that does not exist, expect to fail."""

    with pytest.raises(requests.exceptions.HTTPError) as err:
        client_library_session.group_management.group_members(
            group_id="8ee2051d-3adb-4e76-9e51-ae63238f15bc"
        )
    assert err.value.response.status_code == 404


def test_get_labs_of_non_existent_group(client_library_session: ClientLibrary):
    """Try to get labs of a group that does not exist, expect to fail."""
    with pytest.raises(requests.exceptions.HTTPError) as err:
        client_library_session.group_management.group_labs(
            group_id="8ee2051d-3adb-4e76-9e51-ae63238f15bc"
        )
    assert err.value.response.status_code == 404


def test_create_user_with_group(
    cleanup_test_users, cleanup_test_groups, client_library_session: ClientLibrary
):
    """Create a group, then create an user already assigned to the group and verify."""

    test_group1 = client_library_session.group_management.create_group(
        name=test_group_name
    )
    group1_id = test_group1["id"]

    test_user1 = client_library_session.user_management.create_user(
        username=test_username, pwd=test_password, groups=[group1_id]
    )
    user1_id = test_user1["id"]

    assert user1_id in client_library_session.group_management.group_members(
        group_id=group1_id
    )


def test_create_group_with_user_lab(
    cleanup_test_labs,
    cleanup_test_users,
    cleanup_test_groups,
    client_library_session: ClientLibrary,
):
    """Create a user, create a lab, then create a group assigned to both and verify."""

    test_user1 = client_library_session.user_management.create_user(
        username=test_username, pwd=test_password
    )
    user1_id = test_user1["id"]

    test_lab1 = client_library_session.create_lab(title=test_lab_name)
    lab_id = test_lab1.id

    lab_entry = {"id": lab_id, "permission": "read_only"}

    test_group1 = client_library_session.group_management.create_group(
        name=test_group_name, members=[user1_id], labs=[lab_entry]
    )
    group1_id = test_group1["id"]

    group_entry = {"id": group1_id, "permission": "read_only"}

    assert group1_id in client_library_session.user_management.user_groups(
        user_id=user1_id
    )
    assert group_entry in test_lab1.groups


def test_add_group_to_user_negative(
    invalid_user_data, cleanup_test_users, client_library_session: ClientLibrary
):
    """Create a user, try updating the user with invalid group data and expect to fail."""

    test_user1 = client_library_session.user_management.create_user(
        username=test_username, pwd=test_password
    )
    user1_id = test_user1["id"]

    with pytest.raises(requests.exceptions.HTTPError) as err:
        client_library_session.user_management.update_user(
            user_id=user1_id, groups=invalid_user_data
        )
    assert err.value.response.status_code == 400


def test_add_group_to_lab_negative(
    invalid_lab_data, cleanup_test_labs, client_library_session: ClientLibrary
):
    """Create a lab, try updating the lab with invalid group data and expect to fail."""

    test_lab1 = client_library_session.create_lab(title=test_lab_name)

    with pytest.raises(requests.exceptions.HTTPError) as err:
        test_lab1.update_lab_groups(invalid_lab_data)
    assert err.value.response.status_code == 400


def test_remove_group_with_users_labs(
    cleanup_test_labs,
    cleanup_test_users,
    cleanup_test_groups,
    client_library_session: ClientLibrary,
):
    """Create group, user, lab, add both to group.
    Remove the group and verify associations are removed."""

    test_user1 = client_library_session.user_management.create_user(
        username=test_username, pwd=test_password
    )
    user1_id = test_user1["id"]

    test_lab1 = client_library_session.create_lab(title=test_lab_name)
    lab_id = test_lab1.id

    lab_entry = {"id": lab_id, "permission": "read_only"}

    test_group1 = client_library_session.group_management.create_group(
        name=test_group_name, members=[user1_id], labs=[lab_entry]
    )
    group1_id = test_group1["id"]

    client_library_session.group_management.delete_group(group1_id)
    assert group1_id not in client_library_session.user_management.user_groups(
        user_id=user1_id
    )
    assert lab_entry not in test_lab1.groups


def test_delete_user_in_group(
    cleanup_test_users, cleanup_test_groups, client_library_session: ClientLibrary
):
    """Create group, user, add user to group.
    Remove the user and verify group association is removed."""

    test_user1 = client_library_session.user_management.create_user(
        username=test_username, pwd=test_password
    )
    user1_id = test_user1["id"]

    test_group1 = client_library_session.group_management.create_group(
        name=test_group_name, members=[user1_id]
    )
    group1_id = test_group1["id"]

    client_library_session.user_management.delete_user(user_id=user1_id)
    assert user1_id not in client_library_session.group_management.group_members(
        group_id=group1_id
    )


def test_delete_lab_in_group(
    cleanup_test_labs, cleanup_test_groups, client_library_session: ClientLibrary
):
    """Create group, lab, add lab to group.
    Remove the lab and verify group association is removed."""

    test_lab1 = client_library_session.create_lab(title=test_lab_name)
    lab_id = test_lab1.id

    lab_entry = {"id": lab_id, "permission": "read_only"}

    test_group1 = client_library_session.group_management.create_group(
        name=test_group_name, labs=[lab_entry]
    )
    group1_id = test_group1["id"]

    test_lab1.remove()

    assert lab_entry not in client_library_session.group_management.group_labs(
        group_id=group1_id
    )


# ========== permissions ==========


def test_default_permissions(
    cleanup_test_labs,
    cleanup_test_users,
    cleanup_test_groups,
    client_config: ClientConfig,
    client_library_session: ClientLibrary,
):
    """Create group, two users and lab.
    Verify non-admin user cannot see any groups, labs or other users."""

    test_user1 = client_library_session.user_management.create_user(
        username=test_username, pwd=test_password, admin=False
    )
    user1_id = test_user1["id"]
    test_user2 = client_library_session.user_management.create_user(
        username=test_username2, pwd=test_password, admin=False
    )
    user2_id = test_user2["id"]

    test_lab1 = client_library_session.create_lab(title=test_lab_name)
    lab_id = test_lab1.id

    test_group1 = client_library_session.group_management.create_group(
        name=test_group_name
    )
    group1_id = test_group1["id"]

    test_user_session = ClientLibrary(
        client_config.url,
        username=test_username,
        password=test_password,
        ssl_verify=client_config.ssl_verify,
        allow_http=client_config.allow_http,
    )

    test_user_session.user_management.get_user(user1_id)
    with pytest.raises(requests.exceptions.HTTPError) as err:
        test_user_session.user_management.get_user(user2_id)
    assert err.value.response.status_code == 403

    with pytest.raises(requests.exceptions.HTTPError) as err:
        test_user_session.group_management.get_group(group_id=group1_id)
    assert err.value.response.status_code == 403

    with pytest.raises(LabNotFound):
        test_user_session.join_existing_lab(lab_id=lab_id)


def test_group_permissions(
    cleanup_test_labs,
    cleanup_test_users,
    cleanup_test_groups,
    client_config: ClientConfig,
    client_library_session: ClientLibrary,
):
    """Create group and user, add user to group.
    Verify user can see the group, but cannot modify the group."""

    test_user1 = client_library_session.user_management.create_user(
        username=test_username, pwd=test_password, admin=False
    )
    user1_id = test_user1["id"]

    test_group1 = client_library_session.group_management.create_group(
        name=test_group_name, members=[user1_id]
    )
    group1_id = test_group1["id"]

    test_user_session = ClientLibrary(
        client_config.url,
        username=test_username,
        password=test_password,
        ssl_verify=client_config.ssl_verify,
        allow_http=client_config.allow_http,
    )

    test_user_session.group_management.get_group(group_id=group1_id)

    with pytest.raises(requests.exceptions.HTTPError) as err:
        test_user_session.group_management.update_group(group_id=group1_id, members=[])
    assert err.value.response.status_code == 403


def test_user_permissions(
    cleanup_test_labs,
    cleanup_test_users,
    cleanup_test_groups,
    client_config: ClientConfig,
    client_library_session: ClientLibrary,
):
    """Create group and two users, add both to group.
    Verify one user can see but not modify the other user."""

    test_user1 = client_library_session.user_management.create_user(
        username=test_username, pwd=test_password, admin=False
    )
    user1_id = test_user1["id"]
    test_user2 = client_library_session.user_management.create_user(
        username=test_username2, pwd=test_password, admin=False
    )
    user2_id = test_user2["id"]

    test_group1 = client_library_session.group_management.create_group(
        name=test_group_name, members=[user1_id, user2_id]
    )
    group1_id = test_group1["id"]

    test_user_session = ClientLibrary(
        client_config.url,
        username=test_username,
        password=test_password,
        ssl_verify=client_config.ssl_verify,
        allow_http=client_config.allow_http,
    )

    # Can see user ID in group members
    assert user2_id in test_user_session.group_management.group_members(
        group_id=group1_id
    )

    # Can't see the user directly
    with pytest.raises(requests.exceptions.HTTPError) as err:
        test_user_session.user_management.get_user(user_id=user2_id)
    assert err.value.response.status_code == 403

    # Can't modify the user
    with pytest.raises(requests.exceptions.HTTPError) as err:
        test_user_session.user_management.update_user(user_id=user2_id, groups=[])
    assert err.value.response.status_code == 403


def test_lab_permissions(
    cleanup_test_labs,
    cleanup_test_users,
    cleanup_test_groups,
    client_config: ClientConfig,
    client_library_session: ClientLibrary,
):
    """Create group, user and three labs.
    Setup permissions for read-only, read-write and none, verify permissions.
    Verify user cannot change lab group membership."""

    test_user1 = client_library_session.user_management.create_user(
        username=test_username, pwd=test_password, admin=False
    )
    user1_id = test_user1["id"]

    test_lab_readonly = client_library_session.create_lab(title=test_lab_name)
    lab_id_readonly = test_lab_readonly.id
    test_lab_readwrite = client_library_session.create_lab(title=test_lab_name)
    lab_id_readwrite = test_lab_readwrite.id
    test_lab_unallowed = client_library_session.create_lab(title=test_lab_name)
    lab_id_unallowed = test_lab_unallowed.id

    lab_entry_readonly = {"id": lab_id_readonly, "permission": "read_only"}
    lab_entry_readwrite = {"id": lab_id_readwrite, "permission": "read_write"}

    test_group1 = client_library_session.group_management.create_group(
        name=test_group_name,
        members=[user1_id],
        labs=[lab_entry_readonly, lab_entry_readwrite],
    )

    test_user_session = ClientLibrary(
        client_config.url,
        username=test_username,
        password=test_password,
        ssl_verify=client_config.ssl_verify,
        allow_http=client_config.allow_http,
    )

    labs = test_user_session.get_lab_list(show_all=True)
    assert lab_id_unallowed not in labs
    assert lab_id_readonly in labs and lab_id_readwrite in labs

    with pytest.raises(LabNotFound):
        test_user_session.join_existing_lab(lab_id_unallowed)

    lab_readonly = test_user_session.join_existing_lab(lab_id_readonly)
    lab_readwrite = test_user_session.join_existing_lab(lab_id_readwrite)

    with pytest.raises(requests.exceptions.HTTPError) as err:
        lab_readonly.description = "should not be editable"
    assert err.value.response.status_code == 403

    lab_readwrite.description = "integration test lab group permissions read-write"


def test_lab_permission_update(
    cleanup_test_labs,
    cleanup_test_users,
    cleanup_test_groups,
    client_config: ClientConfig,
    client_library_session: ClientLibrary,
):
    """Create group, user and lab, assign to group.
    Update lab permission from read-only to read-write, verify user can now modify lab."""

    test_user1 = client_library_session.user_management.create_user(
        username=test_username, pwd=test_password
    )
    user1_id = test_user1["id"]

    test_lab1 = client_library_session.create_lab(title=test_lab_name)
    lab_id = test_lab1.id

    lab_entry_readonly = {"id": lab_id, "permission": "read_only"}
    lab_entry_readwrite = {"id": lab_id, "permission": "read_write"}

    test_group1 = client_library_session.group_management.create_group(
        name=test_group_name, members=[user1_id], labs=[lab_entry_readonly]
    )
    group1_id = test_group1["id"]

    test_user_session = ClientLibrary(
        client_config.url,
        username=test_username,
        password=test_password,
        ssl_verify=client_config.ssl_verify,
        allow_http=client_config.allow_http,
    )

    lab = test_user_session.join_existing_lab(lab_id=lab_id)

    # Check lab is not editable
    with pytest.raises(requests.exceptions.HTTPError) as err:
        lab.description = "should not be editable"
    assert err.value.response.status_code == 403

    # Update to read_write, check it is editable
    client_library_session.group_management.update_group(
        group_id=group1_id, labs=[lab_entry_readwrite]
    )
    lab.description = "integration test lab group permissions read-write"

    # Revert to read-only, check it is not editable
    client_library_session.group_management.update_group(
        group_id=group1_id, labs=[lab_entry_readonly]
    )
    with pytest.raises(requests.exceptions.HTTPError) as err:
        lab.description = "should not be editable"
    assert err.value.response.status_code == 403


def test_remove_user_from_group(
    cleanup_test_labs,
    cleanup_test_users,
    cleanup_test_groups,
    client_config: ClientConfig,
    client_library_session: ClientLibrary,
):
    """Create group, user and lab, assign to group.
    Remove user from group, verify user loses permissions."""

    test_user1 = client_library_session.user_management.create_user(
        username=test_username, pwd=test_password
    )
    user1_id = test_user1["id"]

    test_lab1 = client_library_session.create_lab(title=test_lab_name)
    lab_id = test_lab1.id

    lab_entry = {"id": lab_id, "permission": "read_only"}

    test_group1 = client_library_session.group_management.create_group(
        name=test_group_name, members=[user1_id], labs=[lab_entry]
    )
    group1_id = test_group1["id"]

    test_user_session = ClientLibrary(
        client_config.url,
        username=test_username,
        password=test_password,
        ssl_verify=client_config.ssl_verify,
        allow_http=client_config.allow_http,
    )

    # Check that user has access to lab
    lab = test_user_session.join_existing_lab(lab_id=lab_id)

    # Remove user from group and verify he loses lab access
    client_library_session.group_management.update_group(group_id=group1_id, members=[])
    with pytest.raises(requests.exceptions.HTTPError) as err:
        lab.description = "should not be editable"
    assert err.value.response.status_code == 404
    with pytest.raises(LabNotFound):
        test_user_session.join_existing_lab(lab_id=lab_id)


def test_remove_lab_from_group(
    cleanup_test_labs,
    cleanup_test_users,
    cleanup_test_groups,
    client_config: ClientConfig,
    client_library_session: ClientLibrary,
):
    """Create group, user and lab, assign to group.
    Remove lab from group, verify user can no longer access it."""

    test_user1 = client_library_session.user_management.create_user(
        username=test_username, pwd=test_password
    )
    user1_id = test_user1["id"]

    test_lab1 = client_library_session.create_lab(title=test_lab_name)
    lab_id = test_lab1.id

    lab_entry = {"id": lab_id, "permission": "read_only"}

    test_group1 = client_library_session.group_management.create_group(
        name=test_group_name, members=[user1_id], labs=[lab_entry]
    )
    group1_id = test_group1["id"]

    test_user_session = ClientLibrary(
        client_config.url,
        username=test_username,
        password=test_password,
        ssl_verify=client_config.ssl_verify,
        allow_http=client_config.allow_http,
    )

    # Check that user has access to lab
    lab = test_user_session.join_existing_lab(lab_id=lab_id)

    # Remove lab from group and verify user loses lab access
    client_library_session.group_management.update_group(group_id=group1_id, labs=[])
    with pytest.raises(requests.exceptions.HTTPError) as err:
        lab.description = "should not be editable"
    assert err.value.response.status_code == 404
    with pytest.raises(LabNotFound):
        test_user_session.join_existing_lab(lab_id=lab_id)
