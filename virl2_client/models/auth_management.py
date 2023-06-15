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
from typing import TYPE_CHECKING, Any, Optional

from ..exceptions import MethodNotActive
from .resource_pools import ResourcePool

if TYPE_CHECKING:
    from httpx import Client


_BASE_URL = "system/auth"
_CONFIG_URL = _BASE_URL + "/config"
_TEST_URL = _BASE_URL + "/test"


class AuthManagement:
    def __init__(self, session: Client, auto_sync=True, auto_sync_interval=1.0):
        """
        Sync and modify authentication settings.

        :param session: parent client's httpx.Client object
        :param auto_sync: whether to automatically synchronize resource pools
        :param auto_sync_interval: how often to synchronize resource pools in seconds
        """
        self.auto_sync = auto_sync
        self.auto_sync_interval = auto_sync_interval
        self._last_sync_time = 0.0
        self._session = session
        self._settings = {}
        self._managers = {
            "local": None,
            "ldap": LDAPManager(self),
        }

    def sync_if_outdated(self) -> None:
        timestamp = time.time()
        if (
            self.auto_sync
            and timestamp - self._last_sync_time > self.auto_sync_interval
        ):
            self.sync()

    def sync(self) -> None:
        self._settings = self._session.get(_CONFIG_URL).json()
        self._last_sync_time = time.time()

    @property
    def method(self) -> str:
        """Current authentication method."""
        self.sync_if_outdated()
        return self._settings["method"]

    @property
    def manager(self) -> AuthMethodManager:
        """
        The property manager for the current authentication method.
        """
        self.sync_if_outdated()
        return self._managers[self._settings["method"]]

    def _get_current_settings(self) -> dict:
        return self._session.get(_CONFIG_URL).json()

    def _get_setting(self, setting: str) -> Any:
        """
        Returns the value of a specific setting of the current authentication method.

        Note: consider using parameters instead.
        """
        self.sync_if_outdated()
        return self._settings[setting]

    def get_settings(self) -> dict:
        """Returns a dictionary of the settings of the current authentication method."""
        self.sync_if_outdated()
        return self._settings.copy()

    def _update_setting(self, setting: str, value: Any) -> None:
        """
        Update a setting for the current auth method.

        :param setting: the setting to update
        :param value: the value to set the setting to
        """

        self._session.put(
            _CONFIG_URL,
            json={setting: value, "method": self._settings["method"]},
        )
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
        self._session.put(_CONFIG_URL, json=settings)
        self.sync()

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
        response = self._session.post(_TEST_URL, json=body)
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
        response = self._session.post(_TEST_URL, json=body)
        return response.json()


class AuthMethodManager:
    METHOD = ""

    def __init__(self, auth_management: AuthManagement):
        self._auth_management = auth_management

    def _check_method(self):
        """This makes sure that storing the manager in a variable won't allow the user
        to accidentaly set settings of other methods using this."""
        if self._auth_management._get_setting("method") != self.METHOD:
            raise MethodNotActive(f"{self.METHOD} is not the currently active method.")

    def _get_setting(self, setting: str) -> Any:
        self._check_method()
        return self._auth_management._get_setting(setting)

    def _update_setting(self, setting: str, value: Any) -> None:
        self._check_method()
        self._auth_management._update_setting(setting, value)


class LDAPManager(AuthMethodManager):
    METHOD = "ldap"

    @property
    def server_urls(self) -> str:
        return self._get_setting("server_urls")

    @server_urls.setter
    def server_urls(self, value: str) -> None:
        self._update_setting("server_urls", value)

    @property
    def verify_tls(self) -> bool:
        return self._get_setting("verify_tls")

    @verify_tls.setter
    def verify_tls(self, value: bool) -> None:
        self._update_setting("verify_tls", value)

    @property
    def cert_data_pem(self) -> str:
        return self._get_setting("cert_data_pem")

    @cert_data_pem.setter
    def cert_data_pem(self, value: str) -> None:
        self._update_setting("cert_data_pem", value)

    @property
    def use_ntlm(self) -> bool:
        return self._get_setting("use_ntlm")

    @use_ntlm.setter
    def use_ntlm(self, value: bool) -> None:
        self._update_setting("use_ntlm", value)

    @property
    def root_dn(self) -> str:
        return self._get_setting("root_dn")

    @root_dn.setter
    def root_dn(self, value: str) -> None:
        self._update_setting("root_dn", value)

    @property
    def user_search_base(self) -> str:
        return self._get_setting("user_search_base")

    @user_search_base.setter
    def user_search_base(self, value: str) -> None:
        self._update_setting("user_search_base", value)

    @property
    def user_search_filter(self) -> str:
        return self._get_setting("user_search_filter")

    @user_search_filter.setter
    def user_search_filter(self, value: str) -> None:
        self._update_setting("user_search_filter", value)

    @property
    def admin_search_filter(self) -> str:
        return self._get_setting("admin_search_filter")

    @admin_search_filter.setter
    def admin_search_filter(self, value: str) -> None:
        self._update_setting("admin_search_filter", value)

    @property
    def group_search_base(self) -> str:
        return self._get_setting("group_search_base")

    @group_search_base.setter
    def group_search_base(self, value: str) -> None:
        self._update_setting("group_search_base", value)

    @property
    def group_search_filter(self) -> str:
        return self._get_setting("group_search_filter")

    @group_search_filter.setter
    def group_search_filter(self, value: str) -> None:
        self._update_setting("group_search_filter", value)

    @property
    def group_via_user(self) -> bool:
        return self._get_setting("group_via_user")

    @group_via_user.setter
    def group_via_user(self, value: bool) -> None:
        self._update_setting("group_via_user", value)

    @property
    def group_user_attribute(self) -> str:
        return self._get_setting("group_user_attribute")

    @group_user_attribute.setter
    def group_user_attribute(self, value: str) -> None:
        self._update_setting("group_user_attribute", value)

    @property
    def group_membership_filter(self) -> str:
        return self._get_setting("group_membership_filter")

    @group_membership_filter.setter
    def group_membership_filter(self, value: str) -> None:
        self._update_setting("group_membership_filter", value)

    @property
    def manager_dn(self) -> str:
        return self._get_setting("manager_dn")

    @manager_dn.setter
    def manager_dn(self, value: str) -> None:
        self._update_setting("manager_dn", value)

    def manager_password(self, value: str) -> None:
        self._update_setting("display_attribute", value)

    # manager password can't be retrieved, only set, so we only provide a setter
    manager_password = property(fset=manager_password)

    @property
    def display_attribute(self) -> str:
        return self._get_setting("display_attribute")

    @display_attribute.setter
    def display_attribute(self, value: str) -> None:
        self._update_setting("display_attribute", value)

    @property
    def email_address_attribute(self) -> str:
        return self._get_setting("email_address_attribute")

    @email_address_attribute.setter
    def email_address_attribute(self, value: str) -> None:
        self._update_setting("email_address_attribute", value)

    @property
    def resource_pool(self) -> str:
        return self._get_setting("resource_pool")

    @resource_pool.setter
    def resource_pool(self, value: str | ResourcePool) -> None:
        if isinstance(value, ResourcePool):
            value = value.id
        self._update_setting("resource_pool", value)
