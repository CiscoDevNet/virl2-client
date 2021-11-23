#
# This file is part of CML 2
#
# Copyright 2021 Cisco Systems Inc.
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

"""Integration tests require access to a live CML2 instance."""

import pytest

from virl2_client import ClientLibrary


def find_labs_by_owner(owner, client_library_session):
    """
    Return a list of labs which match the given owner

    :param client_library_session: Session object
    :param owner: The owner to search for
    :type owner: str
    :returns: A list of lab objects which match the owner specified
    :rtype: list[models.Lab]
    """

    url = client_library_session._base_url + "populate_lab_tiles"
    response = client_library_session.session.get(url)
    response.raise_for_status()

    resp = response.json()

    # populate_lab_tiles response has been changed in 2.1
    # if it doesn't have a key "lab_tiles" then it's <2.1
    labs = resp.get("lab_tiles")
    if labs is None:
        labs = resp

    matched_lab_ids = []

    for lab_id, lab_data in labs.items():
        if lab_data["owner"] == owner:
            matched_lab_ids.append(lab_id)

    matched_labs = []
    for lab_id in matched_lab_ids:
        lab = client_library_session.join_existing_lab(lab_id)
        matched_labs.append(lab)

    return matched_labs


def cleanup_lab(client_library_session: ClientLibrary, lab_id):
    """Stop, wipe and delete the specified lab.

    :param client_library_session: Test client session object.
    :param lab_id: ID of the lab to be removed.
    :type client_library_session: ClientLibrary
    :type lab_id: int
    Raises requests.exceptions.HTTPError: If any request fails.
    """

    lab = client_library_session.join_existing_lab(lab_id)
    lab.stop()
    lab.wipe()
    client_library_session.remove_lab(lab_id)


@pytest.fixture
def cleanup_test_labs(client_library_session: ClientLibrary):
    """Remove all labs created during the test.
    Keep labs that existed previously."""

    lab_list_original = client_library_session.get_lab_list()
    yield
    lab_list = client_library_session.get_lab_list()
    for lab_id in lab_list:
        if lab_id not in lab_list_original:
            cleanup_lab(client_library_session, lab_id)


@pytest.fixture
def cleanup_test_users(client_library_session: ClientLibrary):
    """Remove all users created during the test. Remove all of their labs.
    Keep users that existed previously."""

    user_list_original = [
        user["id"] for user in client_library_session.user_management.users()
    ]
    yield
    user_list = [user["id"] for user in client_library_session.user_management.users()]
    for user_id in user_list:
        if user_id not in user_list_original:
            lab_list = client_library_session.all_labs(show_all=True)
            for lab in lab_list:
                if lab.owner == user_id:
                    cleanup_lab(client_library_session, lab.id)
            client_library_session.user_management.delete_user(user_id)


@pytest.fixture
def cleanup_test_groups(client_library_session: ClientLibrary):
    """Remove all groups created during the test.
    Keep groups that existed previously."""

    group_list_original = [
        group["id"] for group in client_library_session.group_management.groups()
    ]
    yield
    group_list = [
        group["id"] for group in client_library_session.group_management.groups()
    ]
    for group_id in group_list:
        if group_id not in group_list_original:
            client_library_session.group_management.delete_group(group_id)
