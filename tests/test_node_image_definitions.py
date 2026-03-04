"""Tests for NodeImageDefinitions CRUD, upload validation, and progress callbacks."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from virl2_client.exceptions import InvalidImageFile
from virl2_client.models.node_image_definition import (
    EXTENSION_LIST,
    NodeImageDefinitions,
    print_progress_bar,
)


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
    "upload_method,payload",
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
    session.request.return_value.json.return_value = "Success"
    assert getattr(defs, upload_method)(payload) == "Success"


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
    session.request.return_value.json.return_value = "Success"
    assert getattr(defs, upload_method)("yaml-body", update=True) == "Success"


@pytest.mark.parametrize(
    "method,arg",
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
    """remove_dropfolder_image deletes and returns result.

    NOTE: LLM-generated test -- verify for correctness.
    """
    session = MagicMock()
    defs = NodeImageDefinitions(session)
    session.delete.return_value.json.return_value = "Success"
    assert defs.remove_dropfolder_image("x.qcow2") == "Success"


@pytest.mark.parametrize(
    "method,arg",
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
    "rename,exc_type",
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
    session.delete.return_value.json.return_value = {"status": "removed"}

    remove_result = defs.remove_dropfolder_image("image.qcow2")
    assert remove_result == {"status": "removed"}
    assert session.delete.mock_calls[0].args[0] == "images/manage/image.qcow2"
