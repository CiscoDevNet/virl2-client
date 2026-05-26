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
"""Tests for stale-checking utilities and related helpers."""

from __future__ import annotations

import httpx
import pytest

from virl2_client.exceptions import AnnotationNotFound, LabNotFound, VirlException
from virl2_client.utils import (
    UNCHANGED,
    _check_and_mark_stale,
    _deprecated_argument,
    _make_not_found,
    check_stale,
    get_url_from_template,
    property_s,
)


class Lab:
    """Minimal test double with class name expected by stale helpers."""

    def __init__(self, lab_id: str = "lab-1", stale: bool = False) -> None:
        """Create a lab double for stale-helper tests.

        :param lab_id: Lab identifier (default "lab-1").
        :param stale: Whether the lab is considered stale (default False).
        """
        self._id = lab_id
        self._stale = stale


def _http_status_error(status_code: int, text: str = "") -> httpx.HTTPStatusError:
    """Build an HTTPStatusError for testing.

    :param status_code: HTTP status code for the response.
    :param text: Optional response body text.
    :returns: An httpx.HTTPStatusError with the given status and text.
    """
    request = httpx.Request("GET", "https://example/api")
    response = httpx.Response(status_code, request=request, text=text)
    return httpx.HTTPStatusError("error", request=request, response=response)


def test_check_stale_raises_already_stale() -> None:
    """_check_and_mark_stale raises LabNotFound when instance is already stale.

    NOTE: LLM-generated test -- verify for correctness.
    """
    instance = Lab(stale=True)

    with pytest.raises(LabNotFound):
        _check_and_mark_stale(lambda *_args, **_kwargs: None, instance, instance)


def test_check_stale_raises_if_marked_after_call() -> None:
    """Raise LabNotFound when call marks instance stale.

    NOTE: LLM-generated test -- verify for correctness.
    """
    instance = Lab(stale=False)

    def mark_stale(*_args: object, **_kwargs: object) -> str:
        """Mutate instance stale flag to exercise decorator behavior."""
        instance._stale = True
        return "ignored"

    with pytest.raises(LabNotFound):
        _check_and_mark_stale(mark_stale, instance, instance)


def test_check_stale_marks_on_404() -> None:
    """_check_and_mark_stale marks instance stale on 404 with expected message.

    NOTE: LLM-generated test -- verify for correctness.
    """
    instance = Lab(stale=False)
    error = _http_status_error(404, "Lab not found: lab-1")

    def raise_404(*_args: object, **_kwargs: object) -> None:
        """Raise expected 404 error for stale marking path."""
        raise error

    with pytest.raises(LabNotFound):
        _check_and_mark_stale(raise_404, instance, instance)

    assert instance._stale is True


def test_check_stale_passthrough_other_errors() -> None:
    """Pass through unexpected HTTP errors without stale-marking.

    NOTE: LLM-generated test -- verify for correctness.
    """
    instance = Lab(stale=False)
    error = _http_status_error(500, "server failure")

    def raise_500(*_args: object, **_kwargs: object) -> None:
        """Raise generic server error for passthrough branch."""
        raise error

    with pytest.raises(httpx.HTTPStatusError):
        _check_and_mark_stale(raise_500, instance, instance)

    assert instance._stale is False


def test_check_stale_decorator_returns_value() -> None:
    """Pass through return value when instance is not stale.

    NOTE: LLM-generated test -- verify for correctness.
    """
    instance = Lab(stale=False)

    @check_stale
    def f(_self: Lab, value: str) -> str:
        """Echo value for decorated function behavior assertion."""
        return value

    assert f(instance, "ok") == "ok"


def test_check_stale_decorator_raises_for_stale() -> None:
    """Raise LabNotFound when decorated instance is stale.

    NOTE: LLM-generated test -- verify for correctness.
    """
    instance = Lab(stale=True)

    @check_stale
    def f(_self: Lab) -> None:
        """No-op helper used only to trigger stale guard."""
        return None

    with pytest.raises(LabNotFound):
        f(instance)


class AnnotationRectangle:
    """Minimal annotation double whose class name triggers AnnotationNotFound mapping."""

    def __init__(self, annotation_id: str) -> None:
        """Store synthetic annotation identifier."""
        self._id = annotation_id


def test_unchanged_repr() -> None:
    """UNCHANGED sentinel has expected repr.

    NOTE: LLM-generated test -- verify for correctness.
    """
    assert repr(UNCHANGED) == "<Unchanged>"


def test_make_not_found_annotation_map() -> None:
    """_make_not_found for AnnotationRectangle returns AnnotationNotFound.

    NOTE: LLM-generated test -- verify for correctness.
    """
    not_found = _make_not_found(AnnotationRectangle("a-1"))
    assert isinstance(not_found, AnnotationNotFound)


def test_property_s_doc() -> None:
    """property_s uses custom doc string.

    NOTE: LLM-generated test -- verify for correctness.
    """

    class Holder:
        def __init__(self) -> None:
            self._stale = False
            self._id = "h1"

        def _get_value(self) -> str:
            return "ok"

        value = property_s(_get_value, doc="custom-doc")

    assert Holder.__dict__["value"].__doc__ == "custom-doc"


def test_property_s_getter() -> None:
    """property_s getter returns value from underlying function.

    NOTE: LLM-generated test -- verify for correctness.
    """

    class Holder:
        def __init__(self) -> None:
            self._stale = False
            self._id = "h1"

        def _get_value(self) -> str:
            return "ok"

        value = property_s(_get_value, doc="custom-doc")

    holder = Holder()
    assert holder.value == "ok"


def test_url_template_missing() -> None:
    """get_url_from_template raises VirlException when key is missing.

    NOTE: LLM-generated test -- verify for correctness.
    """
    with pytest.raises(VirlException):
        get_url_from_template("missing", {"known": "x"})


def test_url_template_success() -> None:
    """get_url_from_template returns resolved URL with template vars.

    NOTE: LLM-generated test -- verify for correctness.
    """
    assert get_url_from_template("known", {"known": "path/{CONFIG_MODE}"}) == (
        "path/exclude_configurations=false"
    )


def test_deprecated_argument_warns_and_ignores_none() -> None:
    """Cover deprecation warning helper for set and unset arguments.

    NOTE: LLM-generated test -- verify for correctness.
    """

    class Dummy:
        def method(self) -> None:
            """No-op method for deprecation warning origin."""
            return None

    dummy = Dummy()
    with pytest.deprecated_call(match="The argument 'offline' is deprecated"):
        _deprecated_argument(dummy.method, True, "offline")

    _deprecated_argument(dummy.method, None, "offline")
