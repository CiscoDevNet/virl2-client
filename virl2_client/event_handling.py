from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from os import name as os_name
from typing import TYPE_CHECKING, Any, Optional, Union

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
    """An event object, stores parsed info about the event it represents."""

    def __init__(self, event_dict: dict[str, Any]):
        self.type: str = (event_dict.get("event_type") or "").casefold()
        self.subtype_original: Optional[str] = event_dict.get("event")
        self.subtype: str = (self.subtype_original or "").casefold()
        self.element_type: str = (event_dict.get("element_type") or "").casefold()
        self.lab_id: str = event_dict.get("lab_id", "")
        self.element_id: str = event_dict.get("element_id", "")
        self.data: Optional[dict] = event_dict.get("data")
        self.lab: Optional[Lab] = None
        self.element: Union[Node, Interface, Link, None] = None


class EventHandlerBase(ABC):
    """
    Abstract base class for event handlers. Subclass this if you
    want to implement the entire event handling mechanism from scratch,
    otherwise subclass EventHandler instead.
    """

    def __init__(self, client_library: ClientLibrary = None):
        self.client_library = client_library

    def parse_event(self, event: Event) -> None:
        if event.type == "lab_event":
            self._parse_lab(event)
        elif event.type == "lab_element_event":
            self._parse_element(event)
        elif event.type == "state_change":
            self._parse_state_change(event)
        else:
            self._parse_other(event)

    def _parse_lab(self, event: Event) -> None:
        if event.subtype == "created":
            self._parse_lab_created(event)
        elif event.subtype == "modified":
            self._parse_lab_modified(event)
        elif event.subtype == "deleted":
            self._parse_lab_deleted(event)
        elif event.subtype == "state":
            self._parse_lab_state(event)
        else:
            _LOGGER.warning("Received an invalid lab event (%s)", event.subtype)

    @abstractmethod
    def _parse_lab_created(self, event: Event) -> None:
        pass

    @abstractmethod
    def _parse_lab_modified(self, event: Event) -> None:
        pass

    @abstractmethod
    def _parse_lab_deleted(self, event: Event) -> None:
        pass

    @abstractmethod
    def _parse_lab_state(self, event: Event) -> None:
        pass  # TODO: implement lab state sync via events

    def _parse_element(self, event: Event) -> None:
        if event.subtype == "created":
            self._parse_element_created(event)
        elif event.subtype == "modified":
            self._parse_element_modified(event)
        elif event.subtype == "deleted":
            self._parse_element_deleted(event)
        else:
            _LOGGER.warning("Received an invalid element event (%s)", event.subtype)

    @abstractmethod
    def _parse_element_created(self, event: Event) -> None:
        pass

    @abstractmethod
    def _parse_element_modified(self, event: Event) -> None:
        pass

    @abstractmethod
    def _parse_element_deleted(self, event: Event) -> None:
        pass

    @abstractmethod
    def _parse_state_change(self, event: Event) -> None:
        pass

    def _parse_other(self, event: Event) -> None:
        # All other events are useless to the client, but in case some handling
        # needs to be done on them, this method can be overridden
        pass


class EventHandler(EventHandlerBase):
    """Handler for JSON events received from controller over websockets.
    Used by EventListener by default, but can be subclassed and methods overridden
    to change/extend the handling mechanism, then passed to EventListener."""

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
                # This should really raise the following error, but the order
                # in which the events arrive is inconsistent, so sometimes
                # when e.g. a node is deleted, the node deletion event
                # arrives before the interface deletion events, so the interfaces
                # no longer exist by the time their deletion events arrive,
                # which would raise an unwarranted DesynchronizedError
                # so instead for now, we just ignore those events
                # TODO: implement serverside echo prevention and consistent message
                #  order for all events and raise the following error
                # raise DesynchronizedError(
                #     "{} {} not found in lab {}, "
                #     "likely due to desynchronization".format(
                #         event.element_type,
                #         event.element_id,
                #         event.lab_id,
                #     )
                # )

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
        existing_elements: dict = getattr(event.lab, f"_{event.element_type}s", {})
        if event.element_id in existing_elements:
            # element was created by this client, so it already exists,
            # but the event might at least contain some new data
            # that was added during serverside creation
            event.element = existing_elements[event.element_id]
            self._parse_element_modified(event)
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
            _LOGGER.warning("Received an invalid element type (%s)", event.element_type)
            return
        new_element._state = event.data.get("state")

    def _parse_element_modified(self, event: Event) -> None:
        if event.element_type == "node":
            event.element.update(event.data, exclude_configurations=False)

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
                "Received an invalid lab element event (%s %s)",
                event.subtype,
                event.element_type,
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
                "Received an invalid lab element event (%s %s)",
                event.subtype,
                event.element_type,
            )

    def _parse_state_change(self, event: Event) -> None:
        event.element._state = event.subtype_original
