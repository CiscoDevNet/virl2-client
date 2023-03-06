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
from unittest.mock import MagicMock

import pytest

from virl2_client.exceptions import InvalidImageFile
from virl2_client.models.authentication import make_session
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
    ],
)
@pytest.mark.parametrize("usage", [pytest.param("name"), pytest.param("rename")])
@pytest.mark.parametrize(
    "test_string, message",
    [pytest.param(test_str, "wrong format") for test_str in wrong_format_list]
    + [pytest.param(test_str, "not supported") for test_str in not_supported_list]
    + [pytest.param(test_str, "") for test_str in expected_pass_list],
)
def test_image_upload_file(usage: str, test_string: str, message: str, test_path: str):
    context = make_session("http://dontcare")
    context.session = MagicMock()
    nid = NodeImageDefinitions(context)

    rename = None
    filename = test_path + test_string

    if usage == "rename":
        rename = test_string

    try:
        with windows_path(filename):
            nid.upload_image_file(filename, rename)
    except FileNotFoundError:
        assert message == ""
    except InvalidImageFile as exc:
        assert message in exc.args[0]
    else:
        assert message == ""
