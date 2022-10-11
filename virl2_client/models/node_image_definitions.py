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

from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING, Optional

from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor

if TYPE_CHECKING:
    from requests import Session


class NodeImageDefinitions:
    def __init__(self, context) -> None:
        """
        VIRL2 Definition classes to specify a node VM and associated disk images.

        :param context: the authentication context to use
        :type context: authentication.Context
        """
        self._context = context

    @property
    def session(self) -> Session:
        """
        Returns the used Requests session object.

        :returns: The Requests session object
        """
        return self._context.session

    @property
    def _base_url(self) -> str:
        """
        Returns the base URL to access the controller.

        :returns: The base URL
        """
        return self._context.base_url

    def node_definitions(self) -> list[dict]:
        """
        Returns all node definitions.

        :return: list of node definitions
        """
        url = self._base_url + "node_definitions/"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def image_definitions(self) -> list[dict]:
        """
        Returns all image definitions.

        :return: list of image definitions
        """
        url = self._base_url + "image_definitions/"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def image_definitions_for_node_definition(self, definition_id: str) -> list[dict]:
        """
        Returns all image definitions for a given node definition

        example::

            client_library.definitions.image_definitions_for_node_definition("iosv")

        :param definition_id: node definition id
        :returns: list of image definition objects
        """
        url = (
            self._base_url + "node_definitions/" + definition_id + "/image_definitions"
        )
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def upload_node_definition(self, body, json: bool = False) -> str:
        """
        Upload new node definition.

        :param body: node definition (yaml or json)
        :type: str or dict
        :param json: whether we are sending json data
        :return: "Success"
        """
        url = self._base_url + "node_definitions/"
        if json:
            response = self.session.post(url, json=body)
        else:
            # YAML
            response = self.session.post(url, data=body)
        response.raise_for_status()
        return response.json()

    def upload_image_definition(self, body, json: bool = False) -> str:
        """
        Upload new image definition.

        :param body: image definition (yaml or json)
        :type: str or dict
        :param json: whether we are sending json data
        :return: "Success"
        """
        url = self._base_url + "image_definitions/"
        if json:
            response = self.session.post(url, json=body)
        else:
            # YAML
            response = self.session.post(url, data=body)
        response.raise_for_status()
        return response.json()

    def download_node_definition(self, definition_id: str) -> str:
        """
        Returns the node definition for a given definition ID

        Example::

            client_library.definitions.download_node_definition("iosv")

        :param definition_id: the node definition ID
        :returns: the node definition as YAML
        """
        url = self._base_url + "node_definitions/" + definition_id
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def download_image_definition(self, definition_id: str) -> str:
        """
        Example::

            client_library.definitions.download_image_definition("iosv-158-3")

        :param definition_id: the image definition ID
        :returns: the image definition as YAML
        """

        url = self._base_url + "image_definitions/" + definition_id
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def upload_image_file(
        self, filename: str, rename: Optional[str] = None, chunk_size_mb: int = 10
    ) -> None:
        """
        :param filename: the path of the image to upload
        :param rename:  Optional filename to rename to
        :param chunk_size_mb: Optional size of upload chunk (mb)
            (deprecated since 2.2.0)
        """
        url = self._base_url + "images/upload"
        if rename:
            name = rename
        else:
            _, name = os.path.split(filename)
        print("Uploading %s" % name)
        headers = {"X-Original-File-Name": name}

        mpe = MultipartEncoder(fields={"field0": (name, open(filename, "rb"))})
        monitor = MultipartEncoderMonitor(mpe, progress_callback)

        response = self.session.post(url, data=monitor, headers=headers)  # type: ignore
        # type is ignored because a duck-compatible extension is used
        response.raise_for_status()
        print("Upload completed")

    def download_image_file_list(self) -> list[str]:
        url = self._base_url + "list_image_definition_drop_folder/"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def remove_dropfolder_image(self, filename: str) -> str:
        """
        :returns: "Success"
        """
        url = self._base_url + "images/manage/{}".format(filename)
        response = self.session.delete(url)
        response.raise_for_status()
        return response.json()

    def remove_node_definition(self, definition_id: str) -> None:
        """
        Removes the node definition with the given ID.

        Example::

            client_library.definitions.remove_node_definition("iosv-custom")

        :param definition_id: the definition ID to delete
        """

        url = self._base_url + "node_definitions/" + definition_id
        response = self.session.delete(url)
        response.raise_for_status()

    def remove_image_definition(self, definition_id: str) -> None:
        """
        Removes the image definition with the given ID.

        Example::

            client_library.definitions.remove_image_definition("iosv-158-3-custom")

        :param definition_id: the image definition ID to remove
        """

        url = self._base_url + "image_definitions/" + definition_id
        response = self.session.delete(url)
        response.raise_for_status()


def progress_callback(monitor: MultipartEncoderMonitor) -> None:
    if not hasattr(monitor, "start_time"):
        monitor.start_time = time.time()
    if not hasattr(monitor, "last_bytes"):
        monitor.last_bytes = -1
    # Track progress in the monitor instance itself.
    if monitor.bytes_read > monitor.last_bytes:
        print_progress_bar(monitor.bytes_read, monitor.len, monitor.start_time)
        monitor.last_bytes = monitor.bytes_read


def print_progress_bar(cur: int, total: int, start_time: float, length=50) -> None:
    percent = "{0:.1f}".format(100 * (cur / float(total)))
    filled_len = int(round(length * cur / float(total)))
    bar = "#" * filled_len + "-" * (length - filled_len)
    raw_elapsed = time.time() - start_time
    elapsed = time.strftime("[%H:%M:%S]", time.gmtime(raw_elapsed))
    print(
        "\r |{}| {}/{} {}% {}".format(bar, cur, total, percent, elapsed),
        end="",
        flush=True,
    )
    if cur == total:
        print()
