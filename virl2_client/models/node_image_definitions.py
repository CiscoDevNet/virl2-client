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
import os

logger = logging.getLogger(__name__)


class NodeImageDefinitions:
    """
    VIRL2 Definition classes to specify a node VM and associated disk images.

    :param context: the authentication context to use
    :type context: authentication.Context
    """
    def __init__(self, context):
        """Constructor method"""
        self._context = context

    @property
    def session(self):
        """
        Returns the used Requests session object.

        :returns: The Requests session object
        :rtype: Requests.Session
        """
        return self._context.session

    @property
    def _base_url(self):
        """
        Returns the base URL to access the controller.

        :returns: The base URL
        :rtype: str
        """
        return self._context.base_url

    def node_definitions(self):
        url = self._base_url + "node_definitions/"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def image_definitions(self):
        url = self._base_url + "image_definitions/"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def image_definitions_for_node_definition(self, definition_id):
        """
        Returns the image definition for a given node definition

        example::

            client_library.definitions.image_definitions_for_node_definition("iosv")

        :param definition_id:
        :returns: the image definition as JSON
        :rtype: str
        """
        url = self._base_url + "node_definitions/" + \
            definition_id + "/image_definitions"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def upload_node_definition(self, definition_id, body):
        url = self._base_url + "node_definitions/"
        response = self.session.post(url, data=body)
        response.raise_for_status()
        return response.json()

    def upload_image_definition(self, definition_id, body):
        url = self._base_url + "image_definitions/"
        response = self.session.post(url, data=body)
        response.raise_for_status()
        return response.json()

    def download_node_definition(self, definition_id):
        """
        Returns the node definition for a given definition ID

        Example::

            client_library.definitions.download_node_definition("iosv")

        :param definition_id:
        :type definition_id: str
        :returns: the node definition as JSON
        :rtype: str
        """
        url = self._base_url + "node_definitions/" + definition_id
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def download_image_definition(self, definition_id):
        """
        Example::

            client_library.definitions.download_image_definition("iosv-158-3")

        :param definition_id: the node definition ID
        :type definition_id: str
        :returns: the image definition as JSON
        :rtype: str
        """

        url = self._base_url + "image_definitions/" + definition_id
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def upload_image_file(self, filename, rename=None, chunk_size_mb=10):
        """

        :param filename: the path of the image to upload
        :type filename: str
        :param rename:  Optional filename to rename to
        :type rename: str
        :param chunk_size_mb: Optional size of upload chunk (mb)
        :type chunk_size_mb: int
        """
        url = self._base_url + "images/upload"
        if rename:
            name = rename
        else:
            _, name = os.path.split(filename)
        print("Uploading %s" % name)
        headers = {'X-Original-File-Name': name}

        total_size = os.path.getsize(filename)

        with open(filename, 'rb') as fh:
            chunk_iter = read_file_as_chunks(fh,
                                             chunk_size_mb=chunk_size_mb,
                                             total_size=total_size)
            response = self.session.post(url, headers=headers, data=chunk_iter)
            response.raise_for_status()
            print("Upload completed")

    def download_image_file_list(self):
        url = self._base_url + "list_image_definition_drop_folder/"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def remove_dropfolder_image(self, filename):
        url = self._base_url + f"images/manage/{filename}"
        response = self.session.delete(url)
        response.raise_for_status()
        return response.json()

    def remove_node_definition(self, definition_id):
        """
        Removes the node definition with the given ID.

        Example::

            client_library.definitions.remove_node_definition("iosv-custom")

        :param definition_id: the definition ID to delete
        :type definition_id: str
        """

        url = self._base_url + "image_definitions/" + definition_id
        response = self.session.delete(url)
        response.raise_for_status()
        return response.json()

    def remove_image_definition(self, definition_id):
        """
        Removes the image definition with the given ID.

        Example::

            client_library.definitions.remove_image_definition("iosv-158-3-custom")

        :param definition_id: the image definition ID to remove
        :type definition_id: str
        """

        url = self._base_url + "image_definitions/" + definition_id
        response = self.session.delete(url)
        response.raise_for_status()
        return response.json()

    def create_image_definition(self, image_id, node_definition_id, label,
                                disk_image):
        """
        Creates a new image definition.

        Example::

            client_library.definitions.create_image_definition("test-1", "iosv", "test", "test.img")

        :param image_id: the ID of the new image definition
        :type image_id: str
        :param node_definition_id: the node definition ID for this image definition
        :type node_definition_id: str
        :param label: the label of the new image definition
        :type label: str
        :param disk_image: the name of the .qcow2 disk image (must exist on server)
        :type disk_image: str
        """
        body = {
            "id": image_id,
            "node_definition_id": node_definition_id,
            "label": label,
            "disk_image": disk_image
        }

        params = {"json": True}

        url = self._base_url + "image_definitions/" + image_id
        response = self.session.post(url, json=body, params=params)
        response.raise_for_status()
        return response.json()


def read_file_as_chunks(file_object, total_size=None, chunk_size_mb=10):
    # TODO: look at requests toolbelt for this
    bytes_in_mb = 1024 * 1024
    chunk_size = chunk_size_mb * bytes_in_mb
    counter = 0
    total_chunks = total_size / chunk_size
    print("Uploading {0} MB in {1}MB chunks".format(total_size / bytes_in_mb,
                                                    chunk_size_mb))
    while True:
        data = file_object.read(chunk_size)
        progress = int(100 * (counter / total_chunks))
        progress = min(progress, 100)
        print("Progress: {0}%".format(progress))
        counter += 1
        if not data:
            break
        yield data
