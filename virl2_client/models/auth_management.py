#
# This file is part of VIRL 2
# Copyright (c) 2019-2023, Cisco Systems, Inc.
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
from enum import Enum
from typing import Any, Optional

from httpx import Client

from .resource_pools import ResourcePool


class AuthMethod(Enum):
    LOCAL = "local"
    LDAP = "ldap"


_BASE_URL = "system/auth"


class AuthManagement:
    _METHOD_URL = _BASE_URL + "/config"

    def __init__(self, session: Client, auto_sync=True, auto_sync_interval=1.0):
        self.auto_sync = auto_sync
        self.auto_sync_interval = auto_sync_interval
        self._last_sync_time = 0.0
        self._session = session
        self._method = AuthMethod.LOCAL
        self._managers: dict[AuthMethod, Optional[AuthMethodManager]] = {
            AuthMethod("local"): None,
            AuthMethod("ldap"): LDAPManager(self),
        }

    def sync_if_outdated(self) -> None:
        timestamp = time.time()
        if (
            self.auto_sync
            and timestamp - self._last_sync_time > self.auto_sync_interval
        ):
            self.sync()

    def sync(self) -> None:
        settings: dict = self._session.get(self._METHOD_URL).json()
        self._method = AuthMethod(settings.pop("method"))
        self._last_sync_time = time.time()
        # Since right now we also get the other settings along with the method, we
        # might as well save a request and store said settings in the relevant manager
        if (manager := self._managers[self._method]) is not None:
            manager._settings = settings
            manager._last_sync_time = time.time()

    @property
    def method(self) -> AuthMethod:
        self.sync_if_outdated()
        return self._method

    @method.setter
    def method(self, value: AuthMethod | str):
        value = AuthMethod(value)
        self._session.put(self._METHOD_URL, json={"method": value.value})
        self._method = value

    @property
    def manager(self) -> AuthMethodManager:
        """
        The manager for the current auth method.
        """
        # TODO: should we allow users to also configure currently inactive auth methods?
        #  not sure how useful that might or might not be, but if they can then that
        #  changes the answer to the question in AuthMethodManager.update_setting
        self.sync_if_outdated()
        return self._managers[self._method]


class AuthMethodManager:
    _METHOD = ""
    _CONFIG_URL = _BASE_URL + "/config"
    _TEST_URL = _BASE_URL + "/test"

    def __init__(self, auth_management: AuthManagement):
        self._auth_management = auth_management
        self._last_sync_time = 0.0
        self._settings = {}

    def sync_if_outdated(self) -> None:
        timestamp = time.time()
        if (
            self._auth_management.auto_sync
            and timestamp - self._last_sync_time
            > self._auth_management.auto_sync_interval
        ):
            self.sync()

    def sync(self) -> None:
        self._settings = self._get_current_settings()
        self._last_sync_time = time.time()

    @property
    def _session(self) -> Client:
        return self._auth_management._session

    def _get_current_settings(self) -> dict:
        settings = self._session.get(self._CONFIG_URL).json()
        del settings["method"]
        return settings

    def get_setting(self, setting: str) -> Any:
        """
        Returns the value of a specific setting of this authentication method.
        Note: consider using parameters instead.
        """
        self.sync_if_outdated()
        return self._settings[setting]

    def get_settings(self) -> dict:
        """Returns a dictionary of the settings of this authentication method."""
        self.sync_if_outdated()
        return self._settings.copy()

    def _update_setting(self, setting: str, value) -> None:
        """
        Update a setting for this auth method.

        :param setting: the setting to update
        :param value: the value to set the setting to
        """
        if setting == "method":
            raise ValueError(
                f"To set method, use 'AuthManagement.method = {value}' instead."
            )
        # TODO: currently, method is required, so we have to provide it;
        #  do we provide this one or the one that is currently active?
        #  in other words, if method=local and you change an LDAP setting, do we
        #  switch to LDAP or keep local?
        #  we can also provide an argument, so the user can choose, but what would
        #  the default be?
        # also note this should generally not happen;
        # see AuthManagement.method above
        method = self._METHOD
        self._session.put(
            self._CONFIG_URL,
            json={setting: value, "method": method},
        )
        self._auth_management._method = AuthMethod(method)
        if setting in self._settings:
            self._settings[setting] = value

    def update_settings(self, settings_dict: Optional[dict] = None, **kwargs) -> None:
        """
        Update multiple auth settings at once.
        More efficient in batches than setting manager properties.
        If passed a dictionary, reads the dictionary for settings.
        If passed multiple keyword arguments, each is taken as a setting.
        Can mix and match; keywords take precedence.


        Examples::
            am = client.auth_management
            am.update_settings({"method": "ldap", "verify_tls": False})
            am.update_settings(method="ldap", verify_tls=False)
            # "verify_tls" key in dictionary overridden by keyword argument into False
            am.update_settings({"method": "ldap", "verify_tls": True}, verify_tls=False)

        :param settings_dict: a dictionary of settings
        :param kwargs: keywords of settings
        """
        settings = {}
        if settings_dict:
            settings.update(settings_dict)
        settings.update(kwargs)
        if not settings:
            raise TypeError("No settings to update.")
        if settings.get("method", None):
            # TODO: see update_setting above
            raise ValueError("Settings include method.")
        settings["method"] = self._METHOD
        self._session.put(self._CONFIG_URL, json=settings)
        self._auth_management._method = AuthMethod(settings["method"])
        # If we didn't get the setting from the API when syncing, it is write-only,
        # so we don't want to store it; we only update existing keys
        storable_settings = {
            shared_key: settings[shared_key]
            for shared_key in settings.keys() & self._settings.keys()
        }
        self._settings.update(storable_settings)

    def test_auth(self, config: dict, username: str, password: str) -> dict:
        """
        Tests a set of credentials against the specified authentication configuration.

        :param config: a dictionary of authentication settings to test against
            (including manager password)
        :param username: the username to test
        :param password: the password to test
        :returns: results of the test
        """
        body = {
            "auth-config": config,
            "auth-data": {"username": username, "password": password},
        }
        response = self._session.post(self._TEST_URL, json=body)
        return response.json()

    def test_current_auth(
        self, manager_password: str, username: str, password: str
    ) -> dict:
        """
        Tests a set of credentials against the currently applied authentication
        configuration.

        :param manager_password: the auth manager password to allow testing
        :param username: the username to test
        :param password: the password to test
        :returns: results of the test
        """
        current = self.get_settings()
        current["manager_password"] = manager_password
        body = {
            "auth-config": current,
            "auth-data": {"username": username, "password": password},
        }
        response = self._session.post(self._TEST_URL, json=body)
        return response.json()


class LDAPManager(AuthMethodManager):
    _METHOD = "ldap"

    @property
    def server_urls(self) -> str:
        return self.get_setting("server_urls")

    @server_urls.setter
    def server_urls(self, value: str) -> None:
        self._update_setting("server_urls", value)

    @property
    def verify_tls(self) -> bool:
        return self.get_setting("verify_tls")

    @verify_tls.setter
    def verify_tls(self, value: bool) -> None:
        self._update_setting("verify_tls", value)

    @property
    def cert_data_pem(self) -> str:
        return self.get_setting("cert_data_pem")

    @cert_data_pem.setter
    def cert_data_pem(self, value: str) -> None:
        self._update_setting("cert_data_pem", value)

    @property
    def use_ntlm(self) -> bool:
        return self.get_setting("use_ntlm")

    @use_ntlm.setter
    def use_ntlm(self, value: bool) -> None:
        self._update_setting("use_ntlm", value)

    @property
    def root_dn(self) -> str:
        return self.get_setting("root_dn")

    @root_dn.setter
    def root_dn(self, value: str) -> None:
        self._update_setting("root_dn", value)

    @property
    def user_search_base(self) -> str:
        return self.get_setting("user_search_base")

    @user_search_base.setter
    def user_search_base(self, value: str) -> None:
        self._update_setting("user_search_base", value)

    @property
    def user_search_filter(self) -> str:
        return self.get_setting("user_search_filter")

    @user_search_filter.setter
    def user_search_filter(self, value: str) -> None:
        self._update_setting("user_search_filter", value)

    @property
    def admin_search_filter(self) -> str:
        return self.get_setting("admin_search_filter")

    @admin_search_filter.setter
    def admin_search_filter(self, value: str) -> None:
        self._update_setting("admin_search_filter", value)

    @property
    def group_search_base(self) -> str:
        return self.get_setting("group_search_base")

    @group_search_base.setter
    def group_search_base(self, value: str) -> None:
        self._update_setting("group_search_base", value)

    @property
    def group_search_filter(self) -> str:
        return self.get_setting("group_search_filter")

    @group_search_filter.setter
    def group_search_filter(self, value: str) -> None:
        self._update_setting("group_search_filter", value)

    @property
    def group_via_user(self) -> bool:
        return self.get_setting("group_via_user")

    @group_via_user.setter
    def group_via_user(self, value: bool) -> None:
        self._update_setting("group_via_user", value)

    @property
    def group_user_attribute(self) -> str:
        return self.get_setting("group_user_attribute")

    @group_user_attribute.setter
    def group_user_attribute(self, value: str) -> None:
        self._update_setting("group_user_attribute", value)

    @property
    def group_membership_filter(self) -> str:
        return self.get_setting("group_membership_filter")

    @group_membership_filter.setter
    def group_membership_filter(self, value: str) -> None:
        self._update_setting("group_membership_filter", value)

    @property
    def manager_dn(self) -> str:
        return self.get_setting("manager_dn")

    @manager_dn.setter
    def manager_dn(self, value: str) -> None:
        self._update_setting("manager_dn", value)

    def manager_password(self, value: str) -> None:
        self._update_setting("display_attribute", value)

    # manager password can't be retrieved, only set, so we only provide a setter
    manager_password = property(fset=manager_password)

    @property
    def display_attribute(self) -> str:
        return self.get_setting("display_attribute")

    @display_attribute.setter
    def display_attribute(self, value: str) -> None:
        self._update_setting("display_attribute", value)

    @property
    def email_address_attribute(self) -> str:
        return self.get_setting("email_address_attribute")

    @email_address_attribute.setter
    def email_address_attribute(self, value: str) -> None:
        self._update_setting("email_address_attribute", value)

    @property
    def resource_pool(self) -> str:
        return self.get_setting("resource_pool")

    @resource_pool.setter
    def resource_pool(self, value: str | ResourcePool) -> None:
        if isinstance(value, ResourcePool):
            value = value.id
        self._update_setting("resource_pool", value)
