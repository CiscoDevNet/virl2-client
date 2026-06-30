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
"""Tests for NodeImageDefinitions CRUD, upload validation, image file handling, and definitions."""

from __future__ import annotations

import contextlib
import pathlib
import sys
from io import BufferedReader
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import ANY, MagicMock, patch

import pytest

from virl2_client.exceptions import InvalidContentType, InvalidImageFile
from virl2_client.models.node_image_definition import (
    EXTENSION_LIST,
    NodeImageDefinitions,
    print_progress_bar,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from virl2_client.virl2_client import ClientLibrary


@pytest.mark.parametrize(
    "method",
    [
        "node_definitions",
        "image_definitions",
        "download_image_file_list",
    ],
)
def test_node_image_defs_list(method: str) -> None:
    """node_definitions, image_definitions, download_image_file_list return list.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    defs = NodeImageDefinitions(session)
    session.get.return_value.json.return_value = [{"id": "d1"}]
    assert getattr(defs, method)() == [{"id": "d1"}]


def test_image_definitions_for_node_definition() -> None:
    """image_definitions_for_node_definition returns list for node def id.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    defs = NodeImageDefinitions(session)
    session.get.return_value.json.return_value = [{"id": "d1"}]
    assert defs.image_definitions_for_node_definition("nd1") == [{"id": "d1"}]


@pytest.mark.parametrize(
    "method",
    [
        "set_image_definition_read_only",
        "set_node_definition_read_only",
    ],
)
def test_node_image_defs_read_only(method: str) -> None:
    """set_*_read_only puts and returns read_only flag.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    defs = NodeImageDefinitions(session)
    session.put.return_value.json.return_value = {"id": "x", "read_only": True}
    assert getattr(defs, method)("id1", True)["read_only"] is True


@pytest.mark.parametrize(
    ("upload_method", "payload"),
    [
        ("upload_node_definition", {"id": "a"}),
        ("upload_image_definition", {"id": "a"}),
    ],
)
def test_upload_def_json_rt(upload_method: str, payload: dict) -> None:
    """upload_*_definition with dict posts json.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    defs = NodeImageDefinitions(session)
    session.request.return_value.json.return_value = {"id": "a"}
    assert getattr(defs, upload_method)(payload) == {"id": "a"}


@pytest.mark.parametrize(
    "upload_method",
    [
        "upload_node_definition",
        "upload_image_definition",
    ],
)
def test_upload_def_yaml_update_rt(upload_method: str) -> None:
    """upload_*_definition string with update=True uses PUT.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    defs = NodeImageDefinitions(session)
    session.request.return_value.json.return_value = {"id": "a"}
    assert getattr(defs, upload_method)("yaml-body", update=True) == {"id": "a"}


@pytest.mark.parametrize(
    ("method", "arg"),
    [
        ("download_node_definition", "nd"),
        ("download_image_definition", "img"),
    ],
)
def test_node_image_defs_download(method: str, arg: str) -> None:
    """download_*_definition returns session text.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    defs = NodeImageDefinitions(session)
    session.get.return_value.text = "yaml-doc"
    assert getattr(defs, method)(arg) == "yaml-doc"


def test_remove_dropfolder_image_list() -> None:
    """remove_dropfolder_image deletes the image and returns None.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    defs = NodeImageDefinitions(session)
    assert defs.remove_dropfolder_image("x.qcow2") is None
    session.delete.assert_called_once_with("images/manage/x.qcow2")


@pytest.mark.parametrize(
    ("method", "arg"),
    [
        ("remove_node_definition", "nd"),
        ("remove_image_definition", "img"),
    ],
)
def test_remove_def_list_rt(method: str, arg: str) -> None:
    """remove_*_definition deletes definition.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    defs = NodeImageDefinitions(session)
    getattr(defs, method)(arg)
    session.delete.assert_called()


@pytest.mark.parametrize(
    ("rename", "exc_type"),
    [
        ("file.bad", InvalidImageFile),
        ("file.unsupported", InvalidImageFile),
    ],
)
def test_upload_image_file_validation_errors(
    tmp_path: Path, rename: str, exc_type: type[Exception]
) -> None:
    """upload_image_file raises on bad extension or unsupported format.

    NOTE: LLM-generated test -- verify for correctness.
    """
    defs = NodeImageDefinitions(MagicMock())
    good = tmp_path / "file.qcow2"
    good.write_bytes(b"abc")
    with pytest.raises(exc_type):
        defs.upload_image_file(good, rename=rename)


def test_upload_image_file_missing(tmp_path: Path) -> None:
    """upload_image_file raises FileNotFoundError for missing file.

    NOTE: LLM-generated test -- verify for correctness.
    """
    defs = NodeImageDefinitions(MagicMock())
    with pytest.raises(FileNotFoundError):
        defs.upload_image_file(tmp_path / "missing.qcow2")


def test_upload_image_file_success(tmp_path: Path) -> None:
    """upload_image_file succeeds and posts with valid extension.

    NOTE: LLM-generated test -- verify for correctness.
    """
    defs = NodeImageDefinitions(MagicMock())
    good = tmp_path / "file.qcow2"
    good.write_bytes(b"abc")
    defs.upload_image_file(good)
    defs._session.post.assert_called_once()
    files = defs._session.post.call_args.kwargs["files"]
    uploaded_name = files["field0"][0]
    assert any(uploaded_name.endswith(ext) for ext in EXTENSION_LIST)


def test_upload_image_file_progress(tmp_path: Path) -> None:
    """print_progress_bar runs without error.

    NOTE: LLM-generated test -- verify for correctness.
    """
    _ = NodeImageDefinitions(MagicMock())
    image = tmp_path / "stream.qcow2"
    image.write_bytes(b"abcdef")

    with patch("virl2_client.models.node_image_definition.time.time", return_value=10):
        print_progress_bar(1, 1, start_time=0, length=10)


def test_upload_image_file_progress_callback(tmp_path: Path) -> None:
    """Trigger read callback during upload to cover callback branch.

    NOTE: LLM-generated test -- verify for correctness.
    """
    defs = NodeImageDefinitions(MagicMock())
    image = tmp_path / "stream.qcow2"
    image.write_bytes(b"abcdef")

    def consume_uploaded_file(*_args: object, **kwargs: object) -> MagicMock:
        """Consume one byte from upload stream to exercise read callback."""
        upload_file = kwargs["files"]["field0"][1]
        _ = upload_file.read(1)
        return MagicMock()

    defs._session.post.side_effect = consume_uploaded_file
    defs.upload_image_file(image)
    assert defs._session.post.called


def test_upload_node_def_update() -> None:
    """upload_node_definition with update=True uses PUT.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    defs = NodeImageDefinitions(session)
    session.request.return_value.json.return_value = {"status": "ok"}

    json_result = defs.upload_node_definition({"id": "iosv"}, update=True)
    assert json_result == {"status": "ok"}
    session.request.assert_any_call("PUT", "node_definitions", json={"id": "iosv"})


def test_upload_image_def_create() -> None:
    """upload_image_definition with update=False uses POST.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    defs = NodeImageDefinitions(session)
    session.request.return_value.json.return_value = {"status": "ok"}

    yaml_result = defs.upload_image_definition("id: iosv-1", update=False)
    assert yaml_result == {"status": "ok"}
    session.request.assert_any_call("POST", "image_definitions", content="id: iosv-1")


def test_remove_dropfolder_image() -> None:
    """remove_dropfolder_image deletes image from dropfolder.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    defs = NodeImageDefinitions(session)

    assert defs.remove_dropfolder_image("image.qcow2") is None
    assert session.delete.mock_calls[0].args[0] == "images/manage/image.qcow2"


def test_reload_definitions() -> None:
    """reload_definitions returns report with node and image definition changes.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    defs = NodeImageDefinitions(session)
    expected_report = {
        "node_definitions": {
            "unchanged": ["iosv", "nxosv"],
            "updated": ["asav"],
            "new": ["custom-node"],
            "removed": ["old-node"],
            "failed": [],
        },
        "image_definitions": {
            "unchanged": ["iosv-159-3"],
            "updated": [],
            "new": ["custom-image"],
            "removed": [],
            "failed": ["Error loading bad-image.yaml"],
        },
    }
    session.put.return_value.json.return_value = expected_report

    report = defs.reload_definitions()
    assert report == expected_report
    assert session.put.mock_calls[0].args[0] == defs._URL_TEMPLATES["reload_defs"]


# everything except str or dict is invalid
INVALID_DEFINITIONS: dict[str, Any] = {
    "none": None,
    "bool": True,
    "int": 22,
    "float": 1.0,
    "complex": 1 + 2j,
    "list": ["test"],
    "tuple": ("test",),
    "range": range(2),
    "set": {"test"},
    "bytes": b"test",
    "bytearray": bytearray(2),
    "object": object(),
}


@pytest.fixture(params=list(INVALID_DEFINITIONS))
def invalid_definition(request: pytest.FixtureRequest) -> Any:
    """Provide an invalid definition value for parametrized tests.

    :param request: Pytest fixture request; param selects the invalid type.
    :returns: An invalid value (not str or dict) for definition upload.
    """
    return INVALID_DEFINITIONS[request.param]


@pytest.mark.parametrize(
    "upload_method",
    ["upload_node_definition", "upload_image_definition"],
)
def test_upload_definition_invalid_body(
    client_library: ClientLibrary, invalid_definition: Any, upload_method: str
) -> None:
    """Upload rejects non-str/dict definition bodies with InvalidContentType.

    NOTE: LLM-generated test -- verify for correctness.

    :param client_library: Client library fixture.
    :param invalid_definition: Invalid definition value (parametrized).
    :param upload_method: Upload method name to call.
    """
    with pytest.raises(InvalidContentType):
        getattr(client_library.definitions, upload_method)(invalid_definition)


WRONG_FORMAT_LIST = [
    "",
    ".",
    "file",
    ".text",
    ".qcow2",
    "qcow2",
    "qcow",
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

# pathlib treats ending dot differently since Python 3.14
_TRAILING_DOT_NAMES = [
    ".qcow.",
    "qcow.",
    ".file.",
    "file.qcow.",
]
if sys.version_info >= (3, 14):
    NOT_SUPPORTED_LIST.extend(_TRAILING_DOT_NAMES)
else:
    WRONG_FORMAT_LIST.extend(_TRAILING_DOT_NAMES)


@contextlib.contextmanager
def windows_path(path: str) -> Iterator[None]:
    """Use PureWindowsPath when path contains backslash for cross-platform tests.

    :param path: Path string; if it contains backslash, Path is temporarily Windows.
    :yields: None.
    """
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
    ids=[
        "empty",
        "root",
        "current_unix",
        "parent_unix",
        "relative_unix",
        "absolute_unix",
        "backslash",
        "parent_windows",
        "absolute_windows",
    ],
)
@pytest.mark.parametrize("rename", [None, "rename"])
@pytest.mark.parametrize(
    "test_string",
    WRONG_FORMAT_LIST + NOT_SUPPORTED_LIST + EXPECTED_PASS_LIST,
)
def test_image_upload_file(
    rename: str | None, test_string: str, test_path: str
) -> None:
    """Parametrized test for upload_image_file validation and path handling.

    :param rename: Optional rename suffix; if set, appended to test_string.
    :param test_string: Filename or extension from WRONG_FORMAT/NOT_SUPPORTED/PASS lists.
    :param test_path: Path prefix (empty, root, relative, absolute, Windows-style).
    """
    session = MagicMock()
    nid = NodeImageDefinitions(session)
    filename = test_path + test_string
    if rename is not None:
        rename += test_string

    if test_string in WRONG_FORMAT_LIST:
        with (
            pytest.raises(InvalidImageFile, match="wrong format"),
            windows_path(filename),
        ):
            nid.upload_image_file(filename, rename)
    elif test_string in NOT_SUPPORTED_LIST:
        with (
            pytest.raises(InvalidImageFile, match="unsupported extension"),
            windows_path(filename),
        ):
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
            with (
                pytest.raises(InvalidImageFile, match="does not match source"),
                windows_path(filename),
            ):
                nid.upload_image_file(filename, rename[:-3])
        with pytest.raises(FileNotFoundError), windows_path(filename):
            nid.upload_image_file(filename, rename)
