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

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from virl2_client.exceptions import MethodNotActive
from virl2_client.models.auth_management import (
    AuthManagement,
    LDAPManager,
    RADIUSManager,
)
from virl2_client.models.resource_pool import ResourcePool


def make_auth_management(settings: dict) -> tuple[AuthManagement, MagicMock]:
    """Create AuthManagement instance with mocked session and given settings.

    :param settings: Auth configuration dict (method, ldap/radius settings).
    :returns: Tuple of (AuthManagement, mocked session).
    """
    session = MagicMock()
    auth_management = AuthManagement(session, auto_sync=False)
    auth_management._settings = settings.copy()
    return auth_management, session


@pytest.mark.parametrize(
    ("method", "manager_cls"),
    [
        ("ldap", LDAPManager),
        ("radius", RADIUSManager),
    ],
)
def test_manager_returns_expected_manager(
    method: str, manager_cls: type[LDAPManager] | type[RADIUSManager]
) -> None:
    """Manager property returns LDAPManager or RADIUSManager based on method.

    :param method: Auth method ("ldap" or "radius").
    :param manager_cls: Expected manager class.
    """
    auth_management, _ = make_auth_management({"method": method})

    assert isinstance(auth_management.manager, manager_cls)


def test_update_settings_no_args_raises() -> None:
    """update_settings with no args raises TypeError."""
    auth_management, _ = make_auth_management({"method": "ldap"})

    with pytest.raises(TypeError, match="No settings to update"):
        auth_management.update_settings()


def test_sync_updates_settings_and_timestamp() -> None:
    """Sync fetches config from server and updates _last_sync_time."""
    auth_management, session = make_auth_management({"method": "ldap"})
    session.get.return_value.json.return_value = {"method": "local"}

    before = time.time()
    auth_management.sync()
    after = time.time()

    assert auth_management._settings == {"method": "local"}
    assert before <= auth_management._last_sync_time <= after
    session.get.assert_called_once_with("system/auth/config")


@pytest.mark.parametrize("search_filter", [None, "(cn=admins)"])
def test_get_ldap_groups(search_filter: str | None) -> None:
    """get_ldap_groups returns groups, optionally filtered.

    :param search_filter: Optional LDAP filter string.
    """
    auth_management, session = make_auth_management({"method": "ldap"})
    session.get.return_value.json.return_value = ["group-1", "group-2"]

    response = auth_management.get_ldap_groups(search_filter=search_filter)

    assert response == ["group-1", "group-2"]
    if search_filter is None:
        session.get.assert_called_once_with("system/auth/groups", params=None)
    else:
        session.get.assert_called_once_with(
            "system/auth/groups", params={"filter": search_filter}
        )


def test_refresh_ldap_groups() -> None:
    """refresh_ldap_groups sends PUT to system/auth/refresh."""
    auth_management, session = make_auth_management({"method": "ldap"})

    auth_management.refresh_ldap_groups()

    session.put.assert_called_once_with("system/auth/refresh")


def test_auth_with_user_credentials() -> None:
    """test_auth with username/password sends auth-data in request."""
    auth_management, session = make_auth_management({"method": "ldap"})
    session.post.return_value.json.return_value = {"auth_ok": True}

    response = auth_management.test_auth(
        config={"method": "ldap"}, username="user", password="pa$$"
    )

    assert response == {"auth_ok": True}
    session.post.assert_called_once_with(
        "system/auth/test",
        json={
            "auth-config": {"method": "ldap"},
            "auth-data": {"username": "user", "password": "pa$$"},
        },
    )


def test_auth_with_group_name() -> None:
    """test_auth with group_name sends group-data in request."""
    auth_management, session = make_auth_management({"method": "ldap"})
    session.post.return_value.json.return_value = {"auth_ok": True}

    response = auth_management.test_auth(
        config={"method": "ldap"}, group_name="cmladmins"
    )

    assert response == {"auth_ok": True}
    session.post.assert_called_once_with(
        "system/auth/test",
        json={
            "auth-config": {"method": "ldap"},
            "group-data": {"group_name": "cmladmins"},
        },
    )


def test_current_auth_includes_manager_password() -> None:
    """test_current_auth includes manager_password in auth-config."""
    auth_management, session = make_auth_management(
        {"method": "ldap", "verify_tls": True}
    )
    session.post.return_value.json.return_value = {"auth_ok": True}

    response = auth_management.test_current_auth(
        manager_password="secret", username="user", password="pa$$"
    )

    assert response == {"auth_ok": True}
    session.post.assert_called_once_with(
        "system/auth/test",
        json={
            "auth-config": {
                "method": "ldap",
                "verify_tls": True,
                "manager_password": "secret",
            },
            "auth-data": {"username": "user", "password": "pa$$"},
        },
    )


@pytest.mark.parametrize(
    "setting,value",
    [
        ("admin_search_filter", "(&(uid={0})(memberOf=cn=admins,dc=corp,dc=com))"),
        (
            "cert_data_pem",
            "-----BEGIN CERTIFICATE-----\nMIIB\n-----END CERTIFICATE-----",
        ),
        ("display_attribute", "displayName"),
        ("email_address_attribute", "mail"),
        ("group_display_attribute", "description"),
        ("group_membership_filter", "(member={0})"),
        ("group_search_base", "cn=groups,dc=corp,dc=com"),
        ("group_search_filter", "(&(cn={0})(objectClass=groupOfNames))"),
        ("group_user_attribute", "memberOf"),
        ("group_via_user", True),
        ("manager_dn", "uid=manager,cn=users,dc=corp,dc=com"),
        ("resource_pool", "pool-id"),
        ("root_dn", "dc=corp,dc=com"),
        ("server_urls", "ldaps://ad.corp.com:3269"),
        ("timeout", 10.0),
        ("use_ntlm", True),
        ("user_search_base", "cn=users,dc=corp,dc=com"),
        ("user_search_filter", "(&(uid={0})(objectClass=person))"),
        ("verify_tls", False),
    ],
)
def test_ldap_settings_update(setting: str, value: str | bool | float) -> None:
    """LDAP manager setter PATCHes config with setting and value.

    :param setting: LDAP setting name.
    :param value: Value to set.
    """
    auth_management, session = make_auth_management({"method": "ldap", setting: value})
    manager = auth_management._managers["ldap"]

    setattr(manager, setting, value)

    session.patch.assert_called_once_with(
        "system/auth/config", json={setting: value, "method": "ldap"}
    )
    assert auth_management._settings[setting] == value


def test_ldap_timeout_inactive_method_raises() -> None:
    """Accessing LDAP timeout when method is local raises MethodNotActive.

    :raises MethodNotActive: When LDAP is not the active auth method.
    """
    auth_management, _ = make_auth_management({"method": "local", "timeout": 5})

    with pytest.raises(MethodNotActive):
        _ = auth_management._managers["ldap"].timeout


def test_ldap_resource_pool_accepts_instance() -> None:
    """LDAP resource_pool setter accepts ResourcePool instance, uses its id."""
    auth_management, session = make_auth_management(
        {"method": "ldap", "resource_pool": "old"}
    )
    manager = auth_management._managers["ldap"]
    resource_pool = ResourcePool(
        MagicMock(_session=MagicMock()),
        "pool-123",
        "label",
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
    )

    manager.resource_pool = resource_pool

    session.patch.assert_called_once_with(
        "system/auth/config", json={"resource_pool": "pool-123", "method": "ldap"}
    )
    assert auth_management._settings["resource_pool"] == "pool-123"


@pytest.mark.parametrize(
    "setting,value",
    [
        ("server_hosts", "radius-1 radius-2:1813"),
        ("port", 1813),
        ("timeout", 7.5),
        ("nas_identifier", "cml-01"),
        ("resource_pool", "pool-id"),
    ],
)
def test_radius_settings_update(setting: str, value: str | int | float) -> None:
    """RADIUS manager setter PATCHes config with setting and value.

    :param setting: RADIUS setting name.
    :param value: Value to set.
    """
    auth_management, session = make_auth_management(
        {"method": "radius", setting: value}
    )
    manager = auth_management._managers["radius"]

    setattr(manager, setting, value)

    session.patch.assert_called_once_with(
        "system/auth/config", json={setting: value, "method": "radius"}
    )
    assert auth_management._settings[setting] == value


def test_radius_secret_setter_updates_setting() -> None:
    """RADIUS secret setter PATCHes config."""
    auth_management, session = make_auth_management({"method": "radius"})
    manager = auth_management._managers["radius"]

    manager.secret = "secret"

    session.patch.assert_called_once_with(
        "system/auth/config", json={"secret": "secret", "method": "radius"}
    )


def test_radius_timeout_inactive_method_raises() -> None:
    """Accessing RADIUS timeout when method is local raises MethodNotActive.

    :raises MethodNotActive: When RADIUS is not the active auth method.
    """
    auth_management, _ = make_auth_management({"method": "local", "timeout": 5})

    with pytest.raises(MethodNotActive):
        _ = auth_management._managers["radius"].timeout


def test_radius_resource_pool_accepts_instance() -> None:
    """RADIUS resource_pool setter accepts ResourcePool instance, uses its id."""
    auth_management, session = make_auth_management(
        {"method": "radius", "resource_pool": "old"}
    )
    manager = auth_management._managers["radius"]
    resource_pool = ResourcePool(
        MagicMock(_session=MagicMock()),
        "pool-456",
        "label",
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
    )

    manager.resource_pool = resource_pool

    session.patch.assert_called_once_with(
        "system/auth/config", json={"resource_pool": "pool-456", "method": "radius"}
    )
    assert auth_management._settings["resource_pool"] == "pool-456"


def test_ldap_manager_password_setter_updates() -> None:
    """LDAP manager_password setter PATCHes config."""
    auth_management, session = make_auth_management({"method": "ldap"})
    manager = auth_management._managers["ldap"]

    manager.manager_password = "secret"

    session.patch.assert_called_once_with(
        "system/auth/config", json={"manager_password": "secret", "method": "ldap"}
    )


def test_update_settings_precedence_and_sync() -> None:
    """Keyword args override dict args; sync fetches updated config."""
    auth_management, session = make_auth_management({"method": "ldap"})
    session.get.return_value.json.return_value = {"method": "ldap", "verify_tls": False}

    auth_management.update_settings({"verify_tls": True}, verify_tls=False)

    session.patch.assert_called_once_with(
        "system/auth/config", json={"verify_tls": False}
    )
    session.get.assert_called_once_with("system/auth/config")
    assert auth_management._settings["verify_tls"] is False


def test_sync_if_outdated_triggers_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    """sync_if_outdated triggers sync when interval exceeded.

    :param monkeypatch: Pytest monkeypatch fixture.
    """
    auth_management, session = make_auth_management({"method": "ldap"})
    session.get.return_value.json.return_value = {"method": "ldap"}
    auth_management.auto_sync = True
    auth_management.auto_sync_interval = 10.0
    auth_management._last_sync_time = 0.0

    monkeypatch.setattr(time, "time", lambda: 20.0)

    auth_management.sync_if_outdated()

    session.get.assert_called_once_with("system/auth/config")


def test_sync_if_outdated_skips_when_recent(monkeypatch: pytest.MonkeyPatch) -> None:
    """sync_if_outdated skips sync when within interval.

    :param monkeypatch: Pytest monkeypatch fixture.
    """
    auth_management, session = make_auth_management({"method": "ldap"})
    auth_management.auto_sync = True
    auth_management.auto_sync_interval = 10.0
    auth_management._last_sync_time = 15.0

    monkeypatch.setattr(time, "time", lambda: 20.0)

    auth_management.sync_if_outdated()

    session.get.assert_not_called()


def test_accessing_wrong_manager_raises() -> None:
    """Accessing RADIUS manager when LDAP is active raises MethodNotActive.

    :raises MethodNotActive: When the requested manager is not active.
    """
    auth_management, _ = make_auth_management({"method": "ldap"})

    with pytest.raises(MethodNotActive):
        _ = auth_management._managers["radius"].timeout
