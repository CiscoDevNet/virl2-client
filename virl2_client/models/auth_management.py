#
# This file is part of VIRL 2
# Copyright (c) 2019-2025, Cisco Systems, Inc.
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
from typing import TYPE_CHECKING, Any

from ..exceptions import MethodNotActive
from ..utils import get_url_from_template
from .resource_pool import ResourcePool

if TYPE_CHECKING:
    from httpx import Client


class AuthManagement:
    _URL_TEMPLATES = {
        "config": "system/auth/config",
        "test": "system/auth/test",
        "groups": "system/auth/groups",
        "refresh": "system/auth/refresh",
    }

    def __init__(self, session: Client, auto_sync=True, auto_sync_interval=1.0):
        """
        Manage authentication settings and synchronization.

        :param session: The httpx-based HTTP client for this session with the server.
        :param auto_sync: Whether to automatically synchronize resource pools.
        :param auto_sync_interval: How often to synchronize resource pools in seconds.
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

    def _url_for(self, endpoint, **kwargs):
        """
        Generate the URL for a given API endpoint.

        :param endpoint: The desired endpoint.
        :param **kwargs: Keyword arguments used to format the URL.
        :returns: The formatted URL.
        """
        return get_url_from_template(endpoint, self._URL_TEMPLATES, kwargs)

    def sync_if_outdated(self) -> None:
        """
        Synchronize local data with the server if the auto sync interval
        has elapsed since the last synchronization.
        """
        timestamp = time.time()
        if (
            self.auto_sync
            and timestamp - self._last_sync_time > self.auto_sync_interval
        ):
            self.sync()

    def sync(self) -> None:
        """Synchronize the authentication settings with the server."""
        url = self._url_for("config")
        self._settings = self._session.get(url).json()
        self._last_sync_time = time.time()

    @property
    def method(self) -> str:
        """Return the current authentication method."""
        self.sync_if_outdated()
        return self._settings["method"]

    @method.setter
    def method(self, value):
        """Set the authentication method."""
        self.update_settings({"method": value})

    @property
    def manager(self) -> AuthMethodManager:
        """Return the property manager for the current authentication method."""
        self.sync_if_outdated()
        return self._managers[self._settings["method"]]

    def _get_current_settings(self) -> dict:
        """
        Get the current authentication settings.

        :returns: The current authentication settings.
        """
        url = self._url_for("config")
        return self._session.get(url).json()

    def _get_setting(self, setting: str) -> Any:
        """
        Get the value of a specific setting of the current authentication method.

        :param setting: The setting to retrieve.
        :returns: The value of the specified setting.
        """
        self.sync_if_outdated()
        return self._settings[setting]

    def get_settings(self) -> dict:
        """
        Get a dictionary of the settings of the current authentication method.

        :returns: A dictionary of the settings of the current authentication method.
        """
        self.sync_if_outdated()
        return self._settings.copy()

    def _update_setting(self, setting: str, value: Any) -> None:
        """
        Update a setting for the current authentication method.

        :param setting: The setting to update.
        :param value: The value to set the setting to.
        """
        url = self._url_for("config")
        settings = {setting: value, "method": self._settings["method"]}
        self._session.patch(url, json=settings)
        if setting in self._settings:
            self._settings[setting] = value

    def update_settings(self, settings_dict: dict | None = None, **kwargs) -> None:
        """
        Update multiple authentication settings at once.

        This method is more efficient in batches than setting manager properties.

        If passed a dictionary, it reads the dictionary for settings.
        If passed multiple keyword arguments, each is taken as a setting.
        Can mix and match; keywords take precedence.


        Examples::
            am = client.auth_management
            am.update_settings({"method": "ldap", "verify_tls": False})
            am.update_settings(method="ldap", verify_tls=False)
            # "verify_tls" key in dictionary overridden by keyword argument into False
            am.update_settings({"method": "ldap", "verify_tls": True}, verify_tls=False)

        :param settings_dict: A dictionary of settings.
        :param kwargs: Setting keywords.
        """
        settings = {}
        if settings_dict:
            settings.update(settings_dict)
        settings.update(kwargs)
        if not settings:
            raise TypeError("No settings to update.")
        url = self._url_for("config")
        self._session.patch(url, json=settings)
        self.sync()

    def get_ldap_groups(self, search_filter=None):
        """
        Get CNs of groups available on the LDAP server, optionally filtered
        by supplied filter.

        :param search_filter: An optional filter applied to the search.
        :returns: A list of CNs of found groups.
        """
        params = {"filter": search_filter} if search_filter else None
        url = self._url_for("groups")
        response = self._session.get(url, params=params)
        return response.json()

    def refresh_ldap_groups(self):
        """
        Refresh the members of LDAP groups. Removes any users from the group that are
        not LDAP users or not a part of said group on LDAP, and adds any users that
        are LDAP users and are a part of said group on LDAP.
        """
        url = self._url_for("refresh")
        self._session.put(url)

    @staticmethod
    def _get_auth(
        username: str | None = None,
        password: str | None = None,
        group_name: str | None = None,
    ) -> dict:
        result = {}
        if username is not None and password is not None:
            result["auth-data"] = {"username": username, "password": password}
        if group_name is not None:
            result["group-data"] = {"group_name": group_name}
        return result

    def test_auth(
        self,
        config: dict,
        username: str | None = None,
        password: str | None = None,
        group_name: str | None = None,
    ) -> dict:
        """
        Test a set of credentials and/or group against the specified authentication
        configuration.

        :param config: A dictionary of authentication settings to test against
            (including manager password).
        :param username: The username to test.
        :param password: The password to test.
        :param group_name: The group name to test.
        :returns: Results of the test.
        """
        body = {"auth-config": config} | self._get_auth(username, password, group_name)
        url = self._url_for("test")
        response = self._session.post(url, json=body)
        return response.json()

    def test_current_auth(
        self,
        manager_password: str,
        username: str | None = None,
        password: str | None = None,
        group_name: str | None = None,
    ) -> dict:
        """
        Test a set of credentials and/or group against the currently applied
        authentication configuration.

        :param manager_password: The manager password to allow testing.
        :param username: The username to test.
        :param password: The password to test.
        :param group_name: The group name to test.
        :returns: Results of the test.
        """
        current = self.get_settings()
        current["manager_password"] = manager_password
        body = {"auth-config": current} | self._get_auth(username, password, group_name)
        url = self._url_for("test")
        response = self._session.post(url, json=body)
        return response.json()


class AuthMethodManager:
    """
    Base class for managing authentication methods.
    Provides a mechanism to retrieve and update settings
    related to authentication methods.
    """

    METHOD = ""

    def __init__(self, auth_management: AuthManagement):
        """
        Initialize the AuthMethodManager with an instance of AuthManagement.

        :param auth_management: An instance of AuthManagement.
        """

        self._auth_management = auth_management

    def _check_method(self):
        """
        Internal method to ensure the current method is active.

        :raises MethodNotActive: If the current method is not active.
        """

        if self._auth_management._get_setting("method") != self.METHOD:
            raise MethodNotActive(f"{self.METHOD} is not the currently active method.")

    def _get_setting(self, setting: str) -> Any:
        """
        Internal method to get a setting value from the AuthManagement instance.

        :param setting: The name of the setting.
        :returns: The value of the setting.
        """

        self._check_method()
        return self._auth_management._get_setting(setting)

    def _update_setting(self, setting: str, value: Any) -> None:
        """
        Internal method to update a setting value in the AuthManagement instance.

        :param setting: The name of the setting.
        :param value: The new value for the setting.
        """

        self._check_method()
        self._auth_management._update_setting(setting, value)


class LDAPManager(AuthMethodManager):
    """
    Manages LDAP authentication settings.

    Extends the AuthMethodManager class and provides properties
    for retrieving and updating LDAP settings.
    """

    METHOD = "ldap"

    @property
    def server_urls(self) -> str:
        """Return the LDAP server URLs."""
        return self._get_setting("server_urls")

    @server_urls.setter
    def server_urls(self, value: str) -> None:
        """Set the LDAP server URLs."""
        self._update_setting("server_urls", value)

    @property
    def verify_tls(self) -> bool:
        """Return the flag indicating whether to verify the TLS certificate."""
        return self._get_setting("verify_tls")

    @verify_tls.setter
    def verify_tls(self, value: bool) -> None:
        """Set the flag indicating whether to verify the TLS certificate."""
        self._update_setting("verify_tls", value)

    @property
    def cert_data_pem(self) -> str:
        """Return the PEM-encoded certificate data."""
        return self._get_setting("cert_data_pem")

    @cert_data_pem.setter
    def cert_data_pem(self, value: str) -> None:
        """Set the PEM-encoded certificate data."""
        self._update_setting("cert_data_pem", value)

    @property
    def use_ntlm(self) -> bool:
        """Return the flag indicating whether to use NTLM authentication."""
        return self._get_setting("use_ntlm")

    @use_ntlm.setter
    def use_ntlm(self, value: bool) -> None:
        """Set the flag indicating whether to use NTLM authentication."""
        self._update_setting("use_ntlm", value)

    @property
    def root_dn(self) -> str:
        """Return the root DN."""
        return self._get_setting("root_dn")

    @root_dn.setter
    def root_dn(self, value: str) -> None:
        """Set the root DN."""
        self._update_setting("root_dn", value)

    @property
    def user_search_base(self) -> str:
        """Return the user search base."""
        return self._get_setting("user_search_base")

    @user_search_base.setter
    def user_search_base(self, value: str) -> None:
        """Set the user search base."""
        self._update_setting("user_search_base", value)

    @property
    def user_search_filter(self) -> str:
        """Return the user search filter."""
        return self._get_setting("user_search_filter")

    @user_search_filter.setter
    def user_search_filter(self, value: str) -> None:
        """Set the user search filter."""
        self._update_setting("user_search_filter", value)

    @property
    def admin_search_filter(self) -> str:
        """Return the admin search filter."""
        return self._get_setting("admin_search_filter")

    @admin_search_filter.setter
    def admin_search_filter(self, value: str) -> None:
        """Set the admin search filter."""
        self._update_setting("admin_search_filter", value)

    @property
    def group_search_base(self) -> str:
        """Return the group search base."""
        return self._get_setting("group_search_base")

    @group_search_base.setter
    def group_search_base(self, value: str) -> None:
        """Set the group search base."""
        self._update_setting("group_search_base", value)

    @property
    def group_search_filter(self) -> str:
        """Return the group search filter."""
        return self._get_setting("group_search_filter")

    @group_search_filter.setter
    def group_search_filter(self, value: str) -> None:
        """Set the group search filter."""
        self._update_setting("group_search_filter", value)

    @property
    def group_via_user(self) -> bool:
        """Return the flag indicating whether to use group via user."""
        return self._get_setting("group_via_user")

    @group_via_user.setter
    def group_via_user(self, value: bool) -> None:
        """Set the flag indicating whether to use group via user."""
        self._update_setting("group_via_user", value)

    @property
    def group_user_attribute(self) -> str:
        """Return the group user attribute."""
        return self._get_setting("group_user_attribute")

    @group_user_attribute.setter
    def group_user_attribute(self, value: str) -> None:
        """Set the group user attribute."""
        self._update_setting("group_user_attribute", value)

    @property
    def group_membership_filter(self) -> str:
        """Return the group membership filter."""
        return self._get_setting("group_membership_filter")

    @group_membership_filter.setter
    def group_membership_filter(self, value: str) -> None:
        """Set the group membership filter."""
        self._update_setting("group_membership_filter", value)

    @property
    def manager_dn(self) -> str:
        """Return the manager DN."""
        return self._get_setting("manager_dn")

    @manager_dn.setter
    def manager_dn(self, value: str) -> None:
        """Set the manager DN."""
        self._update_setting("manager_dn", value)

    def manager_password(self, value: str) -> None:
        """Set the manager password."""
        self._update_setting("display_attribute", value)

    # manager password can't be retrieved, only set, so we only provide a setter
    manager_password = property(fset=manager_password)

    @property
    def display_attribute(self) -> str:
        """Return the display name LDAP attribute."""
        return self._get_setting("display_attribute")

    @display_attribute.setter
    def display_attribute(self, value: str) -> None:
        """Set the display name LDAP attribute."""
        self._update_setting("display_attribute", value)

    @property
    def group_display_attribute(self) -> str:
        """Return the group display name LDAP attribute."""
        return self._get_setting("group_display_attribute")

    @group_display_attribute.setter
    def group_display_attribute(self, value: str) -> None:
        """Set the group display name LDAP attribute."""
        self._update_setting("group_display_attribute", value)

    @property
    def email_address_attribute(self) -> str:
        """Return the email address LDAP attribute."""
        return self._get_setting("email_address_attribute")

    @email_address_attribute.setter
    def email_address_attribute(self, value: str) -> None:
        """Set the email address LDAP attribute."""
        self._update_setting("email_address_attribute", value)

    @property
    def resource_pool(self) -> str:
        """Return the resource pool a new user will be added to."""
        return self._get_setting("resource_pool")

    @resource_pool.setter
    def resource_pool(self, value: str | ResourcePool) -> None:
        """Set the resource pool a new user will be added to."""
        if isinstance(value, ResourcePool):
            value = value.id
        self._update_setting("resource_pool", value)
