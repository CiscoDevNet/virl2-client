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

"""Tests for User Management."""

import pytest
import logging
import requests

from virl2_client import ClientConfig, ClientLibrary, InitializationError

pytestmark = [pytest.mark.integration]

test_username = "integration_test_user"
test_password = "test_password"
test_password_new = "test_password_new"
test_username2 = "integration_test_user2"
test_lab_title = "integration_test_lab_users"
weak_password = "cml2cml"  # At least 8 characters
restricted_password = "password"


def verify_nonadmin_role(session_admin: ClientLibrary, session_user: ClientLibrary):
    """
    Make sure the provided user session cannot access licensing status,
    cannot see unowned labs and cannot modify users/groups.

    :param session_admin: Client session with admin user
    :param session_user: Client session with tested user
    :type session_admin: ClientLibrary
    :type session_user: ClientLibrary
    raises AssertionError: If the user is allowed to perform an admin-only operation.
    """
    # Fails to get licensing status
    with pytest.raises(requests.exceptions.HTTPError) as err:
        session_user.licensing.status()
    assert err.value.response.status_code == 403

    # Fails to create another user
    with pytest.raises(requests.exceptions.HTTPError) as err:
        session_user.user_management.create_user(
            username=test_username2, pwd=test_password, admin=False
        )
    assert err.value.response.status_code == 403

    # Fails to create a group
    with pytest.raises(requests.exceptions.HTTPError) as err:
        session_user.group_management.create_group(name="testgroup")
    assert err.value.response.status_code == 403

    # Does not see lab owned by another user
    lab = session_admin.create_lab(title=test_lab_title)
    assert lab.id not in session_user.get_lab_list(show_all=True)
    # Cleanup the lab
    session_admin.remove_lab(lab.id)


def verify_token_invalidation(caplog, session: ClientLibrary):
    """
    Make some request with the session, expect 401 and re-auth.

    :param caplog: Pytest builtin log capture fixture.
    :param session: Client library session.
    :type caplog: _pytest.logging.caplog
    :type session: ClientLibrary
    :raises AssertionError: If session token is valid.
    """
    with caplog.at_level(logging.WARNING):
        res = session.user_management.users()
        assert isinstance(res, list)
    assert "re-auth called on 401 unauthorized" in caplog.text


def test_create_user_admin(
    cleanup_test_users,
    client_config: ClientConfig,
    client_library_session: ClientLibrary,
):
    """Create a valid user and verify."""

    user = client_library_session.user_management.create_user(
        username=test_username, pwd=test_password
    )
    assert isinstance(user, dict)
    assert user["username"] == test_username
    assert user["fullname"] == ""
    assert user["description"] == ""

    users = client_library_session.user_management.users()
    assert user in users

    # Try logging in as the new user
    ClientLibrary(
        client_config.url,
        username=test_username,
        password=test_password,
        ssl_verify=client_config.ssl_verify,
        allow_http=client_config.allow_http,
        raise_for_auth_failure=True,
    )


def test_create_user_nonadmin(
    cleanup_test_labs,
    cleanup_test_users,
    cleanup_test_groups,
    client_config: ClientConfig,
    client_library_session: ClientLibrary,
):
    """Create a non-admin user, verify he cannot access licensing and unowned labs, cannot modify users or groups."""

    client_library_session.user_management.create_user(
        username=test_username, pwd=test_password, admin=False
    )

    session1 = ClientLibrary(
        client_config.url,
        username=test_username,
        password=test_password,
        ssl_verify=client_config.ssl_verify,
        allow_http=client_config.allow_http,
        raise_for_auth_failure=True,
    )
    verify_nonadmin_role(client_library_session, session1)


def test_create_user_duplicate(
    cleanup_test_users, client_library_session: ClientLibrary
):
    """Try to create the same user twice, expect to fail."""

    client_library_session.user_management.create_user(
        username=test_username, pwd=test_password, admin=False
    )
    with pytest.raises(requests.exceptions.HTTPError) as err:
        client_library_session.user_management.create_user(
            username=test_username, pwd=test_password, admin=False
        )
    assert err.value.response.status_code == 422


def test_modify_user_password(
    cleanup_test_users,
    client_config: ClientConfig,
    client_library_session: ClientLibrary,
):
    """Create a user, modify his password and verify."""

    user = client_library_session.user_management.create_user(
        username=test_username, pwd=test_password
    )
    test_user_id = user["id"]

    response = client_library_session.user_management.update_user(
        user_id=test_user_id,
        password_dict=dict(old_password=test_password, new_password=test_password_new),
    )
    assert isinstance(response, dict)
    assert test_user_id == response["id"]

    # Try logging in with the new password
    session1 = ClientLibrary(
        client_config.url,
        username=test_username,
        password=test_password_new,
        ssl_verify=client_config.ssl_verify,
        allow_http=client_config.allow_http,
        raise_for_auth_failure=True,
    )

    # Fail to login with the old password
    with pytest.raises(InitializationError) as err:
        ClientLibrary(
            client_config.url,
            username=test_username,
            password=test_password,
            ssl_verify=client_config.ssl_verify,
            allow_http=client_config.allow_http,
            raise_for_auth_failure=True,
        )
    err.match("Unable to authenticate, please check your username and password")


def test_modify_own_password(
    cleanup_test_users,
    client_config: ClientConfig,
    client_library_session: ClientLibrary,
):
    """Create a user, have him modify his own password and verify."""

    user = client_library_session.user_management.create_user(
        username=test_username, pwd=test_password
    )
    test_user_id = user["id"]

    session1 = ClientLibrary(
        client_config.url,
        username=test_username,
        password=test_password,
        ssl_verify=client_config.ssl_verify,
        allow_http=client_config.allow_http,
        raise_for_auth_failure=True,
    )

    session1.user_management.update_user(
        user_id=test_user_id,
        password_dict=dict(old_password=test_password, new_password=test_password_new),
    )

    # Try logging in with the new password
    ClientLibrary(
        client_config.url,
        username=test_username,
        password=test_password_new,
        ssl_verify=client_config.ssl_verify,
        allow_http=client_config.allow_http,
        raise_for_auth_failure=True,
    )

    # Fail to login with the old password
    with pytest.raises(InitializationError) as err:
        ClientLibrary(
            client_config.url,
            username=test_username,
            password=test_password,
            ssl_verify=client_config.ssl_verify,
            allow_http=client_config.allow_http,
            raise_for_auth_failure=True,
        )
    err.match("Unable to authenticate, please check your username and password")


def test_delete_user(
    cleanup_test_users,
    client_config: ClientConfig,
    client_library_session: ClientLibrary,
):
    """Create an user, delete the user, verify he cannot login and disappears from users list."""

    user = client_library_session.user_management.create_user(
        username=test_username, pwd=test_password, admin=False
    )
    test_user_id = user["id"]

    client_library_session.user_management.delete_user(user_id=test_user_id)

    users = client_library_session.user_management.users()
    assert test_user_id not in users


def test_delete_non_existent_user(client_library_session: ClientLibrary):
    """Try to delete an user which does not exist, expect to fail."""

    with pytest.raises(requests.exceptions.HTTPError) as err:
        client_library_session.user_management.delete_user(
            "7bfc49f1-081a-4fc7-b0c6-51002fbd4f6b"
        )
    assert err.value.response.status_code == 404


def test_modify_user_role_to_admin(
    cleanup_test_labs,
    cleanup_test_users,
    cleanup_test_groups,
    client_config: ClientConfig,
    client_library_session: ClientLibrary,
):
    """Create a non-admin user, give him admin rights and verify."""

    user = client_library_session.user_management.create_user(
        username=test_username, pwd=test_password, admin=False
    )
    test_user_id = user["id"]

    client_library_session.user_management.update_user(user_id=test_user_id, admin=True)

    session1 = ClientLibrary(
        client_config.url,
        username=test_username,
        password=test_password,
        ssl_verify=client_config.ssl_verify,
        allow_http=client_config.allow_http,
        raise_for_auth_failure=True,
    )
    # Try getting licensing status, shouldn't fail for admin user
    session1.licensing.status()


def test_modify_user_role_to_nonadmin(
    cleanup_test_labs,
    cleanup_test_users,
    client_config: ClientConfig,
    client_library_session: ClientLibrary,
):
    """Create an admin user, remove his admin rights and verify."""

    user = client_library_session.user_management.create_user(
        username=test_username, pwd=test_password, admin=True
    )
    test_user_id = user["id"]

    client_library_session.user_management.update_user(
        user_id=test_user_id, admin=False
    )

    session1 = ClientLibrary(
        client_config.url,
        username=test_username,
        password=test_password,
        ssl_verify=client_config.ssl_verify,
        allow_http=client_config.allow_http,
        raise_for_auth_failure=True,
    )
    verify_nonadmin_role(client_library_session, session1)


def test_create_user_with_invalid_role(client_library_session: ClientLibrary):
    """Create a user with a non-existent role and expect to fail."""

    with pytest.raises(requests.exceptions.HTTPError) as err:
        user = client_library_session.user_management.create_user(
            username=test_username, pwd=test_password, admin="non-existent-role"
        )
    assert err.value.response.status_code == 400


def test_modify_user_role_to_invalid(
    cleanup_test_users, client_library_session: ClientLibrary
):
    """Create an admin user, change his role to a non-existent one and expect to fail."""

    user = client_library_session.user_management.create_user(
        username=test_username, pwd=test_password, admin=True
    )
    test_user_id = user["id"]

    with pytest.raises(requests.exceptions.HTTPError) as err:
        client_library_session.user_management.update_user(
            user_id=test_user_id, admin=["non-existent-role"]
        )
    assert err.value.response.status_code == 400


def test_modify_user_fullname_description(
    cleanup_test_users, client_library_session: ClientLibrary
):
    """Create an user, modify his fullname, description and verify."""
    user = client_library_session.user_management.create_user(
        username=test_username, pwd=test_password, admin=True
    )
    test_user_id = user["id"]

    # change fullname
    res = client_library_session.user_management.update_user(
        user_id=test_user_id, fullname=test_username, admin=True
    )
    assert res["fullname"] == test_username
    assert res["description"] == ""

    # change description
    res = client_library_session.user_management.update_user(
        user_id=test_user_id, description=test_username
    )
    assert res["fullname"] == test_username
    assert res["description"] == test_username

    # change both
    res = client_library_session.user_management.update_user(
        user_id=test_user_id,
        description=test_username + test_username,
        fullname=test_username + test_username,
    )
    assert res["fullname"] == test_username + test_username
    assert res["description"] == test_username + test_username

    # verify
    user = client_library_session.user_management.get_user(test_user_id)
    assert isinstance(user, dict)
    assert user["username"] == test_username
    assert "admin" in user and "groups" in user
    assert res["fullname"] == test_username + test_username
    assert res["description"] == test_username + test_username


def test_create_user_weak_password(
    cleanup_test_users, client_library_session: ClientLibrary
):
    """Try to create a new user with a weak password, expect to fail."""

    with pytest.raises(requests.exceptions.HTTPError) as err:
        client_library_session.user_management.create_user(
            username=test_username, pwd=weak_password
        )
    assert err.value.response.status_code == 403
    assert "Password validation failure! Reason: Length" in err.value.response.text


def test_create_user_wordlist_password(
    cleanup_test_users, client_library_session: ClientLibrary
):
    """Try to create a new user with a restricted password, expect to fail."""

    with pytest.raises(requests.exceptions.HTTPError) as err:
        client_library_session.user_management.create_user(
            username=test_username, pwd=restricted_password
        )
    assert err.value.response.status_code == 403
    assert (
        "Password validation failure! Reason: password in common word list"
        in err.value.response.text
    )


def test_change_password_weak(
    cleanup_test_users, client_library_session: ClientLibrary
):
    """Create a user, try to change his password to a weak one and expect to fail."""

    user = client_library_session.user_management.create_user(
        username=test_username, pwd=test_password
    )
    test_user_id = user["id"]

    with pytest.raises(requests.exceptions.HTTPError) as err:
        response = client_library_session.user_management.update_user(
            user_id=test_user_id,
            password_dict=dict(old_password=test_password, new_password=weak_password),
        )
    assert err.value.response.status_code == 403
    assert "Password validation failure! Reason: Length" in err.value.response.text


def test_change_password_wordlist(
    cleanup_test_users, client_library_session: ClientLibrary
):
    """Create a user, try to change his password to a restricted one and expect to fail."""

    user = client_library_session.user_management.create_user(
        username=test_username, pwd=test_password
    )
    test_user_id = user["id"]

    with pytest.raises(requests.exceptions.HTTPError) as err:
        response = client_library_session.user_management.update_user(
            user_id=test_user_id,
            password_dict=dict(
                old_password=test_password, new_password=restricted_password
            ),
        )
    assert err.value.response.status_code == 403
    assert (
        "Password validation failure! Reason: password in common word list"
        in err.value.response.text
    )


def test_token_invalidation_password_change(
    cleanup_test_users,
    caplog,
    client_config: ClientConfig,
    client_library_session: ClientLibrary,
):
    """Create a user, login, change the user's password and verify his token expired."""

    user = client_library_session.user_management.create_user(
        username=test_username, pwd=test_password
    )
    test_user_id = user["id"]
    session1 = ClientLibrary(
        client_config.url,
        username=test_username,
        password=test_password,
        ssl_verify=client_config.ssl_verify,
        allow_http=client_config.allow_http,
        raise_for_auth_failure=True,
    )
    client_library_session.user_management.update_user(
        user_id=test_user_id,
        password_dict=dict(old_password=test_password, new_password=test_password_new),
    )
    session1.password = test_password_new

    verify_token_invalidation(caplog, session1)


def test_token_invalidation_role_change(
    cleanup_test_users,
    caplog,
    client_config: ClientConfig,
    client_library_session: ClientLibrary,
):
    """Create a user, login, change the user's role and verify his token expired."""

    user = client_library_session.user_management.create_user(
        username=test_username, pwd=test_password, admin=False
    )
    test_user_id = user["id"]
    session1 = ClientLibrary(
        client_config.url,
        username=test_username,
        password=test_password,
        ssl_verify=client_config.ssl_verify,
        allow_http=client_config.allow_http,
        raise_for_auth_failure=True,
    )
    client_library_session.user_management.update_user(
        user_id=test_user_id,
        admin=True,
    )

    verify_token_invalidation(caplog, session1)


def test_token_invalidation_logout(
    cleanup_test_users,
    caplog,
    client_config: ClientConfig,
    client_library_session: ClientLibrary,
):
    """Create a user, login, logout and verify the session token expires."""

    user = client_library_session.user_management.create_user(
        username=test_username, pwd=test_password, admin=False
    )
    test_user_id = user["id"]
    session1 = ClientLibrary(
        client_config.url,
        username=test_username,
        password=test_password,
        ssl_verify=client_config.ssl_verify,
        allow_http=client_config.allow_http,
    )
    session1.logout()

    verify_token_invalidation(caplog, session1)


def test_token_invalidation_logout_all_sessions(
    cleanup_test_users,
    caplog,
    client_config: ClientConfig,
    client_library_session: ClientLibrary,
):
    """Create a user, login in two sessions, logout one session with Clear All Sessions,
    verify both tokens expired."""

    client_library_session.user_management.create_user(
        username=test_username, pwd=test_password, admin=False
    )

    session1 = ClientLibrary(
        client_config.url,
        username=test_username,
        password=test_password,
        ssl_verify=client_config.ssl_verify,
        allow_http=client_config.allow_http,
    )
    session2 = ClientLibrary(
        client_config.url,
        username=test_username,
        password=test_password,
        ssl_verify=client_config.ssl_verify,
        allow_http=client_config.allow_http,
    )
    session1.logout(clear_all_sessions=True)

    for session in session1, session2:
        verify_token_invalidation(caplog, session)


def test_token_invalidation_user_deletion(
    cleanup_test_users,
    caplog,
    client_config: ClientConfig,
    client_library_session: ClientLibrary,
):
    """Create a user, login, delete the user, then verify the session token expired."""

    user = client_library_session.user_management.create_user(
        username=test_username, pwd=test_password, admin=False
    )
    user_id = user["id"]

    session1 = ClientLibrary(
        client_config.url,
        username=test_username,
        password=test_password,
        ssl_verify=client_config.ssl_verify,
        allow_http=client_config.allow_http,
    )
    client_library_session.user_management.delete_user(user_id)

    with pytest.raises(requests.exceptions.HTTPError) as err:
        session1.user_management.users()
    # Client catches 401 and tries to re-auth, but the user no longer exists
    assert err.value.response.status_code == 403


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
