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
"""Tests for annotation subclasses (rectangle, ellipse, line, text) and server sync."""

from typing import Any
from unittest.mock import patch

import pytest
from helpers import make_lab

from virl2_client.exceptions import InvalidProperty
from virl2_client.models.annotation import (
    Annotation,
    AnnotationEllipse,
    AnnotationLine,
    AnnotationRectangle,
    AnnotationText,
)


@pytest.mark.parametrize(
    ("cls", "extra_updates"),
    [
        (AnnotationRectangle, {"border_radius": 5, "x2": 11, "y2": 12, "rotation": 15}),
        (AnnotationEllipse, {"x2": 11, "y2": 12, "rotation": 15}),
        (
            AnnotationLine,
            {"x2": 11, "y2": 12, "line_start": "arrow", "line_end": "circle"},
        ),
        (
            AnnotationText,
            {
                "rotation": 15,
                "text_bold": True,
                "text_content": "hello",
                "text_font": "serif",
                "text_italic": True,
                "text_size": 16,
                "text_unit": "px",
            },
        ),
    ],
)
def test_annotation_subclass_setters(
    cls: type[Any], extra_updates: dict[str, Any]
) -> None:
    """Verify annotation subclass property setters and base property inheritance.

    NOTE: LLM-generated test -- verify for correctness.

    :param cls: Annotation subclass (Rectangle, Ellipse, Line, or Text).
    :param extra_updates: Subclass-specific properties to set and assert.
    """
    lab = make_lab()
    annotation = cls(lab, "a1")
    base_updates = {
        "border_color": "#11111111",
        "border_style": "2,2",
        "color": "#22222222",
        "thickness": 2,
        "x1": 3,
        "y1": 4,
        "z_index": 7,
    }

    with patch.object(annotation, "_set_annotation_property", return_value=None):
        for key, value in base_updates.items():
            setattr(annotation, key, value)
        for key, value in extra_updates.items():
            setattr(annotation, key, value)
            assert getattr(annotation, key) == value

    for key, value in base_updates.items():
        assert getattr(annotation, key) == value


def test_annotation_set_props_patches() -> None:
    """_set_annotation_properties patches server with payload and type.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    annotation = AnnotationRectangle(lab, "a1")
    annotation._set_annotation_properties({"x1": 100})
    lab._session.patch.assert_called_with(
        url="labs/l1/annotations/a1", json={"x1": 100, "type": "rectangle"}
    )


def test_annotation_remove_on_server() -> None:
    """_remove_on_server calls delete on annotation URL.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    annotation = AnnotationRectangle(lab, "a1")
    annotation._remove_on_server()
    lab._session.delete.assert_called_with("labs/l1/annotations/a1")


def test_annotation_repr() -> None:
    """repr includes class name.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    annotation = AnnotationRectangle(lab, "a9")
    assert "AnnotationRectangle(" in repr(annotation)


def test_annotation_equality() -> None:
    """eq with same-type and non-annotation.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    annotation = AnnotationRectangle(lab, "a9")
    assert annotation == AnnotationRectangle(lab, "a9")
    assert (annotation == object()) is False


def test_annotation_hash() -> None:
    """hash equals hash of id.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    annotation = AnnotationRectangle(lab, "a9")
    assert hash(annotation) == hash("a9")


def test_annotation_type_and_as_dict() -> None:
    """type property and as_dict includes id.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    annotation = AnnotationRectangle(lab, "a9")
    assert annotation.type == "rectangle"
    assert annotation.as_dict()["id"] == "a9"


def test_annotation_set_property_patches() -> None:
    """_set_annotation_property triggers PATCH.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    annotation = AnnotationRectangle(lab, "a9")
    annotation._set_annotation_property("x1", 44)
    lab._session.patch.assert_called_with(
        url="labs/l1/annotations/a9", json={"x1": 44, "type": "rectangle"}
    )


def test_annotation_default_prop_values() -> None:
    """get_default_property_values returns type-specific defaults.

    NOTE: LLM-generated test -- verify for correctness.
    """
    defaults = Annotation.get_default_property_values("text")
    assert "text_content" in defaults
    assert "x2" not in defaults


@pytest.mark.parametrize(
    ("annotation_type", "prop", "expected"),
    [
        ("line", "line_start", True),
        ("text", "line_start", False),
        ("text", "unknown_key", False),
    ],
)
def test_annotation_is_valid_property(
    annotation_type: str, prop: str, expected: bool
) -> None:
    """is_valid_property returns True/False per type and key.

    NOTE: LLM-generated test -- verify for correctness.
    """
    assert Annotation.is_valid_property(annotation_type, prop) is expected


@pytest.mark.parametrize(
    ("payload", "exc_type", "match"),
    [
        ({"type": "text"}, ValueError, "Can't change annotation type"),
        ({"invalid": 1}, InvalidProperty, None),
    ],
)
def test_annotation_update_guards(
    payload: dict[str, Any],
    exc_type: type[Exception],
    match: str | None,
) -> None:
    """_update raises for type change or invalid property.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    annotation = AnnotationRectangle(lab, "a10")
    with pytest.raises(exc_type, match=match):
        annotation._update(payload, push_to_server=False)


def test_annotation_update_succeeds() -> None:
    """update with valid x1 applies changes.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    annotation = AnnotationRectangle(lab, "a10")
    annotation.update({"x1": 1})
    assert annotation.x1 == 1


def test_annotation_remove_delegates() -> None:
    """remove delegates to lab and marks stale.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    annotation = AnnotationRectangle(lab, "a10")
    lab._annotations["a10"] = annotation
    annotation.remove()
    assert "a10" not in lab._annotations
    assert annotation._stale is True
