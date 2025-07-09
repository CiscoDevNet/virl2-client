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

from typing import TYPE_CHECKING, Any

from ..utils import UNCHANGED, _Sentinel, get_url_from_template

if TYPE_CHECKING:
    import httpx


class UserManagement:
    _URL_TEMPLATES = {
        "users": "users",
        "user": "users/{user_id}",
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

    def create_user(self, username: str, pwd: str, **kwargs: Any) -> dict:
        """
        Create a new user.

        :param username: Username.
        :param pwd: Desired password.
        :param kwargs: Optional parameters. See below.

        :Keyword Arguments:
            - fullname: Full name.
            - description: Description.
            - email: Email address.
            - admin: Whether to create an admin user.
            - groups: List of groups to which the user should be added.
            - associations: List of lab associations for the user.
            - resource_pool: Resource pool to which the user should be added.
            - opt_in: Whether the user has seen the initial contact dialog.
            - tour_version: The version of the Workbench tour the user has completed.
            - pubkey: An SSH public key for terminal server. Empty string to clear.

        :returns: User object.
        """
        data: dict[str, Any] = {"username": username, "password": pwd}
        self._prepare_body(data, **kwargs)
        url = self._url_for("users")
        return self._session.post(url, json=data).json()

    def update_user(self, user_id: str, **kwargs: Any) -> dict:
        """
        Update an existing user.

        :param user_id: User UUID4.
        :param kwargs: Optional parameters. See below.

        :Keyword Arguments:
            - fullname: Full name.
            - description: Description.
            - email: Email address.
            - admin: Whether to create an admin user.
            - groups: List of groups to which the user should be added.
            - associations: List of lab associations for the user.
            - password_dict: Dictionary containing old and new passwords.
            - resource_pool: Resource pool to which the user should be added.
            - opt_in: Whether the user has seen the initial contact dialog.
            - tour_version: The version of the Workbench tour the user has completed.
            - pubkey: An SSH public key for terminal server. Empty string to clear.

        :returns: User object.
        """
        data: dict[str, Any] = {}
        self._prepare_body(data, **kwargs)
        url = self._url_for("user", user_id=user_id)
        return self._session.patch(url, json=data).json()

    def _prepare_body(
        self,
        data: dict[str, Any],
        fullname: str | None = None,
        description: str | None = None,
        email: str | None = None,
        groups: list[str] | None = None,
        associations: list[dict[str, list[str]]] | None = None,
        admin: bool | None = None,
        password_dict: dict[str, str] | None = None,
        pubkey: str | None = None,
        resource_pool: str | None | _Sentinel = UNCHANGED,
        opt_in: bool | None | _Sentinel = UNCHANGED,
        tour_version: str | None = None,
    ) -> dict[str, Any]:
        optional_data = {
            "fullname": fullname,
            "description": description,
            "email": email,
            "admin": admin,
            "groups": groups,
            "associations": associations,
            "password": password_dict,
            "pubkey": pubkey,
            "tour_version": tour_version,
        }
        sentinel_data = {
            "resource_pool": resource_pool,
            "opt_in": opt_in,
        }
        for key, value in optional_data.items():
            if value is not None:
                data[key] = value
        for key, value in sentinel_data.items():
            if value != UNCHANGED:
                data[key] = value

    def user_groups(self, user_id: str) -> list[str]:
        """
        Get the groups that a user is a member of.

        :param user_id: User UUID4.
        :returns: List of group names.
        """
        return self.get_user(user_id)["groups"]

    def associations(self, user_id: str) -> list[dict[str, list[str]]]:
        """
        Get a list of lab associations for a user.

        :param user_id: The UUID4 of the user.
        :returns: A list of lab associations for this user.
        """
        return self.get_user(user_id)["associations"]

    def update_associations(
        self, user_id: str, associations: list[dict[str, list[str]]]
    ) -> dict:
        """
        Update the lab associations for a user.

        :param user_id: The UUID4 of the user.
        :param associations: The new list of lab associations.
        :returns: The updated user object.
        """
        data = {"associations": associations}
        url = self._url_for("user", user_id=user_id)
        return self._session.patch(url, json=data).json()

    def user_id(self, username: str) -> str:
        """
        Get the unique UUID4 of a user.

        :param username: User name.
        :returns: User unique identifier.
        """
        url = self._url_for("user_id", username=username)
        return self._session.get(url).json()
