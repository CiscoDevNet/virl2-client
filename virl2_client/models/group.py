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

import warnings
from typing import TYPE_CHECKING, Any

from ..utils import _deprecated_argument, get_url_from_template

if TYPE_CHECKING:
    import httpx


class GroupManagement:
    """Manage groups."""

    _URL_TEMPLATES = {
        "groups": "groups",
        "group": "groups/{group_id}",
        "id": "groups/{group_name}/id",
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

    def groups(self) -> list:
        """
        Get the list of available groups.

        :returns: A list of group objects.
        """
        url = self._url_for("groups")
        return self._session.get(url).json()

    def get_group(self, group_id: str) -> dict:
        """
        Get information for the specified group.

        :param group_id: The UUID4 of the group.
        :returns: A group object.
        """
        url = self._url_for("group", group_id=group_id)
        return self._session.get(url).json()

    def delete_group(self, group_id: str) -> None:
        """
        Delete a group.

        :param group_id: The UUID4 of the group.
        """
        url = self._url_for("group", group_id=group_id)
        self._session.delete(url)

    def create_group(self, name: str, **kwargs: Any) -> dict:
        """
        Create a group.

        :param name: The name of the group.
        :param kwargs: Optional parameters. See below.

        :Keyword Arguments:
            - description: The description of the group.
            - members: The members of the group.
            - associations: The lab associations for the group.
            - labs: DEPRECATED: replaced by 'associations'.
                The labs associated with the group.

        :returns: The created group object.
        """
        data: dict[str, str | list] = {"name": name}
        self._prepare_body(data, **kwargs)
        url = self._url_for("groups")
        return self._session.post(url, json=data).json()

    def update_group(self, group_id: str, **kwargs: Any) -> dict:
        """
        Update a group.

        :param group_id: The UUID4 of the group.
        :param kwargs: Optional parameters. See below.

        :Keyword Arguments:
            - name: The name of the group.
            - description: The description of the group.
            - members: The members of the group.
            - associations: The lab associations for the group.
            - labs: DEPRECATED: replaced by 'associations'.
                The labs associated with the group.

        :returns: The updated group object.
        """
        data: dict[str, str | list] = {}
        self._prepare_body(data, **kwargs)
        url = self._url_for("group", group_id=group_id)
        return self._session.patch(url, json=data).json()

    def _prepare_body(
        self,
        data: dict[str, str | list],
        name: str | None = None,
        description: str | None = None,
        members: list[str] | None = None,
        labs: list[dict[str, str]] | None = None,
        associations: list[dict[str, list[str]]] | None = None,
    ):
        optional_data = {
            "name": name,
            "description": description,
            "members": members,
            "labs": labs,
            "associations": associations,
        }
        if labs is not None:
            func = self.create_group if data else self.update_group
            _deprecated_argument(func, labs, "labs")
        for key, value in optional_data.items():
            if value is not None:
                data[key] = value

    def group_members(self, group_id: str) -> list[str]:
        """
        Get the members of a group.

        :param group_id: The UUID4 of the group.
        :returns: A list of users associated with this group.
        """
        return self.get_group(group_id)["members"]

    def group_labs(self, group_id: str) -> list[str]:
        """
        DEPRECATED: Use `.associations()` instead.
        (Reason: adapted to the new format of lab associations)

        Get a list of labs associated with a group.

        :param group_id: The UUID4 of the group.
        :returns: A list of labs associated with this group.
        """
        warnings.warn(
            "'GroupManagement.group_labs()' is deprecated.Use '.associations' instead.",
        )
        return [lab["id"] for lab in self.get_group(group_id)["labs"]]

    def associations(self, group_id: str) -> list[dict[str, list[str]]]:
        """
        Get a list of lab associations for a group.

        :param group_id: The UUID4 of the group.
        :returns: A list of lab associations for this group.
        """
        return self.get_group(group_id)["associations"]

    def update_associations(
        self, group_id: str, associations: list[dict[str, list[str]]]
    ) -> dict:
        """
        Update the lab associations for a group.

        :param group_id: The UUID4 of the group.
        :param associations: The new list of lab associations.
        :returns: The updated group object.
        """
        data = {"associations": associations}
        url = self._url_for("group", group_id=group_id)
        return self._session.patch(url, json=data).json()

    def group_id(self, group_name: str) -> str:
        """
        Get the unique UUID4 of a group.

        :param group_name: The name of the group.
        :returns: The unique identifier of the group.
        """
        url = self._url_for("id", group_name=group_name)
        return self._session.get(url).json()
