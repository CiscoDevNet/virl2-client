#
# Python bindings for the Cisco VIRL 2 Network Simulation Platform
#
# This file is part of VIRL 2
#
# Copyright 2020 Cisco Systems Inc.
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

        :return: mapping form username to user object
        :rtype:  dict
        """
        response = self.ctx.session.get(self.base_url)
        response.raise_for_status()
        return response.json()

    def user_roles(self):
        """
        Get roles for this user.

        :return: current user roles
        :rtype: list
        """
        url = self.ctx.base_url + "/user/roles"
        response = self.ctx.session.get(url)
        response.raise_for_status()
        return response.json()

    def change_password(self, user_id, old_pwd, new_pwd):
        """
        Changes user password.

        :param user_id: username
        :type user_id: str
        :param old_pwd: old password
        :type old_pwd: str
        :param new_pwd: new password
        :type new_pwd: str
        :return: None
        """
        data = {"old_password": old_pwd, "new_password": new_pwd}
        url = self.base_url + "/{}/change_password".format(user_id)
        response = self.ctx.session.put(url, json=data)
        response.raise_for_status()
        return response.json()

    def get_user(self, user_id):
        """
        Gets user info.

        :param user_id: username
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

        :param user_id: username
        :return: OK
        :rtype str
        """
        url = self.base_url + "/{}".format(user_id)
        response = self.ctx.session.delete(url)
        response.raise_for_status()
        return response.json()

    def create_user(
        self, user_id, pwd, fullname="", description="", roles=None, groups=None
    ):
        """
        Creates user.

        :param user_id: username
        :type user_id: str
        :param pwd: desired password
        :type pwd: str
        :param fullname: full name
        :type fullname: str
        :param description: description
        :type description: str
        :param roles: roles to give to user
        :type roles: List[str]
        :param groups: adds user to groups specified
        :type groups: List[str]
        :return: OK
        :rtype: str
        """
        data = {
            "password": pwd,
            "fullname": fullname,
            "description": description,
            "roles": roles or ["USER"],
            "groups": groups or [],
        }
        url = self.base_url + "/{}".format(user_id)
        response = self.ctx.session.post(url, json=data)
        response.raise_for_status()
        return response.json()

    def user_groups(self, user_id):
        """
        Get the groups the user is member of.

        :param user_id: username
        :type user_id: str
        """
        url = self.base_url + "/{}/groups".format(user_id)
        response = self.ctx.session.get(url)
        response.raise_for_status()
        return response.json()

    def update_roles(self, user_id, roles=None):
        """
        Updates user roles

        :param user_id:
        :type user_id: str
        :param roles:
        :type roles: List[str]
        :return: Success
        :rtype: str
        """
        data = roles or []
        url = self.base_url + "/{}/roles".format(user_id)
        response = self.ctx.session.put(url, json=data)
        response.raise_for_status()
        return response.json()
