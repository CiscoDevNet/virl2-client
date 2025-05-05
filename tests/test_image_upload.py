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

import contextlib
import pathlib
from io import BufferedReader
from typing import Iterator
from unittest.mock import ANY, MagicMock

import pytest

from virl2_client.exceptions import InvalidImageFile
from virl2_client.models import NodeImageDefinitions

WRONG_FORMAT_LIST = [
    "",
    ".",
    "file",
    ".text",
    ".qcow2",
    "qcow.",
    "qcow2",
    "qcow",
    ".qcow.",
    ".file.",
    "file.qcow.",
]
NOT_SUPPORTED_LIST = [
    " . ",
    "file.txt",
    "file.qcw",
    "file.qcow3",
    "file.qcow22",
    "file. qcow",
    "file.qcow2 2",
    "file.qcow ",
    "file.qcow.gz",
    "file.tgz",
]
EXPECTED_PASS_LIST = [
    "file.qcow",
    "file.tar.gz.qcow",
    "file.qcow.qcow",
    "qcow2.qcow2.qcow2",
    ".file.qcow",
    "file.iol",
    "qcow.iol",
    "file.tar",
    "file.tar.gz",
]


# This fixture is not meant to be used in tests - rather, it's here to easily manually
# update files when the expected_pass_list is changed. Just change autouse to True,
# then locally run test_image_upload_file, and this will generate all the files
# in the expected_pass_list into test_data.
@pytest.fixture
def create_test_files(test_data_dir):
    for file_path in EXPECTED_PASS_LIST:
        path = test_data_dir / file_path
        path.write_text("test")


@contextlib.contextmanager
def windows_path(path: str) -> Iterator[None]:
    if "\\" in path:
        orig = pathlib.Path
        pathlib.Path = pathlib.PureWindowsPath
        try:
            yield
        finally:
            pathlib.Path = orig
    else:
        yield


@pytest.mark.parametrize(
    "test_path",
    ["", "/", "./", "./../", "test/test/", "/test/test/", "\\", "..\\..\\", "\\test\\"],
)
@pytest.mark.parametrize("rename", [None, "rename"])
@pytest.mark.parametrize(
    "test_string",
    WRONG_FORMAT_LIST + NOT_SUPPORTED_LIST + EXPECTED_PASS_LIST,
)
def test_image_upload_file(rename: str | None, test_string: str, test_path: str):
    session = MagicMock()
    nid = NodeImageDefinitions(session)
    filename = test_path + test_string
    if rename is not None:
        rename += test_string

    if test_string in WRONG_FORMAT_LIST:
        with pytest.raises(InvalidImageFile, match="wrong format"):
            with windows_path(filename):
                nid.upload_image_file(filename, rename)
    elif test_string in NOT_SUPPORTED_LIST:
        with pytest.raises(InvalidImageFile, match="unsupported extension"):
            with windows_path(filename):
                nid.upload_image_file(filename, rename)
    elif test_path == "test_data/":
        with windows_path(filename):
            nid.upload_image_file(filename, rename)
        name = rename or test_string
        files = {"field0": (name, ANY)}
        headers = {"X-Original-File-Name": name}
        session.post.assert_called_with("images/upload", files=files, headers=headers)
        file = session.post.call_args.kwargs["files"]["field0"][1]
        assert isinstance(file, BufferedReader)
        assert pathlib.Path(file.name).resolve() == pathlib.Path(filename).resolve()
        file.close()
    else:
        if rename is not None:
            with pytest.raises(InvalidImageFile, match="does not match source"):
                with windows_path(filename):
                    nid.upload_image_file(filename, rename[:-3])
        with pytest.raises(FileNotFoundError):
            with windows_path(filename):
                nid.upload_image_file(filename, rename)
