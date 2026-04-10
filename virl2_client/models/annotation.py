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
from typing import TYPE_CHECKING, Any, Literal, TypeAlias

from ..exceptions import InvalidProperty
from ..utils import check_stale, get_url_from_template, locked
from ..utils import property_s as property

if TYPE_CHECKING:
    import httpx

    from .lab import Lab

    AnnotationTypeString = Literal["text", "line", "ellipse", "rectangle"]
    AnnotationType: TypeAlias = (
        "AnnotationRectangle | AnnotationEllipse | AnnotationLine | AnnotationText"
    )

_LOGGER = logging.getLogger(__name__)

GREY = "#808080FF"
WHITE = "#FFFFFFFF"
TRANSPARENT = "#00000000"
# map properties to the annotation types by using binary flags array
# ---X: rectangle
# --X-: ellipse
# -X--: line
# X---: text
ANNOTATION_MAP = {
    "text": 0b1000,
    "line": 0b0100,
    "ellipse": 0b0010,
    "rectangle": 0b0001,
}
ANNOTATION_PROPERTY_MAP = {
    "border_color": 0b1111,
    "border_radius": 0b0001,
    "border_style": 0b1111,
    "color": 0b1111,
    "line_end": 0b0100,
    "line_start": 0b0100,
    "rotation": 0b1011,
    "text_bold": 0b1000,
    "text_content": 0b1000,
    "text_font": 0b1000,
    "text_italic": 0b1000,
    "text_size": 0b1000,
    "text_unit": 0b1000,
    "thickness": 0b1111,
    "type": 0b1111,
    "x1": 0b1111,
    "x2": 0b0111,
    "y1": 0b1111,
    "y2": 0b0111,
    "z_index": 0b1111,
}

ANNOTATION_PROPERTIES_DEFAULTS = {
    "border_color": {
        "rectangle": GREY,
        "ellipse": GREY,
        "line": GREY,
        "text": TRANSPARENT,
    },
    "border_radius": 0,
    "border_style": "",
    "color": {
        "rectangle": WHITE,
        "ellipse": WHITE,
        "line": WHITE,
        "text": GREY,
    },
    "line_end": None,
    "line_start": None,
    "rotation": 0,
    "text_bold": False,
    "text_content": "text annotation",
    "text_font": "monospace",
    "text_italic": False,
    "text_size": 12,
    "text_unit": "pt",
    "thickness": 1,
    "x1": 0,
    "x2": 100,
    "y1": 0,
    "y2": 100,
    "z_index": 0,
}

_ANNOTATION_TYPES = ["text", "line", "ellipse", "rectangle"]


class _CoordinateXY2Mixin:
    """Mixin providing x2/y2 coordinate properties for annotation subclasses."""

    @property
    def x2(self) -> int:
        """X2 coordinate.

        :returns: The x2 coordinate value.
        """
        self._lab.sync_topology_if_outdated()
        return self._x2

    @x2.setter
    @locked
    def x2(self, value: int) -> None:
        """Set x2 coordinate.

        :param value: The x2 coordinate value to set.
        """
        self._set_annotation_property("x2", value)
        self._x2 = value

    @property
    def y2(self) -> int:
        """Y2 coordinate.

        :returns: The y2 coordinate value.
        """
        self._lab.sync_topology_if_outdated()
        return self._y2

    @y2.setter
    @locked
    def y2(self, value: int) -> None:
        """Set y2 coordinate.

        :param value: The y2 coordinate value to set.
        """
        self._set_annotation_property("y2", value)
        self._y2 = value


class _RotationMixin:
    """Mixin providing rotation property for annotation subclasses."""

    @property
    def rotation(self) -> int:
        """Rotation of an object, in degrees.

        :returns: The rotation value in degrees.
        """
        self._lab.sync_topology_if_outdated()
        return self._rotation

    @rotation.setter
    @locked
    def rotation(self, value: int) -> None:
        """Set rotation of an object, in degrees.

        :param value: The rotation value in degrees to set.
        """
        self._set_annotation_property("rotation", value)
        self._rotation = value


class Annotation:
    """Base class for VIRL2 lab annotations (text, line, ellipse, rectangle)."""

    _URL_TEMPLATES = {
        "annotations": "labs/{lab_id}/annotations",
        "annotation": "labs/{lab_id}/annotations/{annotation_id}",
    }

    _VALID_KEYS: frozenset[str] = frozenset(
        {
            "id",
            "type",
            "border_color",
            "border_style",
            "color",
            "thickness",
            "x1",
            "y1",
            "z_index",
        }
    )

    def __init__(
        self,
        lab: Lab,
        annotation_id: str,
        annotation_type: AnnotationTypeString,
    ) -> None:
        """
        A VIRL2 lab annotation.

        :param lab: The lab object to which the annotation belongs.
        :param annotation_id: The ID of the annotation.
        :param annotation_type: annotation type (text, line, ellipse, rectangle)
        """
        self._id = annotation_id
        self._lab = lab
        self._session: httpx.Client = lab._session
        # When the annotation is removed on the server, this annotation object is marked
        # stale and can no longer be interacted with - the user should discard it
        self._stale = False

        # set properties required by all annotations
        # values set to 'None' have type-specific default values
        self._border_color = None
        self._border_style = ""
        self._color = None
        self._thickness = 1
        self._type = annotation_type
        self._x1 = 0
        self._y1 = 0
        self._z_index = 0

    def __str__(self) -> str:
        """Return user-friendly annotation description.

        :returns: Annotation id with stale marker when applicable.
        """
        return (
            f"{self.__class__.__name__}: {self._id}{' (STALE)' if self._stale else ''}"
        )

    def __repr__(self) -> str:
        """Return debug representation for this annotation.

        :returns: Representation containing lab, id, and annotation type.
        """
        return (
            f"{self.__class__.__name__}("
            f"{str(self._lab)!r}, "
            f"{self._id!r}, "
            f"{self._type!r})"
        )

    def __eq__(self, other: object) -> bool:
        """Compare annotations by identifier.

        :param other: Object to compare against.
        :returns: True when other is an annotation with same id.
        """
        if not isinstance(other, Annotation):
            return False
        return self._id == other._id

    def __hash__(self) -> int:
        """Return hash based on annotation identifier.

        :returns: Stable hash value for this annotation id.
        """
        return hash(self._id)

    def _url_for(self, endpoint: str, **kwargs: str) -> str:
        """
        Generate the URL for a given API endpoint.

        :param endpoint: The desired endpoint.
        :param kwargs: Keyword arguments used to format the URL.
        :returns: The formatted URL.
        """
        kwargs["lab_id"] = self._lab._id
        kwargs["annotation_id"] = self._id
        return get_url_from_template(endpoint, self._URL_TEMPLATES, kwargs)

    @property
    def id(self) -> str:
        """Return ID of the annotation.

        :returns: The annotation ID.
        """
        return self._id

    @property
    def border_color(self) -> str:
        """Border color (example: #FF00FF00).

        :returns: The border color string.
        """
        self._lab.sync_topology_if_outdated()
        return self._border_color

    @border_color.setter
    @locked
    def border_color(self, value: str) -> None:
        """Set border color (example: #FF00FF00).

        :param value: The border color string to set.
        """
        self._set_annotation_property("border_color", value)
        self._border_color = value

    @property
    def border_style(self) -> str:
        """Border style; valid values: '' (solid), '2,2' (dotted), '4,2' (dashed).

        :returns: The border style string.
        """
        self._lab.sync_topology_if_outdated()
        return self._border_style

    @border_style.setter
    @locked
    def border_style(self, value: str) -> None:
        """Set border style; valid values: '' (solid), '2,2' (dotted), '4,2' (dashed).

        :param value: The border style string to set.
        """
        self._set_annotation_property("border_style", value)
        self._border_style = value

    @property
    def color(self) -> str:
        """Annotation color (example: #00AAFF).

        :returns: The color string.
        """
        self._lab.sync_topology_if_outdated()
        return self._color

    @color.setter
    @locked
    def color(self, value: str) -> None:
        """Set annotation color (example: #00AAFF).

        :param value: The color string to set.
        """
        self._set_annotation_property("color", value)
        self._color = value

    @property
    def thickness(self) -> int:
        """Annotation border thickness.

        :returns: The thickness value.
        """
        self._lab.sync_topology_if_outdated()
        return self._thickness

    @thickness.setter
    @locked
    def thickness(self, value: int) -> None:
        """Set annotation border thickness.

        :param value: The thickness value to set.
        """
        self._set_annotation_property("thickness", value)
        self._thickness = value

    @property
    def type(self) -> str:
        """Return type of the annotation.

        :returns: The annotation type (text, line, ellipse, rectangle).
        """
        return self._type

    @property
    def x1(self) -> int:
        """X1 coordinate.

        :returns: The x1 coordinate value.
        """
        self._lab.sync_topology_if_outdated()
        return self._x1

    @x1.setter
    @locked
    def x1(self, value: int) -> None:
        """Set x1 coordinate.

        :param value: The x1 coordinate value to set.
        """
        self._set_annotation_property("x1", value)
        self._x1 = value

    @property
    def y1(self) -> int:
        """Y1 coordinate.

        :returns: The y1 coordinate value.
        """
        self._lab.sync_topology_if_outdated()
        return self._y1

    @y1.setter
    @locked
    def y1(self, value: int) -> None:
        """Set y1 coordinate.

        :param value: The y1 coordinate value to set.
        """
        self._set_annotation_property("y1", value)
        self._y1 = value

    @property
    def z_index(self) -> int:
        """Z layer (depth) of an annotation.

        :returns: The z_index value.
        """
        self._lab.sync_topology_if_outdated()
        return self._z_index

    @z_index.setter
    @locked
    def z_index(self, value: int) -> None:
        """Set Z layer (depth) of an annotation.

        :param value: The z_index value to set.
        """
        self._set_annotation_property("z_index", value)
        self._z_index = value

    @classmethod
    def get_default_property_values(cls, annotation_type: str) -> dict[str, Any]:
        """
        Return a list of all valid properties set to default values for the selected
        annotation type.

        :param annotation_type: The annotation type (text, line, ellipse, rectangle).
        :returns: A dictionary of property names to default values for the type.
        """
        default_values = {}
        for ppty in ANNOTATION_PROPERTY_MAP:
            if ppty == "type":
                continue
            if not cls._is_property_valid_for_type(annotation_type, ppty):
                continue
            ppty_default = ANNOTATION_PROPERTIES_DEFAULTS[ppty]
            if isinstance(ppty_default, dict):
                ppty_default = ppty_default[annotation_type]
            default_values[ppty] = ppty_default

        return default_values

    @classmethod
    def is_valid_property(
        cls,
        annotation_type: AnnotationTypeString,
        _property: str,
    ) -> bool:
        """Check if the given property is recognized by the selected annotation type.

        :param annotation_type: The annotation type (text, line, ellipse, rectangle).
        :param _property: The property name to validate.
        :returns: True if the property is valid for the given type, False otherwise.
        """
        return (
            annotation_type in _ANNOTATION_TYPES
            and _property in ANNOTATION_PROPERTY_MAP
            and cls._is_property_valid_for_type(annotation_type, _property)
        )

    @classmethod
    def _is_property_valid_for_type(
        cls, annotation_type: AnnotationTypeString, _property: str
    ) -> bool:
        return bool(
            ANNOTATION_MAP[annotation_type] & ANNOTATION_PROPERTY_MAP[_property]
        )

    @locked
    def as_dict(self) -> dict[str, Any]:
        """
        Convert the annotation object to a dictionary representation.

        :returns: A dictionary representation of the annotation object.
        """
        return {
            "id": self._id,
            **{
                ppty: getattr(self, ppty)
                for ppty in ANNOTATION_PROPERTY_MAP
                if Annotation.is_valid_property(self._type, ppty)
            },
        }

    def remove(self) -> None:
        """Remove annotation from the lab.

        Delegates to the lab's remove_annotation method.
        :raises: Exceptions raised by the lab's remove_annotation implementation.
        """
        self._lab.remove_annotation(self)

    @check_stale
    def _remove_on_server(self) -> None:
        """Remove annotation on the server side."""
        _LOGGER.info("Removing annotation %s", self)
        url = self._url_for("annotation")
        self._session.delete(url)

    def update(self, annotation_data: dict[str, Any]) -> None:
        """Update annotation properties.

        :param annotation_data: JSON dict with new annotation property:value pairs.
        :raises ValueError: If annotation type is changed.
        :raises InvalidProperty: If an invalid property key is provided.
        """
        self._update(annotation_data, push_to_server=True)

    @check_stale
    @locked
    def _update(self, annotation_data: dict[str, Any], push_to_server: bool) -> None:
        """
        Update annotation properties.

        :param annotation_data: JSON dict with new annotation property:value pairs.
        :param push_to_server: Whether to push the changes to the server.
        :raises ValueError: If annotation type is changed.
        :raises InvalidProperty: If an invalid property key is provided.
        """
        if annotation_data.get("type") not in (None, self._type):
            raise ValueError("Can't change annotation type.")

        # make sure all properties we want to update are valid
        for key in annotation_data:
            if key not in self._VALID_KEYS:
                raise InvalidProperty(f"Invalid annotation property: {key}")

        if push_to_server:
            self._set_annotation_properties(annotation_data)

        # update locally
        for key, value in annotation_data.items():
            if key == "id":
                continue
            setattr(self, f"_{key}", value)

    def _set_annotation_property(self, key: str, val: Any) -> None:
        """
        Set a property of the annotation.

        :param key: The name of the property to set.
        :param val: The value to set.
        """
        _LOGGER.debug("Setting annotation property %s %s: %s", self, key, val)
        self._set_annotation_properties({key: val})

    @check_stale
    def _set_annotation_properties(self, annotation_data: dict[str, Any]) -> None:
        """
        Update annotation properties server-side.

        :param annotation_data: JSON dict with property:value pairs to patch.
        """
        self._session.patch(
            url=self._url_for("annotation"), json=annotation_data | {"type": self._type}
        )


# ~~~~~< Annotation subclasses >~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


class AnnotationRectangle(_CoordinateXY2Mixin, _RotationMixin, Annotation):
    """
    Annotation class representing rectangle annotation.
    """

    _VALID_KEYS = Annotation._VALID_KEYS | frozenset(
        {"border_radius", "x2", "y2", "rotation"}
    )

    def __init__(
        self,
        lab: Lab,
        annotation_id: str,
        annotation_data: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize a rectangle annotation.

        :param lab: The lab object to which the annotation belongs.
        :param annotation_id: The ID of the annotation.
        :param annotation_data: Optional initial property data from the server.
        """
        super().__init__(lab, annotation_id, "rectangle")

        # default values
        self._border_color = GREY
        self._border_radius = 0
        self._color = WHITE
        self._x2 = 100
        self._y2 = 100
        self._rotation = 0
        if annotation_data:
            self._update(annotation_data, push_to_server=False)

    @property
    def border_radius(self) -> int:
        """Border radius.

        :returns: The border radius value.
        """
        self._lab.sync_topology_if_outdated()
        return self._border_radius

    @border_radius.setter
    @locked
    def border_radius(self, value: int) -> None:
        """Set border radius.

        :param value: The border radius value to set.
        """
        self._set_annotation_property("border_radius", value)
        self._border_radius = value


class AnnotationEllipse(_CoordinateXY2Mixin, _RotationMixin, Annotation):
    """
    Annotation class representing ellipse annotation.
    """

    _VALID_KEYS = Annotation._VALID_KEYS | frozenset({"x2", "y2", "rotation"})

    def __init__(
        self,
        lab: Lab,
        annotation_id: str,
        annotation_data: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize an ellipse annotation.

        :param lab: The lab object to which the annotation belongs.
        :param annotation_id: The ID of the annotation.
        :param annotation_data: Optional initial property data from the server.
        """
        super().__init__(lab, annotation_id, "ellipse")

        # default values
        self._border_color = GREY
        self._color = WHITE
        self._x2 = 100
        self._y2 = 100
        self._rotation = 0
        if annotation_data:
            self._update(annotation_data, push_to_server=False)


class AnnotationLine(_CoordinateXY2Mixin, Annotation):
    """
    Annotation class representing line annotation.
    """

    _VALID_KEYS = Annotation._VALID_KEYS | frozenset(
        {"x2", "y2", "line_start", "line_end"}
    )

    def __init__(
        self,
        lab: Lab,
        annotation_id: str,
        annotation_data: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize a line annotation.

        :param lab: The lab object to which the annotation belongs.
        :param annotation_id: The ID of the annotation.
        :param annotation_data: Optional initial property data from the server.
        """
        super().__init__(lab, annotation_id, "line")

        # default values
        self._border_color = GREY
        self._color = WHITE
        self._x2 = 100
        self._y2 = 100
        self._line_start = None
        self._line_end = None
        if annotation_data:
            self._update(annotation_data, push_to_server=False)

    @property
    def line_start(self) -> str | None:
        """Line arrow start style.

        :returns: The line start style (arrow, square, circle) or None.
        """
        self._lab.sync_topology_if_outdated()
        return self._line_start

    @line_start.setter
    @locked
    def line_start(self, value: str | None) -> None:
        """Set line arrow start style: (arrow, square, circle).

        :param value: The line start style to set, or None.
        """
        self._set_annotation_property("line_start", value)
        self._line_start = value

    @property
    def line_end(self) -> str | None:
        """Line arrow end style.

        :returns: The line end style (arrow, square, circle) or None.
        """
        self._lab.sync_topology_if_outdated()
        return self._line_end

    @line_end.setter
    @locked
    def line_end(self, value: str | None) -> None:
        """Set line arrow end style: (arrow, square, circle).

        :param value: The line end style to set, or None.
        """
        self._set_annotation_property("line_end", value)
        self._line_end = value


class AnnotationText(_RotationMixin, Annotation):
    """
    Annotation class representing text annotation.
    """

    _VALID_KEYS = Annotation._VALID_KEYS | frozenset(
        {
            "x2",
            "y2",
            "rotation",
            "text_bold",
            "text_content",
            "text_font",
            "text_italic",
            "text_size",
            "text_unit",
        }
    )

    def __init__(
        self,
        lab: Lab,
        annotation_id: str,
        annotation_data: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize a text annotation.

        :param lab: The lab object to which the annotation belongs.
        :param annotation_id: The ID of the annotation.
        :param annotation_data: Optional initial property data from the server.
        """
        super().__init__(lab, annotation_id, "text")

        # default values
        self._border_color = TRANSPARENT
        self._color = GREY
        self._x2 = 100
        self._y2 = 100
        self._rotation = 0
        self._text_bold = False
        self._text_content = "text annotation"
        self._text_font = "monospace"
        self._text_italic = False
        self._text_size = 12
        self._text_unit = "pt"
        if annotation_data:
            self._update(annotation_data, push_to_server=False)

    @property
    def text_bold(self) -> bool:
        """Text boldness.

        :returns: True if text is bold, False otherwise.
        """
        self._lab.sync_topology_if_outdated()
        return self._text_bold

    @text_bold.setter
    @locked
    def text_bold(self, value: bool) -> None:
        """Set text boldness.

        :param value: True for bold, False otherwise.
        """
        self._set_annotation_property("text_bold", value)
        self._text_bold = value

    @property
    def text_content(self) -> str:
        """Text annotation content.

        :returns: The text content string.
        """
        self._lab.sync_topology_if_outdated()
        return self._text_content

    @text_content.setter
    @locked
    def text_content(self, value: str) -> None:
        """Set text annotation content.

        :param value: The text content string to set.
        """
        self._set_annotation_property("text_content", value)
        self._text_content = value

    @property
    def text_font(self) -> str:
        """Text font.

        :returns: The font name string.
        """
        self._lab.sync_topology_if_outdated()
        return self._text_font

    @text_font.setter
    @locked
    def text_font(self, value: str) -> None:
        """Set text font.

        :param value: The font name string to set.
        """
        self._set_annotation_property("text_font", value)
        self._text_font = value

    @property
    def text_italic(self) -> bool:
        """Text italic/cursive.

        :returns: True if text is italic, False otherwise.
        """
        self._lab.sync_topology_if_outdated()
        return self._text_italic

    @text_italic.setter
    @locked
    def text_italic(self, value: bool) -> None:
        """Set text italic/cursive.

        :param value: True for italic, False otherwise.
        """
        self._set_annotation_property("text_italic", value)
        self._text_italic = value

    @property
    def text_size(self) -> int:
        """Size of the text.

        :returns: The text size value.
        """
        self._lab.sync_topology_if_outdated()
        return self._text_size

    @text_size.setter
    @locked
    def text_size(self, value: int) -> None:
        """Set size of the text (various units are recognized).

        :param value: The text size value to set.
        """
        self._set_annotation_property("text_size", value)
        self._text_size = value

    @property
    def text_unit(self) -> str:
        """Text size unit.

        :returns: The text size unit string (pt, px, em, etc.).
        """
        self._lab.sync_topology_if_outdated()
        return self._text_unit

    @text_unit.setter
    @locked
    def text_unit(self, value: str) -> None:
        """Set text size unit (pt, px, em, ...).

        :param value: The unit string to set.
        """
        self._set_annotation_property("text_unit", value)
        self._text_unit = value
