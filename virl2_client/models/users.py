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


class UserManagement(object):
    def __init__(self, context):
        self.ctx = context

    @property
    def base_url(self):
        return self.ctx.base_url + "users"

    def users(self):
        """
        Get the list of available users.

        :return: list of user objects
        :rtype:  list
        """
        response = self.ctx.session.get(self.base_url)
        response.raise_for_status()
        return response.json()

    def get_user(self, user_id):
        """
        Gets user info.

        :param user_id: user uuid4
        :type user_id: str
        :return: user object
        :rtype: dict
        """
        url = self.base_url + "/{}".format(user_id)
        response = self.ctx.session.get(url)
        response.raise_for_status()
        return response.json()

    def delete_user(self, user_id):
        """
        Deletes user.

        :param user_id: user uuid4
        :type user_id: str
        :return: None
        """
        url = self.base_url + "/{}".format(user_id)
        response = self.ctx.session.delete(url)
        response.raise_for_status()

    def create_user(
        self, username, pwd, fullname="", description="", admin=False, groups=None
    ):
        """
        Creates user.

        :param username: username
        :type username: str
        :param pwd: desired password
        :type pwd: str
        :param fullname: full name
        :type fullname: str
        :param description: description
        :type description: str
        :param admin: whether to create admin user
        :type admin: bool
        :param groups: adds user to groups specified
        :type groups: List[str]
        :return: user object
        :rtype: Dict
        """
        data = {
            "username": username,
            "password": pwd,
            "fullname": fullname,
            "description": description,
            "admin": admin,
            "groups": groups or [],
        }
        url = self.base_url
        response = self.ctx.session.post(url, json=data)
        response.raise_for_status()
        return response.json()

    def update_user(
        self,
        user_id,
        fullname="",
        description="",
        groups=None,
        admin=None,
        password_dict=None,
    ):
        """
        Updates user.

        :param user_id: user uuid4
        :type user_id: str
        :param fullname: full name
        :type fullname: str
        :param description: description
        :type description: str
        :param admin: whether to create admin user
        :type admin: bool
        :param groups: adds user to groups specified
        :type groups: List[str]
        :param password_dict: dict containing old and new passwords
        :type password_dict: Dict[str:str]
        :return: user object
        :rtype: Dict
        """
        data = {}
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

        url = self.base_url + "/{}".format(user_id)
        response = self.ctx.session.patch(url, json=data)
        response.raise_for_status()
        return response.json()

    def user_groups(self, user_id):
        """
        Get the groups the user is member of.

        :param user_id: user uuid4
        :type user_id: str
        """
        url = self.base_url + "/{}/groups".format(user_id)
        response = self.ctx.session.get(url)
        response.raise_for_status()
        return response.json()

    def user_id(self, username):
        """
        Get unique user uuid4.

        :param username: user name
        :type username: str
        :return: user unique identifier
        :rtype: str
        """
        url = self.base_url + "/{}/id".format(username)
        response = self.ctx.session.get(url)
        response.raise_for_status()
        return response.json()
