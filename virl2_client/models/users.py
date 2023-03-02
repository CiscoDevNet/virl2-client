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

from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    import httpx


class UserManagement:
    def __init__(self, session: httpx.Client) -> None:
        self._session = session

    @property
    def base_url(self) -> str:
        return "users"

    def users(self) -> list:
        """
        Get the list of available users.

        :return: list of user objects
        """
        return self._session.get(self.base_url).json()

    def get_user(self, user_id: str) -> dict:
        """
        Gets user info.

        :param user_id: user uuid4
        :return: user object
        """
        url = self.base_url + "/{}".format(user_id)
        return self._session.get(url).json()

    def delete_user(self, user_id: str) -> None:
        """
        Deletes user.

        :param user_id: user uuid4
        """
        url = self.base_url + "/{}".format(user_id)
        self._session.delete(url)

    def create_user(
        self,
        username: str,
        pwd: str,
        fullname: str = "",
        description: str = "",
        admin: bool = False,
        groups: Optional[list[str]] = None,
        resource_pool: Optional[str] = None,
    ) -> dict:
        """
        Creates user.

        :param username: username
        :param pwd: desired password
        :param fullname: full name
        :param description: description
        :param admin: whether to create admin user
        :param groups: adds user to groups specified
        :param resource_pool: adds user to resource pool specified
        :return: user object
        """
        data = {
            "username": username,
            "password": pwd,
            "fullname": fullname,
            "description": description,
            "admin": admin,
            "groups": groups or [],
            "resource_pool": resource_pool,
        }
        url = self.base_url
        return self._session.post(url, json=data).json()

    def update_user(
        self,
        user_id: str,
        fullname: str = "",
        description: str = "",
        groups: list[str] = None,
        admin: Optional[bool] = None,
        password_dict: dict[str, str] = None,
        resource_pool: Optional[str] = None,
    ) -> dict:
        """
        Updates user.

        :param user_id: user uuid4
        :param fullname: full name
        :param description: description
        :param admin: whether to create admin user
        :param groups: adds user to groups specified
        :param password_dict: dict containing old and new passwords
        :param resource_pool: adds user to resource pool specified
        :return: user object
        """
        data: dict[str, Any] = {}
        if fullname:
            data["fullname"] = fullname
        if description:
            data["description"] = description
        if admin is not None:
            data["admin"] = admin
        if groups is not None:
            data["groups"] = groups
        if password_dict is not None:
            data["password"] = password_dict
        if resource_pool is not None:
            data["resource_pool"] = resource_pool

        url = self.base_url + "/{}".format(user_id)
        return self._session.patch(url, json=data).json()

    def user_groups(self, user_id: str) -> list[str]:
        """
        Get the groups the user is member of.

        :param user_id: user uuid4
        """
        url = self.base_url + "/{}/groups".format(user_id)
        return self._session.get(url).json()

    def user_id(self, username: str) -> str:
        """
        Get unique user uuid4.

        :param username: user name
        :return: user unique identifier
        """
        url = self.base_url + "/{}/id".format(username)
        return self._session.get(url).json()
