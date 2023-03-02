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

import logging
import os
import pathlib
import time
import warnings
from typing import TYPE_CHECKING, BinaryIO, Callable, Optional

from virl2_client.exceptions import InvalidImageFile

if TYPE_CHECKING:
    import httpx


_LOGGER = logging.getLogger(__name__)


class NodeImageDefinitions:
    def __init__(self, session: httpx.Client) -> None:
        """
        VIRL2 Definition classes to specify a node VM and associated disk images.

        :param session: httpx Client session
        """
        self._session = session

    @property
    def session(self) -> httpx.Client:
        """
        Returns the used httpx client session object.

        :returns: The session object
        """
        return self._session

    def node_definitions(self) -> list[dict]:
        """
        Returns all node definitions.

        :return: list of node definitions
        """
        url = "node_definitions/"
        return self._session.get(url).json()

    def image_definitions(self) -> list[dict]:
        """
        Returns all image definitions.

        :return: list of image definitions
        """
        url = "image_definitions/"
        return self._session.get(url).json()

    def image_definitions_for_node_definition(self, definition_id: str) -> list[dict]:
        """
        Returns all image definitions for a given node definition

        example::

            client_library.definitions.image_definitions_for_node_definition("iosv")

        :param definition_id: node definition id
        :returns: list of image definition objects
        """
        url = "node_definitions/" + definition_id + "/image_definitions"
        return self._session.get(url).json()

    def upload_node_definition(self, body, json: bool = False) -> str:
        """
        Upload new node definition.

        :param body: node definition (yaml or json)
        :type: str or dict
        :param json: whether we are sending json data
        :return: "Success"
        """
        url = "node_definitions/"
        if json:
            return self._session.post(url, json=body).json()
        else:
            # YAML
            return self._session.post(url, content=body).json()

    def upload_image_definition(self, body, json: bool = False) -> str:
        """
        Upload new image definition.

        :param body: image definition (yaml or json)
        :type: str or dict
        :param json: whether we are sending json data
        :return: "Success"
        """
        url = "image_definitions/"
        if json:
            return self._session.post(url, json=body).json()
        else:
            # YAML
            return self._session.post(url, content=body).json()

    def download_node_definition(self, definition_id: str) -> str:
        """
        Returns the node definition for a given definition ID

        Example::

            client_library.definitions.download_node_definition("iosv")

        :param definition_id: the node definition ID
        :returns: the node definition as YAML
        """
        url = "node_definitions/" + definition_id
        return self._session.get(url).json()

    def download_image_definition(self, definition_id: str) -> str:
        """
        Example::

            client_library.definitions.download_image_definition("iosv-158-3")

        :param definition_id: the image definition ID
        :returns: the image definition as YAML
        """

        url = "image_definitions/" + definition_id
        return self._session.get(url).json()

    def upload_image_file(
        self,
        filename: str,
        rename: Optional[str] = None,
        chunk_size_mb: Optional[int] = None,
    ) -> None:
        """
        :param filename: the path of the image to upload
        :param rename:  Optional filename to rename to
        :param chunk_size_mb: Optional size of upload chunk (mb)
            (deprecated since 2.2.0)
        """
        if chunk_size_mb is not None:
            warnings.warn(
                'The argument "chunk_size_mb" is deprecated as it never worked',
                DeprecationWarning,
            )

        extension_list = [".qcow", ".qcow2"]
        url = "images/upload"

        path = pathlib.Path(filename)
        extension = "".join(path.suffixes)
        last_ext = path.suffix
        name = rename or path.stem

        if extension == "" or name == "":
            message = (
                f"Name specified ({name}) is in wrong format "
                f"(correct: filename.({'|'.join(extension_list)}) )."
            )
            raise InvalidImageFile(message)

        if extension not in extension_list and last_ext not in extension_list:
            message = (
                f"Extension in {name} not supported. "
                f"(supported extensions are {', '.join(extension_list)})."
            )
            raise InvalidImageFile(message)

        if not os.path.exists(filename):
            message = f"File with specified name ({filename}) does not exist."
            raise FileNotFoundError(message)

        print(f"Uploading {name}")
        headers = {"X-Original-File-Name": name}

        def callback_read_factory(
            callback_file: BinaryIO, callback: Callable[[int, int, float], None]
        ):
            original_read = callback_file.read
            callback_file.seek(0, os.SEEK_END)
            size = callback_file.tell()
            callback_file.seek(0)
            start_time = time.time()

            def callback_read(__n):
                callback(callback_file.tell(), size, start_time)
                return original_read(__n)

            return callback_read

        file = open(filename, "rb")
        file.read = callback_read_factory(file, print_progress_bar)
        files = {"field0": (name, file)}

        self._session.post(url, files=files, headers=headers)
        print("Upload completed")

    def download_image_file_list(self) -> list[str]:
        url = "list_image_definition_drop_folder/"
        return self._session.get(url).json()

    def remove_dropfolder_image(self, filename: str) -> str:
        """
        :returns: "Success"
        """
        url = "images/manage/" + filename
        return self._session.delete(url).json()

    def remove_node_definition(self, definition_id: str) -> None:
        """
        Removes the node definition with the given ID.

        Example::

            client_library.definitions.remove_node_definition("iosv-custom")

        :param definition_id: the definition ID to delete
        """

        url = "node_definitions/" + definition_id
        self._session.delete(url)

    def remove_image_definition(self, definition_id: str) -> None:
        """
        Removes the image definition with the given ID.

        Example::

            client_library.definitions.remove_image_definition("iosv-158-3-custom")

        :param definition_id: the image definition ID to remove
        """

        url = "image_definitions/" + definition_id
        self._session.delete(url)


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
