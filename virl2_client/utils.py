#
# This file is part of VIRL 2
# Copyright (c) 2019-2022, Cisco Systems, Inc.
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

from contextlib import nullcontext
from functools import wraps
from typing import TYPE_CHECKING, Callable, Optional, Type, TypeVar, Union, cast

import httpx

from .exceptions import (
    ElementNotFound,
    InterfaceNotFound,
    LabNotFound,
    LinkNotFound,
    NodeNotFound,
)

if TYPE_CHECKING:
    from .models import Interface, Lab, Link, Node

    Element = Union[Lab, Node, Interface, Link]

TCallable = TypeVar("TCallable", bound=Callable)


class _Sentinel:
    def __repr__(self):
        return "<Unchanged>"


UNCHANGED = _Sentinel()


def _make_not_found(instance: Element, owner: Type[Element]) -> ElementNotFound:
    """Composes and raises an ElementNotFound error for the given instance."""
    class_name = owner.__name__
    instance_id = instance._id
    instance_label = instance._title if class_name == "Lab" else instance._label

    error_text = (
        f"{class_name} {instance_label} ({instance_id}) no longer exists on the server."
    )
    error: Type[ElementNotFound] = {
        "Lab": LabNotFound,
        "Node": NodeNotFound,
        "Interface": InterfaceNotFound,
        "Link": LinkNotFound,
    }[class_name]
    return error(error_text)


def _check_and_mark_stale(
    func: Callable,
    instance: Element,
    owner: Optional[Type[Element]] = None,
    *args,
    **kwargs,
):
    """
    Checks staleness before and after calling `func`
    and updates staleness if a 404 is raised.

    :param func: the function to be called if not stale
    :param instance: the instance of the parent class of `func`
        which has a `_stale` attribute
    :param owner: the class of `instance`
    :param args: positional arguments to be passed to `func`
    :param kwargs: keyword arguments to be passed to `func`
    """
    if owner is None:
        owner = type(instance)

    if instance._stale:
        raise _make_not_found(instance, owner)

    try:
        ret = func(*args, **kwargs)
        if instance._stale:
            raise _make_not_found(instance, owner)
        return ret

    except httpx.HTTPStatusError as exc:
        resp = exc.response
        class_name = owner.__name__
        instance_id = instance._id
        if (
            resp.status_code == 404
            and f"{class_name} not found: {instance_id}" in resp.text
        ):
            instance._stale = True
            raise _make_not_found(instance, owner) from exc
        raise


def check_stale(func: TCallable) -> TCallable:
    """
    A decorator that will make the wrapped function check staleness.
    """

    @wraps(func)
    def wrapper_stale(*args, **kwargs):
        return _check_and_mark_stale(func, args[0], None, *args, **kwargs)

    return cast(TCallable, wrapper_stale)


class property_s(property):
    """A modified `property` that will check staleness."""

    def __get__(self, instance, owner):
        return _check_and_mark_stale(super().__get__, instance, owner, instance, owner)


def locked(func: TCallable) -> TCallable:
    """
    A decorator that makes a method threadsafe.
    Parent class instance must have a `session.lock` property for locking to occur.
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
