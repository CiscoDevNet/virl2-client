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

import logging
from typing import TYPE_CHECKING, Any, Literal

from ..exceptions import InvalidProperty
from ..utils import _deprecated_argument, check_stale, get_url_from_template, locked
from ..utils import property_s as property

if TYPE_CHECKING:
    import httpx

    from .lab import Lab

    AnnotationTypeString = Literal["text", "line", "ellipse", "rectangle"]
    AnnotationType = (
        "Annotation"
        | "AnnotationRectangle"
        | "AnnotationEllipse"
        | "AnnotationLine"
        | "AnnotationText"
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


class Annotation:
    _URL_TEMPLATES = {
        "annotations": "labs/{lab_id}/annotations",
        "annotation": "labs/{lab_id}/annotations/{annotation_id}",
    }

    def __init__(
        self,
        lab: Lab,
        annotation_id: str,
        annotation_type: AnnotationTypeString,
    ) -> None:
        """
        A VIRL2 lab annotation.

        :param lab: The lab object to which the link belongs.
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

    def __str__(self):
        return (
            f"{self.__class__.__name__}: {self._id}{' (STALE)' if self._stale else ''}"
        )

    def __repr__(self):
        return (
            f"{self.__class__.__name__}("
            f"{str(self._lab)!r}, "
            f"{self._id!r}, "
            f"{self._type!r})"
        )

    def __eq__(self, other: object):
        if not isinstance(other, Annotation):
            return False
        return self._id == other._id

    def __hash__(self):
        return hash(self._id)

    def _url_for(self, endpoint: str, **kwargs) -> str:
        """
        Generate the URL for a given API endpoint.

        :param endpoint: The desired endpoint.
        :param **kwargs: Keyword arguments used to format the URL.
        :returns: The formatted URL.
        """
        kwargs["lab_id"] = self._lab._id
        kwargs["annotation_id"] = self._id
        return get_url_from_template(endpoint, self._URL_TEMPLATES, kwargs)

    @property
    def id(self) -> str:
        """Return ID of the annotation."""
        return self._id

    @property
    def border_color(self) -> str:
        """Border color (example: `#FF00FF00`)."""
        self._lab.sync_topology_if_outdated()
        return self._border_color

    @border_color.setter
    @locked
    def border_color(self, value: str) -> None:
        """Set border color (example: `#FF00FF00`)."""
        self._set_annotation_property("border_color", value)
        self._border_color = value

    @property
    def border_style(self) -> str:
        """Border style; valid values: '' (solid), '2,2' (dotted), '4,2' (dashed)."""
        self._lab.sync_topology_if_outdated()
        return self._border_style

    @border_style.setter
    @locked
    def border_style(self, value: str) -> None:
        """
        Set border style; valid values: '' (solid), '2,2' (dotted), '4,2' (dashed).
        """
        self._set_annotation_property("border_style", value)
        self._border_style = value

    @property
    def color(self) -> str:
        """Annotation color (example: `#00AAFF`)."""
        self._lab.sync_topology_if_outdated()
        return self._color

    @color.setter
    @locked
    def color(self, value: str) -> None:
        """Set annotation color (example: `#00AAFF`)."""
        self._set_annotation_property("color", value)
        self._color = value

    @property
    def thickness(self) -> int:
        """Annotation border thickness."""
        self._lab.sync_topology_if_outdated()
        return self._thickness

    @thickness.setter
    @locked
    def thickness(self, value: int) -> None:
        """Set annotation border thickness."""
        self._set_annotation_property("thickness", value)
        self._thickness = value

    @property
    def type(self) -> str:
        """Return type of the annotation."""
        return self._type

    @property
    def x1(self) -> int:
        """X1 coordinate."""
        self._lab.sync_topology_if_outdated()
        return self._x1

    @x1.setter
    @locked
    def x1(self, value: int) -> None:
        """Set x1 coordinate."""
        self._set_annotation_property("x1", value)
        self._x1 = value

    @property
    def y1(self) -> int:
        """Y1 coordinate."""
        self._lab.sync_topology_if_outdated()
        return self._y1

    @y1.setter
    @locked
    def y1(self, value: int) -> None:
        """Set y1 coordinate."""
        self._set_annotation_property("y1", value)
        self._y1 = value

    @property
    def z_index(self) -> int:
        """Z layer (depth) of an annotation."""
        self._lab.sync_topology_if_outdated()
        return self._z_index

    @z_index.setter
    @locked
    def z_index(self, value: int) -> None:
        """Set Z layer (depth) of an annotation."""
        self._set_annotation_property("z_index", value)
        self._z_index = value

    @classmethod
    def get_default_property_values(cls, annotation_type: str) -> dict[str, Any]:
        """
        Return a list of all valid properties set to default values for the selected
        annotation type.
        """
        default_values = {}
        for ppty in ANNOTATION_PROPERTY_MAP:
            if ppty == "type":
                continue
            if not ANNOTATION_MAP[annotation_type] & ANNOTATION_PROPERTY_MAP[ppty]:
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
        """Check if the given property is recognized by the selected annotation type."""
        try:
            assert annotation_type in _ANNOTATION_TYPES
            assert _property in ANNOTATION_PROPERTY_MAP
        except AssertionError:
            return False
        return ANNOTATION_MAP[annotation_type] & ANNOTATION_PROPERTY_MAP[_property] > 0

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
        """Remove annotation from the lab."""
        self._lab.remove_annotation(self)

    @check_stale
    def _remove_on_server(self) -> None:
        """Remove annotation on the server side."""
        _LOGGER.info(f"Removing annotation {self}")
        url = self._url_for("annotation")
        self._session.delete(url)

    def update(self, annotation_data: dict[str, Any], push_to_server=None) -> None:
        """
        Update annotation properties.

        :param annotation_data: JSON dict with new annotation property:value pairs.
        :param push_to_server: DEPRECATED: Was only used by internal methods
            and should otherwise always be True.
        """
        _deprecated_argument(self.update, push_to_server, "push_to_server")
        self._update(annotation_data, push_to_server=True)

    @check_stale
    @locked
    def _update(self, annotation_data: dict[str, Any], push_to_server: bool) -> None:
        """
        Update annotation properties.

        :param annotation_data: JSON dict with new annotation property:value pairs.
        :param push_to_server: Whether to push the changes to the server.
        """
        if annotation_data.get("type") not in (None, self._type):
            raise ValueError("Can't change annotation type.")

        # make sure all properties we want to update are valid
        existing_keys = dir(self)
        for key in annotation_data:
            if key not in existing_keys:
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
        _LOGGER.debug(f"Setting annotation property {self} {key}: {val}")
        self._set_annotation_properties({key: val})

    @check_stale
    def _set_annotation_properties(self, annotation_data: dict[str, Any]) -> None:
        """Update annotation properties server-side."""
        self._session.patch(
            url=self._url_for("annotation"), json=annotation_data | {"type": self._type}
        )


# ~~~~~< Annotation subclasses >~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


class AnnotationRectangle(Annotation):
    """
    Annotation class representing rectangle annotation.
    """

    def __init__(
        self,
        lab: Lab,
        annotation_id: str,
        annotation_data: dict[str, Any] | None = None,
    ):
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
        """Border radius."""
        self._lab.sync_topology_if_outdated()
        return self._border_radius

    @border_radius.setter
    @locked
    def border_radius(self, value: int) -> None:
        """Set border radius."""
        self._set_annotation_property("border_radius", value)
        self._border_radius = value

    @property
    def x2(self) -> int:
        """X2 coordinate."""
        self._lab.sync_topology_if_outdated()
        return self._x2

    @x2.setter
    @locked
    def x2(self, value: int) -> None:
        """Set x2 coordinate."""
        self._set_annotation_property("x2", value)
        self._x2 = value

    @property
    def y2(self) -> int:
        """Y2 coordinate."""
        self._lab.sync_topology_if_outdated()
        return self._y2

    @y2.setter
    @locked
    def y2(self, value: int) -> None:
        """Set y2 coordinate."""
        self._set_annotation_property("y2", value)
        self._y2 = value

    @property
    def rotation(self) -> int:
        """Rotation of an object, in degrees."""
        self._lab.sync_topology_if_outdated()
        return self._rotation

    @rotation.setter
    @locked
    def rotation(self, value: int) -> None:
        """Set rotation of an object, in degrees."""
        self._set_annotation_property("rotation", value)
        self._rotation = value


class AnnotationEllipse(Annotation):
    """
    Annotation class representing ellipse annotation.
    """

    def __init__(
        self,
        lab: Lab,
        annotation_id: str,
        annotation_data: dict[str, Any] | None = None,
    ):
        super().__init__(lab, annotation_id, "ellipse")

        # default values
        self._border_color = GREY
        self._color = WHITE
        self._x2 = 100
        self._y2 = 100
        self._rotation = 0
        if annotation_data:
            self._update(annotation_data, push_to_server=False)

    @property
    def x2(self) -> int:
        """X2 coordinate."""
        self._lab.sync_topology_if_outdated()
        return self._x2

    @x2.setter
    @locked
    def x2(self, value: int) -> None:
        """Set x2 coordinate."""
        self._set_annotation_property("x2", value)
        self._x2 = value

    @property
    def y2(self) -> int:
        """Y2 coordinate."""
        self._lab.sync_topology_if_outdated()
        return self._y2

    @y2.setter
    @locked
    def y2(self, value: int) -> None:
        """Set y2 coordinate."""
        self._set_annotation_property("y2", value)
        self._y2 = value

    @property
    def rotation(self) -> int:
        """Rotation of an object, in degrees."""
        self._lab.sync_topology_if_outdated()
        return self._rotation

    @rotation.setter
    @locked
    def rotation(self, value: int) -> None:
        """Set rotation of an object, in degrees."""
        self._set_annotation_property("rotation", value)
        self._rotation = value


class AnnotationLine(Annotation):
    """
    Annotation class representing line annotation.
    """

    def __init__(
        self,
        lab: Lab,
        annotation_id: str,
        annotation_data: dict[str, Any] | None = None,
    ):
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
    def x2(self) -> int:
        """X2 coordinate."""
        self._lab.sync_topology_if_outdated()
        return self._x2

    @x2.setter
    @locked
    def x2(self, value: int) -> None:
        """Set x2 coordinate."""
        self._set_annotation_property("x2", value)
        self._x2 = value

    @property
    def y2(self) -> int:
        """Y2 coordinate."""
        self._lab.sync_topology_if_outdated()
        return self._y2

    @y2.setter
    @locked
    def y2(self, value: int) -> None:
        """Set y2 coordinate."""
        self._set_annotation_property("y2", value)
        self._y2 = value

    @property
    def line_start(self) -> str | None:
        """Line arrow start style."""
        self._lab.sync_topology_if_outdated()
        return self._line_start

    @line_start.setter
    @locked
    def line_start(self, value: str | None) -> None:
        """Set line arrow start style: (arrow, square, circle)."""
        self._set_annotation_property("line_start", value)
        self._line_start = value

    @property
    def line_end(self) -> str | None:
        """Line arrow end style."""
        self._lab.sync_topology_if_outdated()
        return self._line_end

    @line_end.setter
    @locked
    def line_end(self, value: str | None) -> None:
        """Set line arrow end style: (arrow, square, circle)."""
        self._set_annotation_property("line_end", value)
        self._line_end = value


class AnnotationText(Annotation):
    """
    Annotation class representing text annotation.
    """

    def __init__(
        self,
        lab: Lab,
        annotation_id: str,
        annotation_data: dict[str, Any] | None = None,
    ):
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
    def rotation(self) -> int:
        """Rotation of an object, in degrees."""
        self._lab.sync_topology_if_outdated()
        return self._rotation

    @rotation.setter
    @locked
    def rotation(self, value: int) -> None:
        """Set rotation of an object, in degrees."""
        self._set_annotation_property("rotation", value)
        self._rotation = value

    @property
    def text_bold(self) -> bool:
        """Text boldness."""
        self._lab.sync_topology_if_outdated()
        return self._text_bold

    @text_bold.setter
    @locked
    def text_bold(self, value: bool) -> None:
        """Set text boldness (bool)."""
        self._set_annotation_property("text_bold", value)
        self._text_bold = value

    @property
    def text_content(self) -> str:
        """Text annotation content."""
        self._lab.sync_topology_if_outdated()
        return self._text_content

    @text_content.setter
    @locked
    def text_content(self, value: str) -> None:
        """Set text annotation content."""
        self._set_annotation_property("text_content", value)
        self._text_content = value

    @property
    def text_font(self) -> str:
        """Text font."""
        self._lab.sync_topology_if_outdated()
        return self._text_font

    @text_font.setter
    @locked
    def text_font(self, value: str) -> None:
        """Set text font."""
        self._set_annotation_property("text_font", value)
        self._text_font = value

    @property
    def text_italic(self) -> bool:
        """Text cursive."""
        self._lab.sync_topology_if_outdated()
        return self._text_italic

    @text_italic.setter
    @locked
    def text_italic(self, value: bool) -> None:
        """Set text cursive (bool)."""
        self._set_annotation_property("text_italic", value)
        self._text_italic = value

    @property
    def text_size(self) -> int:
        """Size of the text."""
        self._lab.sync_topology_if_outdated()
        return self._text_size

    @text_size.setter
    @locked
    def text_size(self, value: int) -> None:
        """Set size of the text (various units are recognized)."""
        self._set_annotation_property("text_size", value)
        self._text_size = value

    @property
    def text_unit(self) -> str:
        """Text size unit."""
        self._lab.sync_topology_if_outdated()
        return self._text_unit

    @text_unit.setter
    @locked
    def text_unit(self, value: str) -> None:
        """Set text size unit (pt, px, em, ...)."""
        self._set_annotation_property("text_unit", value)
        self._text_unit = value
