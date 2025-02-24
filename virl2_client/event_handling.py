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

import asyncio
import logging
from abc import ABC, abstractmethod
from os import name as os_name
from typing import TYPE_CHECKING, Any, Union

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

    def __str__(self):
        return (
            f"Event type: {self.type}, "
            f"Subtype: {self.subtype}, "
            f"Element type: {self.element_type}"
        )


class EventHandlerBase(ABC):
    def __init__(self, client_library: ClientLibrary = None):
        """
        Abstract base class for event handlers.

        Subclass this if you want to implement the entire event handling mechanism
        from scratch, otherwise subclass EventHandler instead.

        :param client_library: The client library which should be modified by events.
        """
        self._client_library = client_library

    def handle_event(self, event: Event) -> None:
        """
        Parse and handle the given event.

        :param event: An Event object representing the event to be parsed.
        """
        if event.type == "lab_event":
            self._handle_lab(event)
        elif event.type == "lab_element_event":
            self._handle_element(event)
        elif event.type == "state_change":
            self._handle_state_change(event)
        else:
            self._handle_other(event)

    def _handle_lab(self, event: Event) -> None:
        """
        Handle lab events.

        :param event: An Event object representing the lab event.
        """
        if event.subtype == "created":
            self._handle_lab_created(event)
        elif event.subtype == "modified":
            self._handle_lab_modified(event)
        elif event.subtype == "deleted":
            self._handle_lab_deleted(event)
        elif event.subtype == "state":
            self._handle_lab_state(event)
        else:
            # There are only four subtypes, anything else is invalid
            _LOGGER.warning(f"Received an invalid event. {event}")

    @abstractmethod
    def _handle_lab_created(self, event: Event) -> None:
        """
        Handle lab created events.

        :param event: An Event object representing the lab created event.
        """
        pass

    @abstractmethod
    def _handle_lab_modified(self, event: Event) -> None:
        """
        Handle lab modified events.

        :param event: An Event object representing the lab modified event.
        """
        pass

    @abstractmethod
    def _handle_lab_deleted(self, event: Event) -> None:
        """
        Handle lab deleted events.

        :param event: An Event object representing the lab deleted event.
        """
        pass

    @abstractmethod
    def _handle_lab_state(self, event: Event) -> None:
        """
        Handle lab state events.

        :param event: An Event object representing the lab state event.
        """
        pass

    def _handle_element(self, event: Event) -> None:
        """
        Handle lab element events.

        :param event: An Event object representing the lab element event.
        """
        if event.element_type in ("annotation", "connectormapping"):
            # These are not used in this client library
            _LOGGER.debug(f"Received an unused element type: {event.data}")
        elif event.subtype == "created":
            self._handle_element_created(event)
        elif event.subtype == "modified":
            self._handle_element_modified(event)
        elif event.subtype == "deleted":
            self._handle_element_deleted(event)
        else:
            # There are only three subtypes, anything else is invalid
            # ("state" is under type "state_change", not "lab_element_event")
            _LOGGER.warning(f"Received an invalid event. {event}")

    @abstractmethod
    def _handle_element_created(self, event: Event) -> None:
        """
        Handle element created events.

        :param event: An Event object representing the element created event.
        """
        pass

    @abstractmethod
    def _handle_element_modified(self, event: Event) -> None:
        """
        Handle element modified events.

        :param event: An Event object representing the element modified event.
        """
        pass

    @abstractmethod
    def _handle_element_deleted(self, event: Event) -> None:
        """
        Handle element deleted events.

        :param event: An Event object representing the element deleted event.
        """
        pass

    @abstractmethod
    def _handle_state_change(self, event: Event) -> None:
        """
        Handle state change events.

        :param event: An Event object representing the state change event.
        """
        pass

    def _handle_other(self, event: Event) -> None:
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

    def handle_event(self, event: Event) -> None:
        if event.type in ("lab_stats", "system_stats") or (
            event.element_type in ("annotation", "connectormapping")
        ):
            # Some events are unused in the client library
            _LOGGER.debug(f"Received an unused event: {event}")
            return

        try:
            event.lab = self._client_library.get_local_lab(event.lab_id)
        except LabNotFound:
            # lab is not locally joined, so we can ignore its events
            return

        if event.subtype != "created":
            event_types = {
                "node": event.lab.get_node_by_id,
                "interface": event.lab.get_interface_by_id,
                "link": event.lab.get_link_by_id,
            }
            try:
                event.element = event_types[event.element_type](event.element_id)
            except ElementNotFound:
                if event.subtype == "deleted":
                    # Element was likely already deleted in a cascading deletion
                    # (e.g. node being deleted and all its links and interfaces being
                    # deleted with it) so the event is useless
                    return
                else:
                    # A modify event arrived for a missing element - something is wrong
                    raise

        super().handle_event(event)

    def _handle_lab_created(self, event: Event) -> None:
        # we don't care about labs the user hasn't joined,
        # so we don't need the lab creation event
        pass

    def _handle_lab_modified(self, event: Event) -> None:
        event.lab.update_lab_properties(event.data)

    def _handle_lab_deleted(self, event: Event) -> None:
        self._client_library._remove_lab_local(event.lab)

    def _handle_lab_state(self, event: Event) -> None:
        event.lab._state = event.data["state"]

    def _handle_element_created(self, event: Event) -> None:
        new_element: Node | Interface | Link
        existing_elements: dict = getattr(event.lab, f"_{event.element_type}s", {})
        if event.element_id in existing_elements:
            # element was created by this client, so it already exists,
            # but the event might at least contain some new data
            # that was added during serverside creation
            event.element = existing_elements[event.element_id]
            self._handle_element_modified(event)
            return
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
            # "Annotation" and "ConnectorMapping" were weeded out before,
            # so we should never get here
            _LOGGER.warning(f"Received an invalid event. {event}")
            return
        new_element._state = event.data.get("state")

    def _handle_element_modified(self, event: Event) -> None:
        if event.element_type == "node":
            event.element._update(
                event.data, exclude_configurations=False, push_to_server=False
            )

        elif event.element_type == "interface":
            event.element._update(event.data, push_to_server=False)

        elif event.element_type == "link":
            # only sends link_capture_key which is not used by the client,
            # so we discard the message
            pass

        else:
            # "Annotation" and "ConnectorMapping" were weeded out before,
            # so we should never get here
            _LOGGER.warning(f"Received an invalid event. {event}")

    def _handle_element_deleted(self, event: Event) -> None:
        if event.element_type == "node":
            event.lab._remove_node_local(event.element)

        elif event.element_type == "interface":
            event.lab._remove_interface_local(event.element)

        elif event.element_type == "link":
            event.lab._remove_link_local(event.element)

        else:
            # "Annotation" and "ConnectorMapping" were weeded out before,
            # so we should never get here
            _LOGGER.warning(f"Received an invalid event. {event}")

    def _handle_state_change(self, event: Event) -> None:
        event.element._state = event.subtype_original
