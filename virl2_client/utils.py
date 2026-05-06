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

import re
import warnings
from collections.abc import Callable
from contextlib import nullcontext
from enum import Enum
from functools import wraps
from typing import TYPE_CHECKING, Any, TypeVar, cast

import httpx

from .exceptions import (
    AnnotationNotFound,
    ElementNotFound,
    FeatureNotSupported,
    InterfaceNotFound,
    LabNotFound,
    LinkNotFound,
    NodeNotFound,
    SmartAnnotationNotFound,
    VirlException,
)

if TYPE_CHECKING:
    from .models import Annotation, Interface, Lab, Link, Node, SmartAnnotation

    Element = Lab | Node | Interface | Link | Annotation | SmartAnnotation

TCallable = TypeVar("TCallable", bound=Callable)


class Version:
    __slots__ = ("major", "minor", "patch", "version_str")

    def __init__(self, version_str: str) -> None:
        self.version_str = version_str
        version_tuple = self.parse_version_str(version_str)
        self.major = int(version_tuple[0])
        self.minor = int(version_tuple[1])
        self.patch = int(version_tuple[2])

    @staticmethod
    def parse_version_str(version_str: str) -> str:
        regex = r"^(\d{1,2})\.(\d{1,2})\.(\d{1,2})(.{0,32})$"
        res = re.findall(regex, version_str)
        if not res:
            raise ValueError("Malformed version string.")
        return res[0]

    def __repr__(self):
        return self.version_str

    def _as_tuple(self) -> tuple[int, int, int]:
        return (self.major, self.minor, self.patch)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return False
        return self._as_tuple() == other._as_tuple()

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return False
        return self._as_tuple() > other._as_tuple()

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return False
        return self._as_tuple() >= other._as_tuple()

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return False
        return self._as_tuple() < other._as_tuple()

    def __le__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return False
        return self._as_tuple() <= other._as_tuple()

    def __hash__(self) -> int:
        return hash(self._as_tuple())

    def major_differs(self, other: Version) -> bool:
        return self.major != other.major

    def major_lt(self, other: Version) -> bool:
        return self.major < other.major

    def minor_differs(self, other: Version) -> bool:
        return self.minor != other.minor

    def minor_lt(self, other: Version) -> bool:
        return self.minor < other.minor

    def patch_differs(self, other: Version) -> bool:
        return self.patch != other.patch

    def minor_or_patch_differs(self, other: Version) -> bool:
        return self.minor_differs(other) or self.patch_differs(other)


class _Sentinel:
    def __repr__(self):
        return "<Unchanged>"


UNCHANGED = _Sentinel()
_CONFIG_MODE = "exclude_configurations=false"


class OptInStatus(Enum):
    ACCEPTED = "accepted"
    DECLINED = "declined"
    UNSET = "unset"


def _make_not_found(instance: Element) -> ElementNotFound:
    """Composes and raises an ElementNotFound error for the given instance."""
    class_name = type(instance).__name__
    if class_name.startswith("Annotation"):
        class_name = "Annotation"
    error: type[ElementNotFound] = {
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
            stacklevel=2,
        )


def _requires_version(min_version: str) -> Callable:
    """Decorator that guards a method behind a minimum CML server version.

    If the controller version is older than *min_version*, a FeatureNotSupported
    error is raised with a user-friendly message *before* the HTTP call is made.
    """
    min_ver = Version(min_version)

    def decorator(func: TCallable) -> TCallable:
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if self._session.controller_version < min_ver:
                raise FeatureNotSupported(
                    f"{type(self).__name__}.{func.__name__}() requires "
                    f"CML server >= {min_version}, but the connected "
                    f"controller is running {self._session.controller_version}."
                )
            return func(self, *args, **kwargs)

        return cast(TCallable, wrapper)

    return decorator
