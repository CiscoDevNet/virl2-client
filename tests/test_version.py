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
"""Tests for the Version class: comparisons, parsing, and diff helpers."""

from __future__ import annotations

import pytest

from virl2_client.virl2_client import Version


@pytest.mark.parametrize(
    "a, b, expected",
    [
        pytest.param(Version("2.0.0"), Version("2.0.0"), True, id="equal"),
        pytest.param(Version("2.0.0"), Version("2.0.1"), False, id="differ"),
        pytest.param(Version("2.0.0"), "2.0.0", False, id="string"),
        pytest.param(Version("2.0.0"), 200, False, id="int"),
    ],
)
def test_version_comparison_eq(
    a: Version, b: Version | str | int, expected: bool
) -> None:
    """Compare Version objects with equality operator.

    NOTE: LLM-generated test -- verify for correctness.

    :param a: First operand.
    :param b: Second operand.
    :param expected: Expected result of a == b.
    """
    assert (a == b) == expected


@pytest.mark.parametrize(
    "greater, lesser, expected",
    [
        pytest.param(
            Version("2.0.1"), Version("2.0.0"), True, id="Patch is greater than"
        ),
        pytest.param(
            Version("2.0.10"), Version("2.0.0"), True, id="Patch is much greater than"
        ),
        pytest.param(
            Version("2.1.0"), Version("2.0.0"), True, id="Minor is greater than"
        ),
        pytest.param(
            Version("2.10.0"), Version("2.0.0"), True, id="Minor is much greater than"
        ),
        pytest.param(
            Version("3.0.0"), Version("2.0.0"), True, id="Major is greater than"
        ),
        pytest.param(
            Version("10.0.0"), Version("2.0.0"), True, id="Major is much greater than"
        ),
        pytest.param(
            Version("2.0.0"), Version("2.0.1"), False, id="Patch is lesser than"
        ),
        pytest.param(
            Version("2.0.0"), Version("2.0.10"), False, id="Patch is much lesser than"
        ),
        pytest.param(
            Version("2.0.0"), Version("2.1.0"), False, id="Minor is lesser than"
        ),
        pytest.param(
            Version("2.0.0"), Version("2.10.0"), False, id="Minor is much lesser than"
        ),
        pytest.param(
            Version("2.0.0"), Version("3.0.0"), False, id="Major is lesser than"
        ),
        pytest.param(
            Version("2.0.0"), Version("10.0.0"), False, id="Major is much lesser than"
        ),
        pytest.param(
            Version("2.0.0"),
            "random string",
            False,
            id="Other object is string and not a Version object",
        ),
        pytest.param(
            Version("2.0.0"),
            12345,
            False,
            id="Other object is int and not a Version object",
        ),
    ],
)
def test_version_comparison_gt(
    greater: Version, lesser: Version | str | int, expected: bool
) -> None:
    """Compare Version objects with greater-than operator.

    NOTE: LLM-generated test -- verify for correctness.

    :param greater: Version expected to be greater.
    :param lesser: Version or other object to compare against.
    :param expected: Expected result of greater > lesser.
    """
    assert (greater > lesser) == expected


@pytest.mark.parametrize(
    "first, second, expected",
    [
        pytest.param(
            Version("2.0.1"), Version("2.0.0"), True, id="Patch is greater than"
        ),
        pytest.param(
            Version("2.0.10"), Version("2.0.0"), True, id="Patch is much greater than"
        ),
        pytest.param(
            Version("2.1.0"), Version("2.0.0"), True, id="Minor is greater than"
        ),
        pytest.param(
            Version("2.10.0"), Version("2.0.0"), True, id="Minor is much greater than"
        ),
        pytest.param(
            Version("3.0.0"), Version("2.0.0"), True, id="Major is greater than"
        ),
        pytest.param(
            Version("10.0.0"), Version("2.0.0"), True, id="Major is much greater than"
        ),
        pytest.param(
            Version("2.0.0"), Version("2.0.1"), False, id="Patch is lesser than"
        ),
        pytest.param(
            Version("2.0.0"), Version("2.0.10"), False, id="Patch is much lesser than"
        ),
        pytest.param(
            Version("2.0.0"), Version("2.1.0"), False, id="Minor is lesser than"
        ),
        pytest.param(
            Version("2.0.0"), Version("2.10.0"), False, id="Minor is much lesser than"
        ),
        pytest.param(
            Version("2.0.0"), Version("3.0.0"), False, id="Major is lesser than"
        ),
        pytest.param(
            Version("2.0.0"), Version("10.0.0"), False, id="Major is much lesser than"
        ),
        pytest.param(
            Version("2.0.0"),
            Version("2.0.0"),
            True,
            id="Equal versions no minor no patch",
        ),
        pytest.param(
            Version("2.0.1"),
            Version("2.0.1"),
            True,
            id="Equal versions patch increment",
        ),
        pytest.param(
            Version("2.1.0"),
            Version("2.1.0"),
            True,
            id="Equal versions minor increment",
        ),
        pytest.param(
            Version("3.0.0"),
            Version("3.0.0"),
            True,
            id="Equal versions major increment",
        ),
        pytest.param(
            Version("2.0.0"),
            "random string",
            False,
            id="Other object is string and not a Version object",
        ),
        pytest.param(
            Version("2.0.0"),
            12345,
            False,
            id="Other object is int and not a Version object",
        ),
    ],
)
def test_version_comparison_gte(
    first: Version, second: Version, expected: bool
) -> None:
    """Compare Version objects with greater-than-or-equal operator.

    NOTE: LLM-generated test -- verify for correctness.

    :param first: First Version to compare.
    :param second: Second Version to compare against.
    :param expected: Expected result of first >= second.
    """
    assert (first >= second) == expected


@pytest.mark.parametrize(
    "lesser, greater, expected",
    [
        pytest.param(Version("2.0.0"), Version("2.0.1"), True, id="Patch is less than"),
        pytest.param(
            Version("2.0.0"), Version("2.0.10"), True, id="Patch is much less than"
        ),
        pytest.param(Version("2.0.0"), Version("2.1.0"), True, id="Minor is less than"),
        pytest.param(
            Version("2.0.0"), Version("2.10.0"), True, id="Minor is much less than"
        ),
        pytest.param(Version("2.0.0"), Version("3.0.0"), True, id="Major is less than"),
        pytest.param(
            Version("2.0.0"), Version("10.0.0"), True, id="Major is much less than"
        ),
        pytest.param(
            Version("2.0.1"), Version("2.0.0"), False, id="Patch is greater than"
        ),
        pytest.param(
            Version("2.0.10"), Version("2.0.0"), False, id="Patch is much greater than"
        ),
        pytest.param(
            Version("2.1.0"), Version("2.0.0"), False, id="Minor is greater than"
        ),
        pytest.param(
            Version("2.10.0"), Version("2.0.0"), False, id="Minor is much greater than"
        ),
        pytest.param(
            Version("3.0.0"), Version("2.0.0"), False, id="Major is greater than"
        ),
        pytest.param(
            Version("10.0.0"), Version("2.0.0"), False, id="Major is much greater than"
        ),
        pytest.param(
            Version("2.0.0"),
            "random string",
            False,
            id="Other object is string and not a Version object",
        ),
        pytest.param(
            Version("2.0.0"),
            12345,
            False,
            id="Other object is int and not a Version object",
        ),
    ],
)
def test_version_comparison_lt(
    lesser: Version, greater: Version | str | int, expected: bool
) -> None:
    """Compare Version objects with less-than operator.

    NOTE: LLM-generated test -- verify for correctness.

    :param lesser: Version expected to be lesser.
    :param greater: Version or other object to compare against.
    :param expected: Expected result of lesser < greater.
    """
    assert (lesser < greater) == expected


@pytest.mark.parametrize(
    "first, second, expected",
    [
        pytest.param(Version("2.0.0"), Version("2.0.1"), True, id="Patch is less than"),
        pytest.param(
            Version("2.0.0"), Version("2.0.10"), True, id="Patch is much less than"
        ),
        pytest.param(Version("2.0.0"), Version("2.1.0"), True, id="Minor is less than"),
        pytest.param(
            Version("2.0.0"), Version("2.10.0"), True, id="Minor is much less than"
        ),
        pytest.param(Version("2.0.0"), Version("3.0.0"), True, id="Major is less than"),
        pytest.param(
            Version("2.0.0"), Version("10.0.0"), True, id="Major is much less than"
        ),
        pytest.param(
            Version("2.0.1"), Version("2.0.0"), False, id="Patch is greater than"
        ),
        pytest.param(
            Version("2.0.10"), Version("2.0.0"), False, id="Patch is much greater than"
        ),
        pytest.param(
            Version("2.1.0"), Version("2.0.0"), False, id="Minor is greater than"
        ),
        pytest.param(
            Version("2.10.0"), Version("2.0.0"), False, id="Minor is much greater than"
        ),
        pytest.param(
            Version("3.0.0"), Version("2.0.0"), False, id="Major is greater than"
        ),
        pytest.param(
            Version("10.0.0"), Version("2.0.0"), False, id="Major is much greater than"
        ),
        pytest.param(
            Version("2.0.0"),
            Version("2.0.0"),
            True,
            id="Equal versions no minor no patch",
        ),
        pytest.param(
            Version("2.0.1"),
            Version("2.0.1"),
            True,
            id="Equal versions patch increment",
        ),
        pytest.param(
            Version("2.1.0"),
            Version("2.1.0"),
            True,
            id="Equal versions minor increment",
        ),
        pytest.param(
            Version("3.0.0"),
            Version("3.0.0"),
            True,
            id="Equal versions major increment",
        ),
        pytest.param(
            Version("2.0.0"),
            "random string",
            False,
            id="Other object is string and not a Version object",
        ),
        pytest.param(
            Version("2.0.0"),
            12345,
            False,
            id="Other object is int and not a Version object",
        ),
    ],
)
def test_version_comparison_lte(
    first: Version, second: Version, expected: bool
) -> None:
    """Compare Version objects with less-than-or-equal operator.

    NOTE: LLM-generated test -- verify for correctness.

    :param first: First Version to compare.
    :param second: Second Version to compare against.
    :param expected: Expected result of first <= second.
    """
    assert (first <= second) == expected


@pytest.mark.parametrize(
    "version_str",
    [
        "2.1.0-dev0+build8.7ee86bf8",
        "2.1.0dev0+build8.7ee86bf8",
        "2.1.0--dev0+build8.7ee86bf8",
        "2.1.0_dev0+build8.7ee86bf8",
        "2.1.0",
        "2.1.0-",
    ],
)
def test_version_parse_valid(version_str: str) -> None:
    """Parse valid Version string formats into expected components.

    NOTE: LLM-generated test -- verify for correctness.

    :param version_str: Version string to parse.
    """
    v = Version(version_str)
    assert v.major == 2 and v.minor == 1 and v.patch == 0


@pytest.mark.parametrize(
    "version_str",
    [
        "2.1-dev0+build8.7ee86bf8",
        "2-dev0+build8.7ee86bf8",
        "54dev0+build8.7ee86bf8",
    ],
)
def test_version_parse_invalid(version_str: str) -> None:
    """Reject malformed version strings with ValueError.

    NOTE: LLM-generated test -- verify for correctness.

    :param version_str: Invalid version string.
    """
    with pytest.raises(ValueError):
        Version(version_str)


def test_version_diff_helpers() -> None:
    """Version helper methods return True when versions differ.

    NOTE: LLM-generated test -- verify for correctness.
    """
    v1 = Version("2.10.3")
    v2 = Version("3.11.4")
    assert v1.major_differs(v2) is True
    assert v1.minor_differs(v2) is True
    assert v1.patch_differs(v2) is True
    assert v1.minor_or_patch_differs(v2) is True
