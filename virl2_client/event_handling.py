#
# This file is part of VIRL 2
# Copyright (c) 2019-2023, Cisco Systems, Inc.
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

import asyncio
import logging
from abc import ABC, abstractmethod
from os import name as os_name
from typing import Any, TYPE_CHECKING, Union

from .exceptions import ElementNotFound, LabNotFound

if TYPE_CHECKING:
    from ..virl2_client import ClientLibrary
    from .models import Interface, Lab, Link, Node

_LOGGER = logging.getLogger(__name__)

# Fixes an arbitrary 'RuntimeError: Event loop is closed'
# that sometimes appeared on Windows for no reason, see
# https://stackoverflow.com/questions/45600579/asyncio-event-loop-is-closed-when-getting-loop
if os_name == "nt":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


class Event:
    def __init__(self, event_dict: dict[str, Any]):
        """
        An event object, stores parsed info about the event it represents.

        :param event_dict: A dictionary containing event data.
        """
        self.type: str = (event_dict.get("event_type") or "").casefold()
        self.subtype_original: str | None = event_dict.get("event")
        self.subtype: str = (self.subtype_original or "").casefold()
        self.element_type: str = (event_dict.get("element_type") or "").casefold()
        self.lab_id: str = event_dict.get("lab_id", "")
        self.element_id: str = event_dict.get("element_id", "")
        self.data: dict | None = event_dict.get("data")
        self.lab: Lab | None = None
        self.element: Union[Node, Interface, Link, None] = None


class EventHandlerBase(ABC):
    def __init__(self, client_library: ClientLibrary = None):
        """
        Abstract base class for event handlers.

        Subclass this if you want to implement the entire event handling mechanism
        from scratch, otherwise subclass EventHandler instead.

        :param client_library: The client library which should be modified by events.
        """
        self.client_library = client_library

    def parse_event(self, event: Event) -> None:
        """
        Parse and handle the given event.

        :param event: An Event object representing the event to be parsed.
        """
        if event.type == "lab_event":
            self._parse_lab(event)
        elif event.type == "lab_element_event":
            self._parse_element(event)
        elif event.type == "state_change":
            self._parse_state_change(event)
        else:
            self._parse_other(event)

    def _parse_lab(self, event: Event) -> None:
        """
        Handle lab events.

        :param event: An Event object representing the lab event.
        """
        if event.subtype == "created":
            self._parse_lab_created(event)
        elif event.subtype == "modified":
            self._parse_lab_modified(event)
        elif event.subtype == "deleted":
            self._parse_lab_deleted(event)
        elif event.subtype == "state":
            self._parse_lab_state(event)
        else:
            _LOGGER.warning(f"Received an invalid lab event ({event.subtype})")

    @abstractmethod
    def _parse_lab_created(self, event: Event) -> None:
        """
        Handle lab created events.

        :param event: An Event object representing the lab created event.
        """
        pass

    @abstractmethod
    def _parse_lab_modified(self, event: Event) -> None:
        """
        Handle lab modified events.

        :param event: An Event object representing the lab modified event.
        """
        pass

    @abstractmethod
    def _parse_lab_deleted(self, event: Event) -> None:
        """
        Handle lab deleted events.

        :param event: An Event object representing the lab deleted event.
        """
        pass

    @abstractmethod
    def _parse_lab_state(self, event: Event) -> None:
        """
        Handle lab state events.

        :param event: An Event object representing the lab state event.
        """
        pass

    def _parse_element(self, event: Event) -> None:
        """
        Handle lab element events.

        :param event: An Event object representing the lab element event.
        """
        if event.subtype == "created":
            self._parse_element_created(event)
        elif event.subtype == "modified":
            self._parse_element_modified(event)
        elif event.subtype == "deleted":
            self._parse_element_deleted(event)
        else:
            _LOGGER.warning(f"Received an invalid element event ({event.subtype})")

    @abstractmethod
    def _parse_element_created(self, event: Event) -> None:
        """
        Handle element created events.

        :param event: An Event object representing the element created event.
        """
        pass

    @abstractmethod
    def _parse_element_modified(self, event: Event) -> None:
        """
        Handle element modified events.

        :param event: An Event object representing the element modified event.
        """
        pass

    @abstractmethod
    def _parse_element_deleted(self, event: Event) -> None:
        """
        Handle element deleted events.

        :param event: An Event object representing the element deleted event.
        """
        pass

    @abstractmethod
    def _parse_state_change(self, event: Event) -> None:
        """
        Handle state change events.

        :param event: An Event object representing the state change event.
        """
        pass

    def _parse_other(self, event: Event) -> None:
        """
        Handle other events.

        :param event: An Event object representing the other event.
        """
        # All other events are useless to the client, but in case some handling
        # needs to be done on them, this method can be overridden
        pass


class EventHandler(EventHandlerBase):
    """
    Handler for JSON events received from controller over websockets.
    Used by EventListener by default, but can be subclassed and methods overridden
    to change/extend the handling mechanism, then passed to EventListener.
    """

    def parse_event(self, event: Event) -> None:
        if event.type in ("lab_stats", "system_stats"):
            return

        try:
            event.lab = self.client_library.get_local_lab(event.lab_id)
        except LabNotFound:
            # lab is not locally joined, so we can ignore its events
            return

        if event.subtype != "created":
            try:
                if event.element_type == "node":
                    event.element = event.lab.get_node_by_id(event.element_id)
                if event.element_type == "interface":
                    event.element = event.lab.get_interface_by_id(event.element_id)
                if event.element_type == "link":
                    event.element = event.lab.get_link_by_id(event.element_id)
            except ElementNotFound:
                return

        super().parse_event(event)

    def _parse_lab_created(self, event: Event) -> None:
        # we don't care about labs the user hasn't joined,
        # so we don't need the lab creation event
        pass

    def _parse_lab_modified(self, event: Event) -> None:
        event.lab.update_lab_properties(event.data)

    def _parse_lab_deleted(self, event: Event) -> None:
        self.client_library._remove_lab_local(event.lab)

    def _parse_lab_state(self, event: Event) -> None:
        event.lab._state = event.data["state"]

    def _parse_element_created(self, event: Event) -> None:
        new_element: Node | Interface | Link
        if event.element_type == "node":
            new_element = event.lab._import_node(
                event.element_id,
                event.data,
            )
        elif event.element_type == "interface":
            new_element = event.lab._import_interface(
                event.element_id,
                event.data["node"],
                event.data,
            )
        elif event.element_type == "link":
            new_element = event.lab._import_link(
                event.element_id,
                event.data["interface_a"],
                event.data["interface_b"],
            )
        else:
            _LOGGER.warning(f"Received an invalid element type ({event.element_type})")
            return
        new_element._state = event.data.get("state")

    def _parse_element_modified(self, event: Event) -> None:
        if event.element_type == "node":
            event.element.update(
                event.data, exclude_configurations=False, push_to_server=False
            )

        elif event.element_type == "interface":
            # it seems only port change info arrives here,
            # which the client doesn't use, so this message can be discarded
            pass

        elif event.element_type == "link":
            # same as above, only sends link_capture_key which is not used
            # by the client, so we discard the message
            pass

        else:
            _LOGGER.warning(
                f"Received an invalid lab element event "
                f"({event.subtype} {event.element_type})"
            )

    def _parse_element_deleted(self, event: Event) -> None:
        if event.element_type == "node":
            event.lab._remove_node_local(event.element)

        elif event.element_type == "interface":
            event.lab._remove_interface_local(event.element)

        elif event.element_type == "link":
            event.lab._remove_link_local(event.element)

        else:
            _LOGGER.warning(
                f"Received an invalid lab element event "
                f"({event.subtype} {event.element_type})"
            )

    def _parse_state_change(self, event: Event) -> None:
        event.element._state = event.subtype_original
