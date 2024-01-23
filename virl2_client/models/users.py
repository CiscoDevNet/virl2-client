#
# This file is part of VIRL 2
# Copyright (c) 2019-2024, Cisco Systems, Inc.
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

from typing import TYPE_CHECKING, Any

from ..utils import UNCHANGED, get_url_from_template

if TYPE_CHECKING:
    import httpx


class UserManagement:
    _URL_TEMPLATES = {
        "users": "users",
        "user": "users/{user_id}",
        "user_groups": "users/{user_id}/groups",
        "user_id": "users/{username}/id",
    }

    def __init__(self, session: httpx.Client) -> None:
        self._session = session

    def _url_for(self, endpoint, **kwargs):
        """
        Generate the URL for a given API endpoint.

        :param endpoint: The desired endpoint.
        :param **kwargs: Keyword arguments used to format the URL.
        :returns: The formatted URL.
        """
        return get_url_from_template(endpoint, self._URL_TEMPLATES, kwargs)

    def users(self) -> list[str]:
        """
        Get the list of available users.

        :returns: List of user IDs.
        """
        url = self._url_for("users")
        return self._session.get(url).json()

    def get_user(self, user_id: str) -> dict:
        """
        Get user information.

        :param user_id: User UUID4.
        :returns: User object.
        """
        url = self._url_for("user", user_id=user_id)
        return self._session.get(url).json()

    def delete_user(self, user_id: str) -> None:
        """
        Delete a user.

        :param user_id: User UUID4.
        """
        url = self._url_for("user", user_id=user_id)
        self._session.delete(url)

    def create_user(
        self,
        username: str,
        pwd: str,
        fullname: str = "",
        description: str = "",
        admin: bool = False,
        groups: list[str] | None = None,
        resource_pool: str | None = None,
    ) -> dict:
        """
        Create a new user.

        :param username: Username.
        :param pwd: Desired password.
        :param fullname: Full name.
        :param description: Description.
        :param admin: Whether to create an admin user.
        :param groups: List of groups to which the user should be added.
        :param resource_pool: Resource pool to which the user should be added.
        :returns: User object.
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
        url = self._url_for("users")
        return self._session.post(url, json=data).json()

    def update_user(
        self,
        user_id: str,
        fullname: str | None = UNCHANGED,
        description: str | None = UNCHANGED,
        groups: list[str] | None = UNCHANGED,
        admin: bool | None = None,
        password_dict: dict[str, str] | None = None,
        resource_pool: str | None = UNCHANGED,
    ) -> dict:
        """
        Update an existing user.

        :param user_id: User UUID4.
        :param fullname: Full name.
        :param description: Description.
        :param admin: Whether to create an admin user.
        :param groups: List of groups to which the user should be added.
        :param password_dict: Dictionary containing old and new passwords.
        :param resource_pool: Resource pool to which the user should be added.
        :returns: User object.
        """
        data: dict[str, Any] = {}
        if fullname is not UNCHANGED:
            data["fullname"] = fullname
        if description is not UNCHANGED:
            data["description"] = description
        if admin is not None:
            data["admin"] = admin
        if groups is not UNCHANGED:
            data["groups"] = groups
        if password_dict is not None:
            data["password"] = password_dict
        if resource_pool is not UNCHANGED:
            data["resource_pool"] = resource_pool

        url = self._url_for("user", user_id=user_id)
        return self._session.patch(url, json=data).json()

    def user_groups(self, user_id: str) -> list[str]:
        """
        Get the groups that a user is a member of.

        :param user_id: User UUID4.
        :returns: List of group names.
        """
        url = self._url_for("user_groups", user_id=user_id)
        return self._session.get(url).json()

    def user_id(self, username: str) -> str:
        """
        Get the unique UUID4 of a user.

        :param username: User name.
        :returns: User unique identifier.
        """
        url = self._url_for("user_id", username=username)
        return self._session.get(url).json()
