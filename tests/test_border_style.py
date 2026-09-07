#
# This file is part of VIRL 2
# Copyright (c) 2019-2026, Cisco Systems, Inc.
# All rights reserved.
#
import pytest

from virl2_client.models.border_style import (
    border_style_for_api,
    border_style_from_api,
)
from virl2_client.utils import Version


@pytest.mark.parametrize(
    ("wire", "expected"),
    [
        ("", "solid"),
        ("2,2", "dotted"),
        ("4,2", "dashed"),
    ],
)
def test_border_style_from_api_legacy_controller(wire, expected):
    assert border_style_from_api(wire, Version("2.10.0")) == expected


@pytest.mark.parametrize(
    ("wire", "expected"),
    [
        ("solid", "solid"),
        ("dotted", "dotted"),
        ("dashed", "dashed"),
    ],
)
def test_border_style_from_api_modern_controller(wire, expected):
    assert border_style_from_api(wire, Version("2.11.0")) == expected


def test_border_style_from_api_modern_controller_rejects_legacy():
    with pytest.raises(ValueError, match=r"'' is not a valid BorderStyle"):
        border_style_from_api("", Version("2.11.0"))


def test_border_style_from_api_legacy_controller_rejects_canonical():
    with pytest.raises(KeyError):
        border_style_from_api("solid", Version("2.10.0"))


@pytest.mark.parametrize(
    ("canonical", "controller", "expected"),
    [
        ("solid", "2.10.0", ""),
        ("dotted", "2.10.0", "2,2"),
        ("dashed", "2.10.0", "4,2"),
        ("solid", "2.11.0", "solid"),
        ("dotted", "2.11.0", "dotted"),
    ],
)
def test_border_style_for_api(canonical, controller, expected):
    assert border_style_for_api(canonical, Version(controller)) == expected


def test_border_style_for_api_rejects_legacy_user_input():
    with pytest.raises(ValueError, match=r"'2,2' is not a valid BorderStyle"):
        border_style_for_api("2,2", Version("2.11.0"))
