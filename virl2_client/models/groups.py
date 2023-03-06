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

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    import httpx


class GroupManagement:
    def __init__(self, session: httpx.Client) -> None:
        self._session = session

    @property
    def base_url(self) -> str:
        return "groups"

    def groups(self) -> list:
        """
        Get the list of available groups.

        :return: list of group objects
        """
        return self._session.get(self.base_url).json()

    def get_group(self, group_id: str) -> dict:
        """
        Gets info for the specified group.

        :param group_id: group uuid4
        :return: group object
        """
        url = self.base_url + "/{}".format(group_id)
        return self._session.get(url).json()

    def delete_group(self, group_id: str) -> None:
        """
        Deletes a group.

        :param group_id: group uuid4
        :return: None
        """
        url = self.base_url + "/{}".format(group_id)
        self._session.delete(url)

    def create_group(
        self,
        name: str,
        description: str = "",
        members: Optional[list[str]] = None,
        labs: Optional[list[dict[str, str]]] = None,
    ) -> dict:
        """
        Creates a group.

        :param name: group name
        :param description: group description
        :param members: group members
        :param labs: group labs
        :return: created group object
        """
        data = {
            "name": name,
            "description": description,
            "members": members or [],
            "labs": labs or [],
        }
        return self._session.post(self.base_url, json=data).json()

    def update_group(
        self,
        group_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        members: Optional[list[str]] = None,
        labs: Optional[list[dict[str, str]]] = None,
    ) -> dict:
        """
        Updates a group.

        :param group_id: group uuid4
        :param name: new group name
        :param description: group description
        :param members: group members
        :param labs: group labs
        :return: updated group object
        """
        data: dict[str, str | list] = {}
        if name is not None:
            data["name"] = name
        if description is not None:
            data["description"] = description
        if members is not None:
            data["members"] = members
        if labs is not None:
            data["labs"] = labs
        url = self.base_url + "/{}".format(group_id)
        return self._session.patch(url, json=data).json()

    def group_members(self, group_id: str) -> list[str]:
        """
        Gets group members.

        :param group_id: group uuid4
        :return: list of users associated with this group
        """
        url = self.base_url + "/{}/members".format(group_id)
        return self._session.get(url).json()

    def group_labs(self, group_id: str) -> list[str]:
        """
        Get the list of labs that are associated with this group.

        :param group_id: group uuid4
        :return: list of labs associated with this group
        """
        url = self.base_url + "/{}/labs".format(group_id)
        return self._session.get(url).json()

    def group_id(self, group_name: str) -> str:
        """
        Get unique user uuid4.

        :param group_name: group name
        :return: group unique identifier
        """
        url = self.base_url + "/{}/id".format(group_name)
        return self._session.get(url).json()
