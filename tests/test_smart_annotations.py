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
"""Tests for SmartAnnotation properties, server sync, and identity helpers."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from tests.helpers import make_lab
from virl2_client.exceptions import InvalidProperty
from virl2_client.models import SmartAnnotation


def test_smart_annotation_prop_setters() -> None:
    """Property setters loop sets and persists values.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    annotation = SmartAnnotation(lab, "s1")
    annotation._tag = "core"
    property_updates = {
        "is_on": False,
        "label": "L",
        "padding": 10,
        "tag_offset_x": 1,
        "tag_offset_y": 2,
        "tag_size": 20,
        "group_distance": 500,
        "thickness": 3,
        "border_style": "2,2",
        "fill_color": "#33333333",
        "border_color": "#44444444",
        "z_index": 9,
    }

    with patch.object(annotation, "_set_smart_annotation_property", return_value=None):
        for key, value in property_updates.items():
            setattr(annotation, key, value)

    for key, value in property_updates.items():
        assert getattr(annotation, key) == value


def test_smart_annotation_set_props_patches() -> None:
    """_set_smart_annotation_properties patches server.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    annotation = SmartAnnotation(lab, "s1")
    annotation._set_smart_annotation_properties({"label": "srv"})
    lab._session.patch.assert_called_with(
        url="labs/l1/smart_annotations/s1", json={"label": "srv"}
    )


def test_smart_annotation_remove_server() -> None:
    """_remove_on_server removes tags from nodes.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    node = MagicMock()
    annotation = SmartAnnotation(lab, "s1")
    annotation._tag = "core"
    with patch.object(lab, "find_nodes_by_tag", return_value=[node]) as find_nodes:
        annotation._remove_on_server()
        find_nodes.assert_called_once_with("core")
    node._remove_tag_on_server.assert_called_with("core")


def test_smart_annotation_identity() -> None:
    """repr, eq, hash, lab, id, tag, as_dict.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    annotation = SmartAnnotation(lab, "s2")
    annotation._tag = "edge"
    assert "SmartAnnotation(" in repr(annotation)
    assert "SmartAnnotation:" in str(annotation)
    assert (annotation == object()) is False
    assert annotation == SmartAnnotation(lab, "s2")
    assert hash(annotation) == hash("s2")
    assert annotation.lab is lab
    assert annotation.id == "s2"
    assert annotation.tag == "edge"
    assert annotation.as_dict()["id"] == "s2"


def test_smart_annotation_update_delegates() -> None:
    """update delegates to _update.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    annotation = SmartAnnotation(lab, "s2")
    with patch.object(annotation, "_update") as wrapped:
        annotation.update({"label": "new"})
        wrapped.assert_called_once_with({"label": "new"}, push_to_server=True)


def test_smart_annotation_set_prop_patches() -> None:
    """_set_smart_annotation_property triggers PATCH.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    annotation = SmartAnnotation(lab, "s2")
    annotation._set_smart_annotation_property("padding", 12)
    lab._session.patch.assert_called_with(
        url="labs/l1/smart_annotations/s2", json={"padding": 12}
    )


def test_smart_annotation_update_push() -> None:
    """_update with push_to_server calls _set_smart_annotation_properties.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    annotation = SmartAnnotation(lab, "s2")
    with patch.object(annotation, "_set_smart_annotation_properties") as set_props:
        annotation._update({"label": "updated"}, push_to_server=True)
        set_props.assert_called_once()


def test_smart_annotation_update_skips_id() -> None:
    """_update with 'id' key skips it without setting attribute.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    annotation = SmartAnnotation(lab, "s2")
    annotation._update({"id": "changed", "label": "new"}, push_to_server=False)
    assert annotation.id == "s2"
    assert annotation._label == "new"


def test_smart_annotation_invalid_prop() -> None:
    """_update with unknown raises InvalidProperty.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    annotation = SmartAnnotation(lab, "s3")
    with pytest.raises(InvalidProperty):
        annotation._update({"unknown": 1}, push_to_server=False)


def test_smart_annotation_remove_multi_node() -> None:
    """_remove_on_server removes tags from multiple nodes.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    node_1 = Mock()
    node_2 = Mock()
    annotation = SmartAnnotation(lab, "s3")
    annotation._tag = "core"
    with patch.object(lab, "find_nodes_by_tag", return_value=[node_1, node_2]):
        annotation._remove_on_server()
    node_1._remove_tag_on_server.assert_called_once_with("core")
    node_2._remove_tag_on_server.assert_called_once_with("core")


def test_smart_annotation_remove_cleans_lab() -> None:
    """remove from lab and marks stale.

    NOTE: LLM-generated test -- verify for correctness.
    """
    lab = make_lab()
    annotation = SmartAnnotation(lab, "s3")
    lab._smart_annotations["s3"] = annotation
    annotation.remove()
    assert "s3" not in lab._smart_annotations
    assert annotation._stale is True
