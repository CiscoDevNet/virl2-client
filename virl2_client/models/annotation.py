#
# This file is part of VIRL 2
# Copyright (c) 2019-2024, Cisco Systems, Inc.
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
from typing import TYPE_CHECKING, Literal, Any, Union

from ..utils import check_stale, get_url_from_template, locked
from ..utils import property_s as property
from ..exceptions import InvalidProperty

if TYPE_CHECKING:
    import httpx

    from .lab import Lab
    AnnotationTypeString = Literal["text", "line", "ellipse", "rectangle"]
    AnnotationType = Union[
        Annotation,
        AnnotationRectangle,
        AnnotationEllipse,
        AnnotationLine,
        AnnotationText,
    ]

_LOGGER = logging.getLogger(__name__)

# map properties to the annotation types by using binary flags array
# ---X: rectangle
# --X-: ellipse
# -X--: line
# X---: text
ANNOTATION_PROPERTY_MAP = {
    "border_color": 0b1111,
    "border_radius": 0b0001,
    "border_style": 0b1111,
    "color": 0b1111,
    "line_end": 0b0100,
    "line_start": 0b0100,
    "rotation": 0b1000,
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
        "rectangle": "#808080FF",
        "ellipse": "#808080FF",
        "line": "#808080FF",
        "text": "#00000000",
    },
    "border_radius": 0,
    "border_style": "",
    "color": {
        "rectangle": "#FFFFFFFF",
        "ellipse": "#FFFFFFFF",
        "line": "#FFFFFFFF",
        "text": "#808080FF",
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

ANNOTATION_PROPERTIES_DOCSTRINGS = {
    "border_color": "border color (example: `#FF00FF00`)",
    "border_radius": "border radius",
    "border_style": "valid values: '' (solid), '2,2' (dotted), '4,2' (dashed)",
    "color": "Annotation color (example: `#00AAFF`)",
    "line_end": "line arror start style: (arrow, square, circle)",
    "line_start": "line arror end style: (arrow, square, circle)",
    "rotation": "Rotation of an object, in degrees.",
    "text_bold": "text boldness (bool)",
    "text_content": "Actual text annotation content",
    "text_font": "text font",
    "text_italic": "text cursive (bool)",
    "text_size": "Size of the text (various units are recognized.)",
    "text_unit": "text size unit (pt, px, em, ...)",
    "thickness": "annotation thickness",
    "x1": "x1 coordinate",
    "x2": "x2 coordinate",
    "y1": "y1 coordinate",
    "y2": "y2 coordinate",
    "z_index": "Z layer (depth) of an annotation",
}
ANNOTATION_TYPES = ["text", "line", "ellipse", "rectangle"]


class Annotation:
    _URL_TEMPLATES = {
        "annotations": "labs/{lab_id}/annotations",
        "annotation": "labs/{lab_id}/annotations/{annotation_id}",
    }

    def __init__(self, lab: Lab, annotation_id: str, annotation_type: str) -> None:
        """
        A VIRL2 lab annotation.

        :param lab: The lab object to which the link belongs.
        :param annotation_id: The ID of the annotation.
        :param annotation_type: annotation type (text, line, ellipse, rectangle)
        """
        self._id = annotation_id
        self._lab = lab
        self._type = annotation_type
        self._session: httpx.Client = lab._session
        # When the annotationis removed on the server, this annotation object is marked
        # stale and can no longer be interacted with - the user should discard it
        self._stale = False

        # set all properties (private only)
        for ppty in ANNOTATION_PROPERTY_MAP:
            if ppty == "type":
                continue
            ppty_default = ANNOTATION_PROPERTIES_DEFAULTS[ppty]
            if isinstance(ppty_default, dict):
                ppty_default = ppty_default[annotation_type]
            setattr(self, f"_{ppty}", ppty_default)

    def __str__(self):
        return f"Annotation: {self._id}{' (STALE)' if self._stale else ''}"

    def __repr__(self):
        return "{}({!r}, {!r})".format(
            self.__class__.__name__,
            str(self._lab),
            self._id,
        )

    def __eq__(self, other: object):
        if not isinstance(other, Annotation):
            return False
        return self._id == other._id

    def __hash__(self):
        return hash(self._id)

    def _url_for(self, endpoint, **kwargs):
        """
        Generate the URL for a given API endpoint.

        :param endpoint: The desired endpoint.
        :param **kwargs: Keyword arguments used to format the URL.
        :returns: The formatted URL.
        """
        kwargs["lab_id"] = self._lab._id
        kwargs["annotation_id"] = self._id
        return get_url_from_template(endpoint, self._URL_TEMPLATES, kwargs)

    @classmethod
    def _get_default_property_values(cls, annotation_type: str) -> dict[str, Any]:
        """
        Return list of all valid properties for selected annotation type
        """
        default_values = {}
        annotation_map = {
            "text": 0b1000,
            "line": 0b0100,
            "ellipse": 0b0010,
            "rectangle": 0b0001,
        }
        for ppty in ANNOTATION_PROPERTY_MAP:
            if ppty == "type":
                continue
            if not annotation_map[annotation_type] & ANNOTATION_PROPERTY_MAP[ppty]:
                continue
            ppty_default = ANNOTATION_PROPERTIES_DEFAULTS[ppty]
            if isinstance(ppty_default, dict):
                ppty_default = ppty_default[annotation_type]
            default_values[ppty] = ppty_default

        return default_values

    @classmethod
    def _is_valid_property(
        cls,
        annotation_type: AnnotationTypeString | AnnotationType,
        _property: str,
    ) -> bool:
        """
        Checks if given property is recognized by selected annotation type
        """
        assert annotation_type in ANNOTATION_TYPES
        assert _property in ANNOTATION_PROPERTY_MAP
        annotation_map = {
            "text": 0b1000,
            "line": 0b0100,
            "ellipse": 0b0010,
            "rectangle": 0b0001,
        }
        return annotation_map[annotation_type] & ANNOTATION_PROPERTY_MAP[_property]

    @property
    def id(self) -> str:
        """Return ID of the annotation."""
        return self._id

    @property
    def type(self) -> str:
        """Return type of the annotation."""
        return self._type

    # TODO
    #@locked
    #def as_dict(self) -> dict[str, str]:
    #    """
    #    Convert the annotation object to a dictionary representation.

    #    :returns: A dictionary representation of the annotation object.
    #    """
    #    return {
    #        "id": self.id,
    #        "interface_a": self.interface_a.id,
    #        "interface_b": self.interface_b.id,
    #    }

    def remove(self):
        """Remove the annotation from the lab."""
        self._lab.remove_annotation(self)

    @check_stale
    def _remove_on_server(self) -> None:
        _LOGGER.info(f"Removing annotation {self}")
        url = self._url_for("annotation")
        self._session.delete(url)

    @check_stale
    @locked
    def update(
        self,
        annotation_data: dict[str, Any],
        push_to_server: bool = False,
    ) -> None:
        """
        Update annotation properties.

        :param annotation_data: JSON dict with new annotation property:value pairs.
        :param push_to_server: Whether to update the annotation on the server side too.
        """
        annotation_data["type"] = self._type

        # make sure all properties we want to update are valid
        for key, value in annotation_data.items():
            if key not in dir(self):
                raise InvalidProperty(f"Invalid annotation property: {key}")

        if push_to_server:
            self._set_annotation_properties(annotation_data)

        for key, value in annotation_data.items():
            setattr(self, f"_{key}", value)

    def _set_annotation_property(self, key: str, val: Any) -> None:
        _LOGGER.debug("Setting annotation property %s %s: %s", self, key, val)
        self._set_annotation_properties({key: val})

    @check_stale
    def _set_annotation_properties(self, annotation_data: dict[str, Any]) -> None:
        self._session.patch(url=self._url_for("annotation"), json=annotation_data)


# ~~~~~< Annotation subclasses >~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


class AnnotationRectangle(Annotation):
    def __init__(self, lab: Lab, annotation_id: str, annotation_data: dict[str, Any]):
        super().__init__(lab, annotation_id, "rectangle")
        self.update(annotation_data)


class AnnotationEllipse(Annotation):
    def __init__(self, lab: Lab, annotation_id: str, annotation_data: dict[str, Any]):
        super().__init__(lab, annotation_id, "ellipse")
        self.update(annotation_data)


class AnnotationLine(Annotation):
    def __init__(self, lab: Lab, annotation_id: str, annotation_data: dict[str, Any]):
        super().__init__(lab, annotation_id, "line")
        self.update(annotation_data)


class AnnotationText(Annotation):
    def __init__(self, lab: Lab, annotation_id: str, annotation_data: dict[str, Any]):
        super().__init__(lab, annotation_id, "text")
        self.update(annotation_data)


# ~~~~~< setup Annotation Classes ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


def annotation_property_getter(_property: str) -> Any:
    def sync_and_get(self, ppty):
        self._lab.sync_topology_if_outdated()
        return self.__dict__[f"_{ppty}"]
    return lambda self: sync_and_get(self, _property)


def annotation_property_setter(_property: str) -> None:
    return lambda self, value: self.update(
        annotation_data={_property: value},
        push_to_server=True,
    )


def annotation_property_doc(_property: str) -> None:
    return ANNOTATION_PROPERTIES_DOCSTRINGS[_property]


def set_annotation_properties(
    annotation_class: Type[AnnotationType],
    _type: AnnotationTypeString,
) -> None:
    """Dynamically generate annotation properties based on it's type."""
    for ppty in ANNOTATION_PROPERTY_MAP:
        if ppty == "type":
            continue
        if annotation_class._is_valid_property(_type, ppty):
            setattr(
                annotation_class,
                ppty,
                property(
                    fget=annotation_property_getter(ppty),
                    fset=annotation_property_setter(ppty),
                    doc=annotation_property_doc(ppty),
                )
            )

set_annotation_properties(AnnotationRectangle, "rectangle")
set_annotation_properties(AnnotationEllipse, "ellipse")
set_annotation_properties(AnnotationLine, "line")
set_annotation_properties(AnnotationText, "text")

ANNOTATION_TYPES_CLASSES = [
    AnnotationRectangle,
    AnnotationEllipse,
    AnnotationLine,
    AnnotationText,
]
