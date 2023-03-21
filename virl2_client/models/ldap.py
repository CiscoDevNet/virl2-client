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

from httpx import Client

from .resource_pools import ResourcePool


class LDAPManagement:
    def __init__(self, session: Client, auto_sync=True, auto_sync_interval=1.0):
        self._session = session
        self.auto_sync = auto_sync
        self.auto_sync_interval = auto_sync_interval
        self._last_sync_time = 0.0
        self._ldap_settings = {}
        self.sync()

    def sync_if_outdated(self) -> None:
        timestamp = time.time()
        if (
            self.auto_sync
            and timestamp - self._last_sync_time > self.auto_sync_interval
        ):
            self.sync()

    def sync(self) -> None:
        self._ldap_settings = self._get_current_settings()
        self._last_sync_time = time.time()

    @property
    def _base_url(self) -> str:
        return "system/auth"

    @property
    def _config_url(self) -> str:
        return self._base_url + "/config"

    @property
    def _test_url(self) -> str:
        return self._base_url + "/test"

    def _get_setting(self, setting: str):
        self.sync_if_outdated()
        return self._ldap_settings[setting]

    @property
    def ldap_settings(self) -> dict:
        self.sync_if_outdated()
        return self._ldap_settings.copy()

    @property
    def method(self) -> str:
        return self._get_setting("method")

    @method.setter
    def method(self, value: str) -> None:
        """Must be either 'local' or 'ldap'."""
        if value not in ("local", "ldap"):
            raise ValueError("Method must be either 'local' or 'ldap'.")
        self.update_settings(method=value)

    @property
    def server_urls(self) -> str:
        return self._get_setting("server_urls")

    @server_urls.setter
    def server_urls(self, value: str) -> None:
        self.update_settings(server_urls=value)

    @property
    def verify_tls(self) -> bool:
        return self._get_setting("verify_tls")

    @verify_tls.setter
    def verify_tls(self, value: bool) -> None:
        self.update_settings(verify_tls=value)

    @property
    def cert_data_pem(self) -> str:
        return self._get_setting("cert_data_pem")

    @cert_data_pem.setter
    def cert_data_pem(self, value: str) -> None:
        self.update_settings(cert_data_pem=value)

    @property
    def use_ntlm(self) -> bool:
        return self._get_setting("use_ntlm")

    @use_ntlm.setter
    def use_ntlm(self, value: bool) -> None:
        self.update_settings(use_ntlm=value)

    @property
    def root_dn(self) -> str:
        return self._get_setting("root_dn")

    @root_dn.setter
    def root_dn(self, value: str) -> None:
        self.update_settings(root_dn=value)

    @property
    def user_search_base(self) -> str:
        return self._get_setting("user_search_base")

    @user_search_base.setter
    def user_search_base(self, value: str) -> None:
        self.update_settings(user_search_base=value)

    @property
    def user_search_filter(self) -> str:
        return self._get_setting("user_search_filter")

    @user_search_filter.setter
    def user_search_filter(self, value: str) -> None:
        self.update_settings(user_search_filter=value)

    @property
    def admin_search_filter(self) -> str:
        return self._get_setting("admin_search_filter")

    @admin_search_filter.setter
    def admin_search_filter(self, value: str) -> None:
        self.update_settings(admin_search_filter=value)

    @property
    def group_search_base(self) -> str:
        return self._get_setting("group_search_base")

    @group_search_base.setter
    def group_search_base(self, value: str) -> None:
        self.update_settings(group_search_base=value)

    @property
    def group_search_filter(self) -> str:
        return self._get_setting("group_search_filter")

    @group_search_filter.setter
    def group_search_filter(self, value: str) -> None:
        self.update_settings(group_search_filter=value)

    @property
    def group_via_user(self) -> bool:
        return self._get_setting("group_via_user")

    @group_via_user.setter
    def group_via_user(self, value: bool) -> None:
        self.update_settings(group_via_user=value)

    @property
    def group_user_attribute(self) -> str:
        return self._get_setting("group_user_attribute")

    @group_user_attribute.setter
    def group_user_attribute(self, value: str) -> None:
        self.update_settings(group_user_attribute=value)

    @property
    def group_membership_filter(self) -> str:
        return self._get_setting("group_membership_filter")

    @group_membership_filter.setter
    def group_membership_filter(self, value: str) -> None:
        self.update_settings(group_membership_filter=value)

    @property
    def manager_dn(self) -> str:
        return self._get_setting("manager_dn")

    @manager_dn.setter
    def manager_dn(self, value: str) -> None:
        self.update_settings(manager_dn=value)

    def manager_password(self, value: str) -> None:
        # can't use update_settings since we don't store the manager password
        # unlike other settings
        settings = {"method": self.method, "manager_password": value}
        self._session.put(self._config_url, json=settings)

    # manager password can't be retrieved, only set, so we only provide a setter
    manager_password = property(fset=manager_password)

    @property
    def display_attribute(self) -> str:
        return self._get_setting("display_attribute")

    @display_attribute.setter
    def display_attribute(self, value: str) -> None:
        self.update_settings(display_attribute=value)

    @property
    def email_address_attribute(self) -> str:
        return self._get_setting("email_address_attribute")

    @email_address_attribute.setter
    def email_address_attribute(self, value: str) -> None:
        self.update_settings(email_address_attribute=value)

    @property
    def resource_pool(self) -> str:
        return self._get_setting("resource_pool")

    @resource_pool.setter
    def resource_pool(self, value: str | ResourcePool) -> None:
        if isinstance(value, ResourcePool):
            value = value.id
        self.update_settings(resource_pool=value)

    def _get_current_settings(self) -> dict:
        return self._session.get(self._config_url).json()

    def update_settings(self, *args, **kwargs):
        """
        Update multiple LDAP settings at once.
        More efficient in batches than setters.
        If passed a dictionary, reads the dictionary for settings.
        If passed multiple keyword arguments, each is taken as a setting.


        Example::

            ldap.update_settings({"method": "ldap", "verify_tls": False})
            ldap.update_settings(method="ldap", verify_tls=False)

        :param kwargs: a dictionary of settings, or multiple keywords of settings
        """
        settings = {"method": self.method}
        if len(kwargs) > 0:
            settings.update(kwargs)
        else:
            settings.update(args[0])
        self._session.put(self._config_url, json=settings)
        self._ldap_settings.update(settings)

    def test_auth(self, config: dict, username: str, password: str) -> dict:
        """
        Tests a set of credentials against the specified authentication configuration.
        """
        body = {
            "auth-config": config,
            "auth-data": {"username": username, "password": password},
        }
        response = self._session.post(self._test_url, json=body)
        return response.json()

    def test_current_auth(
        self, manager_password: str, username: str, password: str
    ) -> dict:
        """
        Tests a set of credentials against the currently applied authentication
        configuration.
        """
        current = self._get_current_settings()
        current.update({"manager_password": manager_password})
        body = {
            "auth-config": current,
            "auth-data": {"username": username, "password": password},
        }
        response = self._session.post(self._test_url, json=body)
        return response.json()
