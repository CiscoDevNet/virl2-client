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
from typing import TYPE_CHECKING, Any

from ..exceptions import InvalidProperty
from ..utils import check_stale, get_url_from_template, locked
from ..utils import property_s as property

if TYPE_CHECKING:
    from .lab import Lab

_LOGGER = logging.getLogger(__name__)
_SMART_ANNOTATION_DEFAULTS = {
    "is_on": True,
    "padding": 35,
    "tag": None,
    "label": None,
    "tag_offset_x": 0,
    "tag_offset_y": 0,
    "tag_size": 14,
    "group_distance": 400,
    "thickness": 1,
    "border_style": "",
    "fill_color": None,  # randomly generated
    "border_color": "#00000080",
    "z_index": 1,
}

_SMART_ANNOTATION_PROPERTIES = set(_SMART_ANNOTATION_DEFAULTS) | {"id"}


class SmartAnnotation:
    _URL_TEMPLATES = {
        "smart_annotation": "labs/{lab_id}/smart_annotations/{annotation_id}",
    }

    def __init__(
        self,
        lab: Lab,
        annotation_id: str,
        annotation_data: dict[str, Any] | None = None,
    ) -> None:
        """
        A VIRL2 lab smart annotation.

        :param lab: The lab object to which the link belongs.
        :param annotation_id: The ID of the smart annotation.
        """
        self._id = annotation_id
        self._lab = lab
        self._session = lab._session
        # When the smart annotation is removed on the server, this object is marked
        # stale and can no longer be interacted with - the user should discard it
        self._stale = False

        self._is_on = _SMART_ANNOTATION_DEFAULTS["is_on"]
        self._padding = _SMART_ANNOTATION_DEFAULTS["padding"]
        self._tag = _SMART_ANNOTATION_DEFAULTS["tag"]
        self._label = _SMART_ANNOTATION_DEFAULTS["label"]
        self._tag_offset_x = _SMART_ANNOTATION_DEFAULTS["tag_offset_x"]
        self._tag_offset_y = _SMART_ANNOTATION_DEFAULTS["tag_offset_y"]
        self._tag_size = _SMART_ANNOTATION_DEFAULTS["tag_size"]
        self._group_distance = _SMART_ANNOTATION_DEFAULTS["group_distance"]
        self._thickness = _SMART_ANNOTATION_DEFAULTS["thickness"]
        self._border_style = _SMART_ANNOTATION_DEFAULTS["border_style"]
        self._fill_color = _SMART_ANNOTATION_DEFAULTS["fill_color"]
        self._border_color = _SMART_ANNOTATION_DEFAULTS["border_color"]
        self._z_index = _SMART_ANNOTATION_DEFAULTS["z_index"]
        if annotation_data:
            self._update(annotation_data, push_to_server=False)

    def __str__(self):
        return (
            f"{self.__class__.__name__}: {self._id}{' (STALE)' if self._stale else ''}"
        )

    def __repr__(self):
        return f"{self.__class__.__name__}({str(self._lab)!r}, {self._id!r})"

    def __eq__(self, other: object):
        if not isinstance(other, SmartAnnotation):
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
    def lab(self) -> Lab:
        """Return the lab of the smart annotation."""
        return self._lab

    @property
    def id(self) -> str:
        """Return ID of the smart annotation."""
        return self._id

    @property
    def is_on(self) -> bool:
        """Whether the smart annotation is enabled."""
        self._lab.sync_topology_if_outdated()
        return self._is_on

    @is_on.setter
    @locked
    def is_on(self, value: bool) -> None:
        """Enable or disable the smart annotation."""
        self._set_smart_annotation_property("is_on", value)
        self._is_on = value

    @property
    def tag(self) -> str:
        """Tag."""
        self._lab.sync_topology_if_outdated()
        return self._tag

    @property
    def label(self) -> str:
        """Label."""
        self._lab.sync_topology_if_outdated()
        return self._label

    @label.setter
    @locked
    def label(self, value: str) -> None:
        """Set label."""
        self._set_smart_annotation_property("label", value)
        self._label = value

    @property
    def padding(self) -> int:
        """Padding."""
        self._lab.sync_topology_if_outdated()
        return self._padding

    @padding.setter
    @locked
    def padding(self, value: int) -> None:
        """Set padding."""
        self._set_smart_annotation_property("padding", value)
        self._padding = value

    @property
    def tag_offset_x(self) -> int:
        """Tag X offset."""
        self._lab.sync_topology_if_outdated()
        return self._tag_offset_x

    @tag_offset_x.setter
    @locked
    def tag_offset_x(self, value: int) -> None:
        """Set tag X offset."""
        self._set_smart_annotation_property("tag_offset_x", value)
        self._tag_offset_x = value

    @property
    def tag_offset_y(self) -> int:
        """Tag Y offset."""
        self._lab.sync_topology_if_outdated()
        return self._tag_offset_y

    @tag_offset_y.setter
    @locked
    def tag_offset_y(self, value: int) -> None:
        """Set tag Y offset."""
        self._set_smart_annotation_property("tag_offset_y", value)
        self._tag_offset_y = value

    @property
    def tag_size(self) -> int:
        """Tag size."""
        self._lab.sync_topology_if_outdated()
        return self._tag_size

    @tag_size.setter
    @locked
    def tag_size(self, value: int) -> None:
        """Set tag size."""
        self._set_smart_annotation_property("tag_size", value)
        self._tag_size = value

    @property
    def group_distance(self) -> int:
        """Group distance."""
        self._lab.sync_topology_if_outdated()
        return self._group_distance

    @group_distance.setter
    @locked
    def group_distance(self, value: int) -> None:
        """Set group distance."""
        self._set_smart_annotation_property("group_distance", value)
        self._group_distance = value

    @property
    def thickness(self) -> int:
        """Thickness."""
        self._lab.sync_topology_if_outdated()
        return self._thickness

    @thickness.setter
    @locked
    def thickness(self, value: int) -> None:
        """Set thickness."""
        self._set_smart_annotation_property("thickness", value)
        self._thickness = value

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
        self._set_smart_annotation_property("border_style", value)
        self._border_style = value

    @property
    def fill_color(self) -> str:
        """Fill color (example: `#00000080`)."""
        self._lab.sync_topology_if_outdated()
        return self._fill_color

    @fill_color.setter
    @locked
    def fill_color(self, value: str) -> None:
        """Set fill color (example: `#00000080`)."""
        self._set_smart_annotation_property("fill_color", value)
        self._fill_color = value

    @property
    def border_color(self) -> str:
        """Border color (example: `#00000080`)."""
        self._lab.sync_topology_if_outdated()
        return self._border_color

    @border_color.setter
    @locked
    def border_color(self, value: str) -> None:
        """Set border color (example: `#00000080`)."""
        self._set_smart_annotation_property("border_color", value)
        self._border_color = value

    @property
    def z_index(self) -> int:
        """Z index."""
        self._lab.sync_topology_if_outdated()
        return self._z_index

    @z_index.setter
    @locked
    def z_index(self, value: int) -> None:
        """Set Z index."""
        self._set_smart_annotation_property("z_index", value)
        self._z_index = value

    @locked
    def as_dict(self) -> dict[str, Any]:
        """
        Convert the smart annotation object to a dictionary representation.

        :returns: A dictionary representation of the smart annotation object.
        """
        return {
            "id": self._id,
            "is_on": self._is_on,
            "padding": self._padding,
            "tag": self._tag,
            "label": self._label,
            "tag_offset_x": self._tag_offset_x,
            "tag_offset_y": self._tag_offset_y,
            "tag_size": self._tag_size,
            "group_distance": self._group_distance,
            "thickness": self._thickness,
            "border_style": self._border_style,
            "fill_color": self._fill_color,
            "border_color": self._border_color,
            "z_index": self._z_index,
        }

    def remove(self) -> None:
        """Remove smart annotation from the lab."""
        self._lab.remove_smart_annotation(self)

    @check_stale
    def _remove_on_server(self) -> None:
        """Remove smart annotation on the server side along with its tag."""
        _LOGGER.info(f"Removing smart annotation {self}")
        tag = self._tag
        nodes = self._lab.find_nodes_by_tag(tag)
        for node in nodes:
            node._remove_tag_on_server(tag)

    def update(self, annotation_data: dict[str, Any]) -> None:
        """
        Update smart annotation properties.

        :param annotation_data: JSON dict with new annotation property:value pairs.
        """
        self._update(annotation_data, push_to_server=True)

    @check_stale
    @locked
    def _update(self, annotation_data: dict[str, Any], push_to_server: bool) -> None:
        """
        Update smart annotation properties.

        :param annotation_data: JSON dict with new annotation property:value pairs.
        :param push_to_server: Whether to push the changes to the server.
        """

        # make sure all properties we want to update are valid
        for key in annotation_data:
            if key not in _SMART_ANNOTATION_PROPERTIES:
                raise InvalidProperty(f"Invalid smart annotation property: {key}")

        if push_to_server:
            self._set_smart_annotation_properties(annotation_data)

        # update locally
        for key, value in annotation_data.items():
            if key == "id":
                continue
            setattr(self, f"_{key}", value)

    def _set_smart_annotation_property(self, key: str, val: Any) -> None:
        """
        Set a property of the smart annotation.

        :param key: The name of the property to set.
        :param val: The value to set.
        """
        _LOGGER.debug(f"Setting smart annotation property {self} {key}: {val}")
        self._set_smart_annotation_properties({key: val})

    @check_stale
    def _set_smart_annotation_properties(self, annotation_data: dict[str, Any]) -> None:
        """Update smart annotation properties server-side."""
        self._session.patch(url=self._url_for("smart_annotation"), json=annotation_data)
