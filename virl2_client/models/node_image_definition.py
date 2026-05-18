#
# This file is part of VIRL 2
# Copyright (c) 2019-2026, Cisco Systems, Inc.
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
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, BinaryIO, ClassVar

from ..exceptions import InvalidContentType, InvalidImageFile
from ..utils import get_url_from_template

if TYPE_CHECKING:
    import httpx

_LOGGER = logging.getLogger(__name__)

TARGZ = ".tar.gz"
EXTENSION_LIST = [".qcow", ".qcow2", ".iol", ".tar", TARGZ]


class NodeImageDefinitions:
    _URL_TEMPLATES: ClassVar[dict[str, str]] = {
        "node_defs": "node_definitions",
        "image_defs": "image_definitions",
        "node_def": "node_definitions/{definition_id}",
        "image_def": "image_definitions/{definition_id}",
        "node_image_defs": "node_definitions/{definition_id}/image_definitions",
        "upload": "images/upload",
        "image_list": "list_image_definition_drop_folder",
        "image_manage": "images/manage/{filename}",
    }

    def __init__(self, session: httpx.Client) -> None:
        """
        Manage node and image definitions.

        Node definitions define the properties of a virtual network node.
        Image definitions define disk images that are required to boot a network node.
        Together, they define a complete virtual network node.

        :param session: The httpx-based HTTP client for this session with the server.
        """
        self._session = session

    def _url_for(self, endpoint: str, **kwargs: str) -> str:
        """
        Generate the URL for a given API endpoint.

        :param endpoint: The desired endpoint.
        :param kwargs: Keyword arguments used to format the URL.
        :returns: The formatted URL.
        """
        return get_url_from_template(endpoint, self._URL_TEMPLATES, kwargs)

    def node_definitions(self) -> list[dict[str, Any]]:
        """
        Return all node definitions.

        :returns: A list of node definitions.
        """
        url = self._url_for("node_defs")
        return self._session.get(url).json()

    def image_definitions(self) -> list[dict[str, Any]]:
        """
        Return all image definitions.

        :returns: A list of image definitions.
        """
        url = self._url_for("image_defs")
        return self._session.get(url).json()

    def image_definitions_for_node_definition(
        self, definition_id: str
    ) -> list[dict[str, Any]]:
        """
        Return all image definitions for a given node definition.

        :param definition_id: The ID of the node definition.
        :returns: A list of image definition objects.
        """
        url = self._url_for("node_image_defs", definition_id=definition_id)
        return self._session.get(url).json()

    def set_image_definition_read_only(
        self, definition_id: str, read_only: bool
    ) -> dict[str, Any]:
        """
        Set the read-only attribute of the image definition with the given ID.

        :param definition_id: The ID of the image definition.
        :param read_only: The new value of the read-only attribute.
        :returns: The modified image definition.
        """
        url = f"image_definitions/{definition_id}/read_only"
        return self._session.put(url, json=read_only).json()

    def set_node_definition_read_only(
        self, definition_id: str, read_only: bool
    ) -> dict[str, Any]:
        """
        Set the read-only attribute of the node definition with the given ID.

        :param definition_id: The ID of the node definition.
        :param read_only: The new value of the read-only attribute.
        :returns: The modified node definition.
        """
        url = f"node_definitions/{definition_id}/read_only"
        return self._session.put(url, json=read_only).json()

    def upload_node_definition(
        self, body: str | dict, update: bool = False
    ) -> dict[str, Any]:
        """
        Upload a new node definition.

        :param body: The node definition (yaml or json).
        :param update: If creating a new node definition or updating an existing one.
        :returns: The created (or updated) node definition.
        """
        is_json = _is_json_content(body)
        url = self._url_for("node_defs")
        method = "PUT" if update else "POST"
        if is_json:
            return self._session.request(method, url, json=body).json()
        else:
            # YAML
            return self._session.request(method, url, content=body).json()

    def upload_image_definition(
        self, body: str | dict, update: bool = False
    ) -> dict[str, Any]:
        """
        Upload a new image definition.

        :param body: The image definition (yaml or json).
        :param update: If creating a new image definition or updating an existing one.
        :returns: The created (or updated) image definition.
        """
        is_json = _is_json_content(body)
        url = self._url_for("image_defs")
        method = "PUT" if update else "POST"
        if is_json:
            return self._session.request(method, url, json=body).json()
        else:
            # YAML
            return self._session.request(method, url, content=body).json()

    def download_node_definition(self, definition_id: str) -> str:
        """
        Return the node definition for a given definition ID.

        Example::

            client_library.definitions.download_node_definition("iosv")

        :param definition_id: The ID of the node definition.
        :returns: The node definition as YAML.
        """
        url = self._url_for("node_def", definition_id=definition_id)
        return self._session.get(url).text

    def download_image_definition(self, definition_id: str) -> str:
        """
        Return the image definition for a given definition ID.

        Example::

            client_library.definitions.download_image_definition("iosv-158-3")

        :param definition_id: The ID of the image definition.
        :returns: The image definition as YAML.
        """
        url = self._url_for("image_def", definition_id=definition_id)
        return self._session.get(url).text

    def upload_image_file(
        self,
        filename: pathlib.Path | str,
        rename: str | None = None,
    ) -> None:
        """
        Upload an image file.

        :param filename: The path of the image to upload.
        :param rename: Optional filename to rename to.
        """
        url = self._url_for("upload")

        path = pathlib.Path(filename)

        name = rename or path.name
        extension = TARGZ if path.name.endswith(TARGZ) else path.suffix

        if not name.endswith(extension):
            message = (
                f"Specified filename ({name}) does not match source file's "
                f"extension ({extension}), possibly using a different file format."
            )
            raise InvalidImageFile(message)

        if extension == "" or name == "":
            message = (
                f"Specified filename ({name}) has wrong format "
                f"(correct format is filename.({'|'.join(EXTENSION_LIST)}) )."
            )
            raise InvalidImageFile(message)

        if extension not in EXTENSION_LIST:
            message = (
                f"Specified filename ({name}) has unsupported extension ({extension}) "
                f"(supported extensions are {', '.join(EXTENSION_LIST)})."
            )
            raise InvalidImageFile(message)

        # path may be a PureWindowsPath, cannot use path.is_file
        if not os.path.isfile(filename):
            raise FileNotFoundError(filename)
        _LOGGER.info("Uploading %s", name)
        headers = {"X-Original-File-Name": name}

        def callback_read_factory(
            callback_file: BinaryIO, callback: Callable[[int, int, float], None]
        ) -> Callable[[int], bytes]:
            """Create a read wrapper that invokes callback with progress.

            :param callback_file: The file object to wrap.
            :param callback: Progress callback (current, total, start_time).
            :returns: A read function that wraps the original and calls callback.
            """
            original_read = callback_file.read
            callback_file.seek(0, os.SEEK_END)
            size = callback_file.tell()
            callback_file.seek(0)
            start_time = time.time()

            def callback_read(__n: int) -> bytes:
                """Read chunk and report progress.

                :param __n: Number of bytes to read.
                :returns: Bytes read from the file.
                """
                callback(callback_file.tell(), size, start_time)
                return original_read(__n)

            return callback_read

        with open(filename, "rb") as file:
            file.read = callback_read_factory(file, print_progress_bar)
            files = {"field0": (name, file)}
            self._session.post(url, files=files, headers=headers)
        _LOGGER.info("Upload completed")

    def download_image_file_list(self) -> list[str]:
        """
        Return a list of image files.

        :returns: A list of image file names.
        """
        url = self._url_for("image_list")
        return self._session.get(url).json()

    def remove_dropfolder_image(self, filename: str) -> None:
        """
        Remove an image file from the drop folder.

        :param filename: The name of the image file to remove.
        """
        url = self._url_for("image_manage", filename=filename)
        self._session.delete(url)

    def remove_node_definition(self, definition_id: str) -> None:
        """
        Remove the node definition with the given ID.

        Example::

            client_library.definitions.remove_node_definition("iosv-custom")

        :param definition_id: The ID of the node definition to remove.
        """
        url = self._url_for("node_def", definition_id=definition_id)
        self._session.delete(url)

    def remove_image_definition(self, definition_id: str) -> None:
        """
        Remove the image definition with the given ID.

        Example::

            client_library.definitions.remove_image_definition("iosv-158-3-custom")

        :param definition_id: The ID of the image definition to remove.
        """
        url = self._url_for("image_def", definition_id=definition_id)
        self._session.delete(url)


def print_progress_bar(
    cur: int, total: int, start_time: float, length: int = 50
) -> None:
    """
    Print a progress bar.

    :param cur: The current progress value.
    :param total: The total progress value.
    :param start_time: The start time of the progress.
    :param length: The length of the progress bar.
    """
    percent = f"{100 * (cur / float(total)):.1f}"
    filled_len = round(length * cur / float(total))
    bar = "#" * filled_len + "-" * (length - filled_len)
    raw_elapsed = time.time() - start_time
    elapsed = time.strftime("[%H:%M:%S]", time.gmtime(raw_elapsed))
    print(  # noqa: T201
        f"\r |{bar}| {cur}/{total} {percent}% {elapsed}",
        end="",
        flush=True,
    )
    if cur == total:
        print()  # noqa: T201


def _is_json_content(content: dict[str, Any] | str) -> bool:
    """
    Check if the content is JSON.

    :param content: The content to check.
    :returns: True if the content is JSON, False otherwise.
    :raises InvalidContentType: If the content type is invalid.
    """
    if isinstance(content, dict):
        return True
    elif isinstance(content, str):
        return False
    raise InvalidContentType(type(content))
