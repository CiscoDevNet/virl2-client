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

"""Tests for User Management."""

import pytest
import logging
import requests

from virl2_client import ClientConfig, ClientLibrary

pytestmark = [pytest.mark.integration]

# TODO: split into more granular test cases and document


def test_user_management(cleanup_test_users, client_library_session: ClientLibrary):
    test_user = "test_user"
    test_password = "test_password"

    res = client_library_session.user_management.create_user(
        username=test_user, pwd=test_password
    )
    assert isinstance(res, dict)
    assert res["username"] == test_user
    assert res["fullname"] == ""
    assert res["description"] == ""
    test_user_id = res["id"]

    # changing only fullname
    res = client_library_session.user_management.update_user(
        user_id=test_user_id, fullname=test_user
    )
    assert res["fullname"] == test_user
    assert res["description"] == ""

    # changing only description; already changed fullname must be kept
    res = client_library_session.user_management.update_user(
        user_id=test_user_id, description=test_user
    )
    assert res["fullname"] == test_user
    assert res["description"] == test_user

    # changing both fullname and description
    res = client_library_session.user_management.update_user(
        user_id=test_user_id,
        description=test_user + test_user,
        fullname=test_user + test_user,
    )
    assert res["fullname"] == test_user + test_user
    assert res["description"] == test_user + test_user

    user = client_library_session.user_management.get_user(test_user_id)
    assert isinstance(user, dict)
    assert user["username"] == test_user
    assert "admin" in user and "groups" in user
    assert res["fullname"] == test_user + test_user
    assert res["description"] == test_user + test_user

    users = client_library_session.user_management.users()
    assert isinstance(users, list)
    assert test_user in [user["username"] for user in users]

    res = client_library_session.user_management.update_user(
        user_id=test_user_id,
        password_dict=dict(
            old_password=test_password, new_password="new_test_password"
        ),
    )
    assert isinstance(res, dict)
    assert test_user_id == res["id"]
    res = client_library_session.user_management.delete_user(user_id=test_user_id)
    assert res is None

    users = client_library_session.user_management.users()
    assert isinstance(users, list)
    assert test_user not in [user["username"] for user in users]

    with pytest.raises(requests.exceptions.HTTPError):
        client_library_session.user_management.get_user(test_user_id)

    # non existent role should return 400 - Bad request
    with pytest.raises(requests.exceptions.HTTPError) as err:
        client_library_session.user_management.create_user(
            username="user569", pwd=test_password, admin=["non-existent-role"]
        )
    assert err.value.response.status_code == 400
    assert "not of type 'boolean'" in err.value.response.text

    # delete non-existent user
    with pytest.raises(requests.exceptions.HTTPError) as err:
        client_library_session.user_management.delete_user(
            user_id="8ee2051d-3adb-4e76-9e51-ae63238f15bc"
        )
    assert err.value.response.status_code == 404
    assert "User does not exist" in err.value.response.text


def test_password_word_list(cleanup_test_users, client_library_session: ClientLibrary):
    test_user = "another-test-user"
    restricted_password = "password"
    # try to create user with restricted password - must fail
    with pytest.raises(requests.exceptions.HTTPError) as err:
        client_library_session.user_management.create_user(
            username=test_user, pwd=restricted_password
        )
    assert err.value.response.status_code == 403
    assert "password in common word list" in err.value.response.text

    good_pwd = restricted_password + "dfsjdf"
    res = client_library_session.user_management.create_user(
        username=test_user, pwd=good_pwd
    )
    assert isinstance(res, dict)
    assert res["username"] == test_user
    test_user_id = res["id"]

    # try to change password to restricted password - must fail
    with pytest.raises(requests.exceptions.HTTPError) as err:
        client_library_session.user_management.update_user(
            user_id=test_user_id,
            password_dict=dict(old_password=good_pwd, new_password=restricted_password),
        )
    assert err.value.response.status_code == 403
    assert "password in common word list" in err.value.response.text

    res = client_library_session.user_management.delete_user(user_id=test_user_id)
    assert res is None

    with pytest.raises(requests.exceptions.HTTPError):
        client_library_session.user_management.get_user(test_user_id)


def test_user_role_change(
    cleanup_test_labs,
    cleanup_test_users,
    client_config: ClientConfig,
    client_library_session: ClientLibrary,
):
    cl_admin = client_library_session
    cl_admin_uid = client_library_session.user_management.user_id(cl_admin.username)
    # create non admin users
    user1, user2 = "cl_user1", "cl_user2"
    password = "super-secret"
    res = cl_admin.user_management.create_user(username=user1, pwd=password)
    cl_user1_uid = res["id"]
    res = cl_admin.user_management.create_user(username=user2, pwd=password)
    cl_user2_uid = res["id"]

    cl_user1 = ClientLibrary(
        client_config.url,
        username=user1,
        password=password,
        ssl_verify=client_config.ssl_verify,
        allow_http=client_config.allow_http,
    )
    cl_user2 = ClientLibrary(
        client_config.url,
        username=user2,
        password=password,
        ssl_verify=client_config.ssl_verify,
        allow_http=client_config.allow_http,
    )

    lab1 = cl_user1.create_lab("lab1-cl_user1")
    lab2 = cl_user1.create_lab("lab2-cl_user1")

    assert cl_user2.all_labs(show_all=True) == []
    # promote cl_user2 to admin
    cl_admin.user_management.update_user(user_id=cl_user2_uid, admin=True)
    # check if cl_user2 can see both labs as admin
    all_labs = cl_user2.all_labs(show_all=True)
    assert lab1.id in [lab.id for lab in all_labs]
    assert lab2.id in [lab.id for lab in all_labs]
    assert lab1.owner == cl_user1_uid
    assert lab2.owner == cl_user1_uid

    # check if cl_user2 can create user and delete users
    res = cl_user2.user_management.create_user(username="TestUser", pwd=password)
    assert cl_user2.user_management.get_user(user_id=res["id"])

    cl_user2.user_management.delete_user(user_id=res["id"])
    with pytest.raises(requests.exceptions.HTTPError) as err:
        cl_user2.user_management.get_user(user_id=res["id"])
    assert err.value.response.status_code == 404

    # check cl_user2 can see licensing
    assert cl_user2.licensing.status()

    for lab in lab1, lab2:
        cl_user2.remove_lab(lab.id)
        assert lab.id not in [lab.id for lab in cl_user2.all_labs(show_all=True)]

    # promote cl_user1 to admin
    cl_admin.user_management.update_user(user_id=cl_user1_uid, admin=True)

    # check if cl_user1 can remove admin cl_user2
    cl_user1.user_management.delete_user(user_id=cl_user2_uid)
    with pytest.raises(requests.exceptions.HTTPError) as err:
        cl_user1.user_management.get_user(user_id=cl_user2_uid)
    assert err.value.response.status_code == 404

    # remove admin rights from cl_user1
    cl_admin.user_management.update_user(user_id=cl_user1_uid, admin=False)
    lab = cl_admin.create_lab("origin-lab")
    assert cl_user1.all_labs(show_all=True) == []

    with pytest.raises(requests.exceptions.HTTPError) as err:
        cl_user1.user_management.create_user(username="TestUser", pwd=password)
    assert err.value.response.status_code == 403

    with pytest.raises(requests.exceptions.HTTPError) as err:
        cl_user1.licensing.status()
    assert err.value.response.status_code == 403

    cl_admin.user_management.delete_user(user_id=cl_user1_uid)

    # check that user cannot update its own user role
    with pytest.raises(requests.exceptions.HTTPError) as err:
        cl_admin.user_management.update_user(user_id=cl_admin_uid, admin=False)
    assert err.value.response.status_code == 400

    # cleanup
    cl_admin.remove_lab(lab.id)


def test_token_invalidation(
    cleanup_test_users,
    caplog,
    client_config: ClientConfig,
    client_library_session: ClientLibrary,
):
    cl_admin = client_library_session

    res = cl_admin.user_management.create_user(username="test_user", pwd="moremore")
    test_user_uid = res["id"]

    cl_test_user = ClientLibrary(
        client_config.url,
        username="test_user",
        password="moremore",
        ssl_verify=client_config.ssl_verify,
        allow_http=client_config.allow_http,
    )
    # make sure user token works
    res = cl_test_user.user_management.users()
    assert isinstance(res, list)
    for obj in res:
        assert "username" in obj and "id" in obj

    # CHANGE PASSWORD
    new_pwd = "moremoreevenmore"
    res = cl_test_user.user_management.update_user(
        user_id=test_user_uid,
        password_dict=dict(old_password="moremore", new_password=new_pwd),
    )
    assert isinstance(res, dict)
    cl_test_user.password = new_pwd
    with caplog.at_level(logging.WARNING):
        res = cl_test_user.user_management.users()
        assert isinstance(res, list)
    assert "re-auth called on 401 unauthorized" in caplog.text

    # CHANGE ROLE
    res = cl_admin.user_management.update_user(user_id=test_user_uid, admin=True)
    assert isinstance(res, dict)
    assert res["admin"] is True
    with caplog.at_level(logging.WARNING):
        res = cl_test_user.user_management.users()
        assert isinstance(res, list)
    assert "re-auth called on 401 unauthorized" in caplog.text

    # LOGOUT
    res = cl_test_user.logout()
    assert res is True
    with caplog.at_level(logging.WARNING):
        res = cl_test_user.user_management.users()
        assert isinstance(res, list)
    assert "re-auth called on 401 unauthorized" in caplog.text

    # CLEAR SESSION
    # create another client library object (this generates new token)
    cl_test_user1 = ClientLibrary(
        client_config.url,
        username="test_user",
        password=new_pwd,
        ssl_verify=client_config.ssl_verify,
        allow_http=client_config.allow_http,
    )
    # clear whole test_user session (remove all tokens)
    res = cl_test_user.logout(clear_all_sessions=True)
    assert res is True
    # cl_test_user
    with caplog.at_level(logging.WARNING):
        res = cl_test_user.user_management.users()
        assert isinstance(res, list)
    assert "re-auth called on 401 unauthorized" in caplog.text
    # cl_test_user1
    with caplog.at_level(logging.WARNING):
        res = cl_test_user1.user_management.users()
        assert isinstance(res, list)
    assert "re-auth called on 401 unauthorized" in caplog.text

    # DELETE USER
    res = cl_admin.user_management.delete_user(user_id=test_user_uid)
    # test that user token works no more
    with pytest.raises(requests.exceptions.HTTPError) as err:
        with caplog.at_level(logging.WARNING):
            cl_test_user.user_management.users()
            assert isinstance(res, list)
        assert "re-auth called on 401 unauthorized" in caplog.text
    # normally you would expect 401 here, it was returned, however
    # response hook that catches 401 TokenAuth.handle_401_unauthorized
    # tried to authenticate and user no longer exists - so 403 Forbidden
    assert err.value.response.status_code == 403
