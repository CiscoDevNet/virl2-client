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

from ..utils import UNCHANGED, _Sentinel, get_url_from_template

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

    def users(self) -> list[dict]:
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
        email: str = "",
        admin: bool = False,
        groups: list[str] | None = None,
        resource_pool: str | None = None,
        opt_in: bool | None = None,
        tour_version: str = "",
    ) -> dict:
        """
        Create a new user.

        :param username: Username.
        :param pwd: Desired password.
        :param fullname: Full name.
        :param description: Description.
        :param email: Email address.
        :param admin: Whether to create an admin user.
        :param groups: List of groups to which the user should be added.
        :param resource_pool: Resource pool to which the user should be added.
        :param opt_in: Whether the user has seen the initial contact dialog.
        :param tour_version: The version of the Workbench tour the user has completed.
        :returns: User object.
        """
        data = {"username": username, "password": pwd}
        optional_data = {
            "fullname": fullname,
            "description": description,
            "email": email,
            "admin": admin,
            "groups": groups,
            "resource_pool": resource_pool,
            "opt_in": opt_in,
            "tour_version": tour_version,
        }
        for key, value in optional_data.items():
            if value:
                data[key] = value
        url = self._url_for("users")
        return self._session.post(url, json=data).json()

    def update_user(
        self,
        user_id: str,
        fullname: str | None = None,
        description: str | None = None,
        email: str | None = None,
        groups: list[str] | None = None,
        admin: bool | None = None,
        password_dict: dict[str, str] | None = None,
        resource_pool: str | None | _Sentinel = UNCHANGED,
        opt_in: bool | None | _Sentinel = UNCHANGED,
        tour_version: str | None = None,
    ) -> dict:
        """
        Update an existing user.

        :param user_id: User UUID4.
        :param fullname: Full name.
        :param description: Description.
        :param email: Email address.
        :param admin: Whether to create an admin user.
        :param groups: List of groups to which the user should be added.
        :param password_dict: Dictionary containing old and new passwords.
        :param resource_pool: Resource pool to which the user should be added.
        :param opt_in: Whether the user has seen the initial contact dialog.
        :param tour_version: The version of the Workbench tour the user has completed.
        :returns: User object.
        """
        data: dict[str, Any] = {}
        if fullname is not None:
            data["fullname"] = fullname
        if description is not None:
            data["description"] = description
        if email is not None:
            data["email"] = email
        if admin is not None:
            data["admin"] = admin
        if groups is not None:
            data["groups"] = groups
        if password_dict is not None:
            data["password"] = password_dict
        if resource_pool is not UNCHANGED:
            data["resource_pool"] = resource_pool
        if opt_in is not UNCHANGED:
            data["opt_in"] = opt_in
        if tour_version is not None:
            data["tour_version"] = tour_version

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
