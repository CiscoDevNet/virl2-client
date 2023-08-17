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

import contextlib
import pathlib
from io import BufferedReader
from unittest.mock import ANY, MagicMock

import pytest

from virl2_client.exceptions import InvalidImageFile
from virl2_client.models.node_image_definitions import NodeImageDefinitions

wrong_format_list = [
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
not_supported_list = [
    " . ",
    "file.txt",
    "file.qcw",
    "file.qcow3",
    "file.qcow22",
    "file. qcow",
    "file.qcow2 2",
    "file.qcow ",
    "file.qcow.tar.gz",
]
expected_pass_list = [
    "file.qcow",
    "file.tar.gz.qcow",
    "file.qcow.qcow",
    "qcow2.qcow2.qcow2",
    ".file.qcow",
]


@pytest.fixture(scope="module")
def test_data_path():
    return pathlib.Path("test_data")


@contextlib.contextmanager
def windows_path(path: str):
    if "\\" in path:
        orig = pathlib.Path
        pathlib.Path = pathlib.PureWindowsPath
        try:
            yield
        finally:
            pathlib.Path = orig
    else:
        yield path


@pytest.fixture(autouse=True, scope="module")
def create_test_files(test_data_path):
    # Create test files
    created = []
    for file_path in expected_pass_list:
        path = test_data_path.joinpath(file_path)
        with path.open("w") as f:
            f.write("test")
        created.append(path)

    yield created

    # Teardown
    for path in created:
        path.unlink()


@pytest.mark.parametrize(
    "test_path",
    [
        pytest.param(""),
        pytest.param("/"),
        pytest.param("./"),
        pytest.param("./../"),
        pytest.param("test/test/"),
        pytest.param("/test/test/"),
        pytest.param("\\"),
        pytest.param("..\\..\\"),
        pytest.param("\\test\\"),
        pytest.param("test_data/"),
    ],
)
@pytest.mark.parametrize(
    "rename",
    [
        pytest.param(None),
        pytest.param("renamed.qcow"),
        pytest.param("renamed.qcow2"),
        pytest.param("renamed"),
    ],
)
@pytest.mark.parametrize(
    "test_string, message",
    [pytest.param(test_str, "wrong format") for test_str in wrong_format_list]
    + [pytest.param(test_str, "not supported") for test_str in not_supported_list]
    + [pytest.param(test_str, "") for test_str in expected_pass_list],
)
def test_image_upload_file(rename: str, test_string: str, message: str, test_path: str):
    session = MagicMock()
    session.post = MagicMock()
    nid = NodeImageDefinitions(session)
    filename = test_path + test_string

    if message in ("wrong format", "not supported"):
        with pytest.raises(InvalidImageFile, match=message):
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
        with pytest.raises(FileNotFoundError):
            with windows_path(filename):
                nid.upload_image_file(filename, rename)
