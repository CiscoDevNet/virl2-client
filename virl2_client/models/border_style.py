#
# This file is part of VIRL 2
# Copyright (c) 2019-2026, Cisco Systems, Inc.
# All rights reserved.
#
"""Convert annotation border_style between canonical and legacy wire formats."""

from __future__ import annotations

from enum import Enum

from ..utils import Version

CANONICAL_BORDER_STYLE_MIN_VERSION = Version("2.11.0")


class BorderStyle(str, Enum):
    """Canonical annotation border styles (mirrors simple_common.schemas.enums.BorderStyle)."""

    SOLID = "solid"
    DOTTED = "dotted"
    DASHED = "dashed"


_LEGACY_TO_CANONICAL: dict[str, str] = {
    "": BorderStyle.SOLID.value,
    "2,2": BorderStyle.DOTTED.value,
    "4,2": BorderStyle.DASHED.value,
}

_CANONICAL_TO_LEGACY: dict[str, str] = {v: k for k, v in _LEGACY_TO_CANONICAL.items()}


def border_style_from_api(value: str, controller_version: Version) -> str:
    """Parse a border_style value returned by the connected controller."""
    if controller_version >= CANONICAL_BORDER_STYLE_MIN_VERSION:
        return BorderStyle(value).value
    return _LEGACY_TO_CANONICAL[value]


def border_style_for_api(value: str, controller_version: Version) -> str:
    """Serialize a canonical border style for the connected controller API."""
    canonical = BorderStyle(value).value
    if controller_version >= CANONICAL_BORDER_STYLE_MIN_VERSION:
        return canonical
    return _CANONICAL_TO_LEGACY[canonical]
