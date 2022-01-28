#
# This file is part of VIRL 2
# Copyright (c) 2019-2022, Cisco Systems, Inc.
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

import logging


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class GroupManagement(object):
    def __init__(self, context):
        self.ctx = context

    @property
    def base_url(self):
        return self.ctx.base_url + "groups"

    def groups(self):
        """
        Get the list of available groups.

        :return: list of group objects
        :rtype:  list
        """
        response = self.ctx.session.get(self.base_url)
        response.raise_for_status()
        return response.json()

    def get_group(self, group_id):
        """
        Gets the info for specified group..

        :param group_id: group uuid4
        :type group_id: str
        :return: group object
        :rtype: dict
        """
        url = self.base_url + "/{}".format(group_id)
        response = self.ctx.session.get(url)
        response.raise_for_status()
        return response.json()

    def delete_group(self, group_id):
        """
        Deletes a group.

        :param group_id: group uuid4
        :type group_id: str
        :return: None
        """
        url = self.base_url + "/{}".format(group_id)
        response = self.ctx.session.delete(url)
        response.raise_for_status()

    def create_group(self, name, description="", members=None, labs=None):
        """
        Creates a group.

        :param name: group name
        :type name: str
        :param description: group description
        :type description: str
        :param members: group members
        :type members: List[str]
        :param labs: group labs
        :type labs: List[Dict[str, str]]
        :return: created group object
        :rtype: dict
        """
        data = {
            "name": name,
            "description": description,
            "members": members or [],
            "labs": labs or [],
        }
        response = self.ctx.session.post(self.base_url, json=data)
        response.raise_for_status()
        return response.json()

    def update_group(
        self, group_id, name=None, description=None, members=None, labs=None
    ):
        """
        Updates a group.

        :param group_id: group uuid4
        :type group_id: str
        :param name: new group name
        :type name: str
        :param description: group description
        :type description: str
        :param members: group members
        :type members: List[str]
        :param labs: group labs
        :type labs: List[Dict[str, str]]
        :return: updated group object
        :rtype: dict
        """
        data = {}
        if name is not None:
            data["name"] = name
        if description is not None:
            data["description"] = description
        if members is not None:
            data["members"] = members
        if labs is not None:
            data["labs"] = labs
        url = self.base_url + "/{}".format(group_id)
        response = self.ctx.session.patch(url, json=data)
        response.raise_for_status()
        return response.json()

    def group_members(self, group_id):
        """
        Gets group members.

        :param group_id: group uuid4
        :type group_id: str
        :return: list of users associated with this group
        :rtype: List[str]
        """
        url = self.base_url + "/{}/members".format(group_id)
        response = self.ctx.session.get(url)
        response.raise_for_status()
        return response.json()

    def group_labs(self, group_id):
        """
        Get the list of labs that are associated with this group.

        :param group_id: group uuid4
        :type group_id: str
        :return: list of labs associated with this group
        :rtype: List[str]
        """
        url = self.base_url + "/{}/labs".format(group_id)
        response = self.ctx.session.get(url)
        response.raise_for_status()
        return response.json()

    def group_id(self, group_name):
        """
        Get unique user uuid4.

        :param group_name: group name
        :type group_name: str
        :return: group unique identifier
        :rtype: str
        """
        url = self.base_url + "/{}/id".format(group_name)
        response = self.ctx.session.get(url)
        response.raise_for_status()
        return response.json()
