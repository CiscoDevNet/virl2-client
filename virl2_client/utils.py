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

import warnings
from contextlib import nullcontext
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable, Type, TypeVar, Union, cast

import httpx

from .exceptions import (
    AnnotationNotFound,
    ElementNotFound,
    InterfaceNotFound,
    LabNotFound,
    LinkNotFound,
    NodeNotFound,
    SmartAnnotationNotFound,
    VirlException,
)

if TYPE_CHECKING:
    from .models import Annotation, Interface, Lab, Link, Node

    Element = Union[Lab, Node, Interface, Link, Annotation]

TCallable = TypeVar("TCallable", bound=Callable)


class _Sentinel:
    def __repr__(self):
        return "<Unchanged>"


UNCHANGED = _Sentinel()
_CONFIG_MODE = "exclude_configurations=false"


def _make_not_found(instance: Element) -> ElementNotFound:
    """Composes and raises an ElementNotFound error for the given instance."""
    class_name = type(instance).__name__
    if class_name.startswith("Annotation"):
        class_name = "Annotation"
    error: Type[ElementNotFound] = {
        "Lab": LabNotFound,
        "Node": NodeNotFound,
        "Interface": InterfaceNotFound,
        "Link": LinkNotFound,
        "Annotation": AnnotationNotFound,
        "SmartAnnotation": SmartAnnotationNotFound,
    }[class_name]
    return error(instance._id)


def _check_and_mark_stale(func: Callable, instance: Element, *args, **kwargs):
    """
    Check staleness before and after calling `func`
    and updates staleness if a 404 is raised.

    :param func: The function to be called if the instance is not stale.
    :param instance: The instance of the parent class of `func`
        which has a `_stale` attribute.
    :param args: Positional arguments to be passed to `func`.
    :param kwargs: Keyword arguments to be passed to `func`.
    """

    if instance._stale:
        raise _make_not_found(instance)

    try:
        ret = func(*args, **kwargs)
        if instance._stale:
            raise _make_not_found(instance)
        return ret
    except httpx.HTTPStatusError as exc:
        resp = exc.response
        class_name = type(instance).__name__
        instance_id = instance._id
        if (
            resp.status_code == 404
            and f"{class_name} not found: {instance_id}" in resp.text
        ):
            instance._stale = True
            raise _make_not_found(instance) from exc
        raise


def check_stale(func: TCallable) -> TCallable:
    """A decorator that will make the wrapped function check staleness."""

    @wraps(func)
    def wrapper_stale(*args, **kwargs):
        return _check_and_mark_stale(func, args[0], *args, **kwargs)

    return cast(TCallable, wrapper_stale)


class property_s(property):
    """A modified `property` that will check staleness."""

    def __init__(self, fget=None, fset=None, fdel=None, doc=None):
        super().__init__(fget=fget, fset=fset, fdel=fdel)
        if doc:
            self.__doc__ = doc

    def __get__(self, instance, owner):
        return _check_and_mark_stale(super().__get__, instance, instance, owner)


def locked(func: TCallable) -> TCallable:
    """
    A decorator that makes a method threadsafe.
    Parent class instance must have a `_session.lock` property for locking to occur.
    """

    @wraps(func)
    def wrapper_locked(*args, **kwargs):
        try:
            ctx = args[0]._session.lock
        except (IndexError, AttributeError):
            ctx = None
        if ctx is None:
            ctx = nullcontext()
        with ctx:
            return func(*args, **kwargs)

    return cast(TCallable, wrapper_locked)


def get_url_from_template(
    endpoint: str, url_templates: dict[str, str], values: dict | None = None
) -> str:
    """
    Generate the URL for a given API endpoint from given templates.

    :param endpoint: The desired endpoint.
    :param url_templates: The templates to map values to.
    :param values: Keyword arguments used to format the URL.
    :returns: The formatted URL.
    """
    endpoint_url_template = url_templates.get(endpoint)
    if endpoint_url_template is None:
        raise VirlException(f"Invalid endpoint: {endpoint}")
    if values is None:
        values = {}
    values["CONFIG_MODE"] = _CONFIG_MODE
    return endpoint_url_template.format(**values)


_DEPRECATION_MESSAGES = {
    "push_to_server": "meant to be used only by internal methods",
    "offline": "offline mode has been removed",
    "labs": "use the `.associations` attribute instead",
}


def _deprecated_argument(func, argument: Any, argument_name: str):
    if argument is not None:
        reason = _DEPRECATION_MESSAGES[argument_name]
        warnings.warn(
            f"{type(func.__self__).__name__}.{func.__name__}: "
            f"The argument '{argument_name}' is deprecated. Reason: {reason}",
            DeprecationWarning,
        )
