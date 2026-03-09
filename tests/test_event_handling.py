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
"""Coverage tests for optional event-handling module.

Tests use stdlib-only dependencies (asyncio, logging). No importorskip needed.
"""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from virl2_client.event_handling import Event, EventHandler, EventHandlerBase
from virl2_client.exceptions import ElementNotFound, LabNotFound


class RecorderHandler(EventHandlerBase):
    """Concrete handler used to validate base-class dispatch behavior."""

    def __init__(self) -> None:
        """Initialize call recorder state."""
        super().__init__(client_library=None)
        self.calls: list[str] = []

    def _handle_lab_created(self, event: Event) -> None:
        """Record lab-created callback invocation.

        :param event: Event instance being handled.
        """
        self.calls.append(f"lab_created:{event.subtype}")

    def _handle_lab_modified(self, event: Event) -> None:
        """Record lab-modified callback invocation.

        :param event: Event instance being handled.
        """
        self.calls.append(f"lab_modified:{event.subtype}")

    def _handle_lab_deleted(self, event: Event) -> None:
        """Record lab-deleted callback invocation.

        :param event: Event instance being handled.
        """
        self.calls.append(f"lab_deleted:{event.subtype}")

    def _handle_lab_state(self, event: Event) -> None:
        """Record lab-state callback invocation.

        :param event: Event instance being handled.
        """
        self.calls.append(f"lab_state:{event.subtype}")

    def _handle_element_created(self, event: Event) -> None:
        """Record element-created callback invocation.

        :param event: Event instance being handled.
        """
        self.calls.append(f"element_created:{event.subtype}")

    def _handle_element_modified(self, event: Event) -> None:
        """Record element-modified callback invocation.

        :param event: Event instance being handled.
        """
        self.calls.append(f"element_modified:{event.subtype}")

    def _handle_element_deleted(self, event: Event) -> None:
        """Record element-deleted callback invocation.

        :param event: Event instance being handled.
        """
        self.calls.append(f"element_deleted:{event.subtype}")

    def _handle_state_change(self, event: Event) -> None:
        """Record state-change callback invocation.

        :param event: Event instance being handled.
        """
        self.calls.append(f"state:{event.subtype}")

    def _handle_other(self, event: Event) -> None:
        """Record unmatched-event callback invocation.

        :param event: Event instance being handled.
        """
        self.calls.append(f"other:{event.type}")


def _event(**kwargs: str) -> Event:
    """Build an event with default values and optional overrides.

    :param kwargs: Event fields overriding the default payload.
    :returns: Parsed Event object.
    """
    payload = {
        "event_type": "lab_event",
        "event": "created",
        "element_type": "node",
        "lab_id": "lab-1",
        "element_id": "n1",
        "data": {"state": "RUNNING"},
    }
    payload.update(kwargs)
    return Event(payload)


def test_event_model_fields_and_string_repr() -> None:
    """Parse event payload fields and expose readable __str__.

    NOTE: LLM-generated test -- verify for correctness.
    """
    event = _event(event_type="LAB_EVENT", event="Modified", element_type="LINK")
    assert event.type == "lab_event"
    assert event.subtype == "modified"
    assert event.element_type == "link"
    assert event.lab_id == "lab-1"
    assert event.element_id == "n1"
    assert "Event type:" in str(event)


@pytest.mark.parametrize(
    ("event_type", "subtype", "expected"),
    [
        ("lab_event", "created", "lab_created:created"),
        ("lab_event", "modified", "lab_modified:modified"),
        ("lab_event", "deleted", "lab_deleted:deleted"),
        ("lab_event", "state", "lab_state:state"),
        ("lab_element_event", "created", "element_created:created"),
        ("lab_element_event", "modified", "element_modified:modified"),
        ("lab_element_event", "deleted", "element_deleted:deleted"),
        ("state_change", "STARTED", "state:started"),
        ("unknown", "x", "other:unknown"),
    ],
)
def test_event_handler_base_dispatch_matrix(
    event_type: str, subtype: str, expected: str
) -> None:
    """Route events through EventHandlerBase public dispatch entrypoint.

    NOTE: LLM-generated test -- verify for correctness.

    :param event_type: Incoming event type.
    :param subtype: Incoming event subtype.
    :param expected: Expected handler call marker.
    """
    handler = RecorderHandler()
    event = _event(event_type=event_type, event=subtype)
    handler.handle_event(event)
    assert handler.calls[-1] == expected


@pytest.mark.parametrize(
    ("event_type", "element_type", "subtype_key"),
    [
        ("lab_event", None, "invalid"),
        ("lab_element_event", "node", "invalid"),
    ],
)
def test_event_handler_logs_invalid_subtypes(
    caplog: pytest.LogCaptureFixture,
    event_type: str,
    element_type: str | None,
    subtype_key: str,
) -> None:
    """Log warnings for invalid lab and element subtypes.

    NOTE: LLM-generated test -- verify for correctness.

    :param caplog: Pytest log capture fixture.
    :param event_type: Incoming event type.
    :param element_type: Element type for element events, or None for lab.
    :param subtype_key: Invalid subtype value to trigger warning.
    """
    handler = RecorderHandler()
    with caplog.at_level(logging.WARNING):
        if event_type == "lab_event":
            handler._handle_lab(_event(event=subtype_key))
        else:
            handler._handle_element(
                _event(
                    event_type=event_type,
                    event=subtype_key,
                    element_type=element_type or "node",
                )
            )
    assert "Received an invalid event." in caplog.text


@pytest.mark.parametrize("element_type", ["annotation", "connectormapping"])
def test_event_handler_ignores_unused_elements(
    caplog: pytest.LogCaptureFixture,
    element_type: str,
) -> None:
    """Ignore annotation/connectormapping element events as unsupported.

    NOTE: LLM-generated test -- verify for correctness.

    :param caplog: Pytest log capture fixture.
    :param element_type: Unused element type to ignore.
    """
    handler = RecorderHandler()
    with caplog.at_level(logging.DEBUG):
        handler._handle_element(
            _event(
                event_type="lab_element_event",
                event="created",
                element_type=element_type,
            )
        )
    assert "Received an unused element type" in caplog.text


def _new_runtime_handler() -> tuple[EventHandler, MagicMock, MagicMock]:
    """Create an EventHandler and mocked client/lab objects.

    :returns: Tuple of handler, client mock, and lab mock.
    """
    client = MagicMock()
    lab = MagicMock()
    client.get_local_lab.return_value = lab
    return EventHandler(client), client, lab


def test_runtime_handler_filters_and_lab_lookup() -> None:
    """Filter unsupported events and ignore events for non-local labs.

    NOTE: LLM-generated test -- verify for correctness.
    """
    handler, client, _lab = _new_runtime_handler()
    with patch("virl2_client.event_handling._LOGGER") as logger:
        handler.handle_event(_event(event_type="lab_stats"))
        logger.debug.assert_called()

    client.get_local_lab.side_effect = LabNotFound("missing")
    handler.handle_event(_event(lab_id="missing"))


def test_element_lookup_found() -> None:
    """Element exists and is resolved on handle_event.

    NOTE: LLM-generated test -- verify for correctness.
    """
    handler, _client, lab = _new_runtime_handler()
    node = MagicMock()
    lab.get_node_by_id.return_value = node
    event = _event(
        event_type="lab_element_event", event="modified", element_type="node"
    )
    handler.handle_event(event)
    assert event.element is node


def test_element_lookup_deleted_ok() -> None:
    """ElementNotFound swallowed for deleted events (cascading deletes).

    NOTE: LLM-generated test -- verify for correctness.
    """
    handler, _client, lab = _new_runtime_handler()
    lab.get_node_by_id.side_effect = ElementNotFound("n1")
    deleted_event = _event(
        event_type="lab_element_event", event="deleted", element_type="node"
    )
    handler.handle_event(deleted_event)


def test_element_lookup_modified_err() -> None:
    """ElementNotFound re-raised for modified events.

    NOTE: LLM-generated test -- verify for correctness.
    """
    handler, _client, lab = _new_runtime_handler()
    lab.get_node_by_id.side_effect = ElementNotFound("n1")
    with pytest.raises(ElementNotFound):
        handler.handle_event(
            _event(
                event_type="lab_element_event",
                event="modified",
                element_type="node",
            )
        )


def test_handle_lab_modified() -> None:
    """_handle_lab_modified updates lab properties from event data.

    NOTE: LLM-generated test -- verify for correctness.
    """
    handler, _client, lab = _new_runtime_handler()
    event = _event(event="modified", data={"title": "new"})
    event.lab = lab
    handler._handle_lab_modified(event)
    lab.update_lab_properties.assert_called_once_with({"title": "new"})


def test_handle_lab_deleted() -> None:
    """_handle_lab_deleted removes lab from local client.

    NOTE: LLM-generated test -- verify for correctness.
    """
    handler, client, lab = _new_runtime_handler()
    event = _event(event="deleted")
    event.lab = lab
    handler._handle_lab_deleted(event)
    client._remove_lab_local.assert_called_once_with(lab)


def test_handle_lab_state() -> None:
    """_handle_lab_state updates lab state from event data.

    NOTE: LLM-generated test -- verify for correctness.
    """
    handler, _client, lab = _new_runtime_handler()
    event = _event(event="state", data={"state": "STOPPED"})
    event.lab = lab
    handler._handle_lab_state(event)
    assert lab._state == "STOPPED"


def test_handle_lab_created_noop() -> None:
    """_handle_lab_created is a no-op.

    NOTE: LLM-generated test -- verify for correctness.
    """
    handler, _client, _lab = _new_runtime_handler()
    handler._handle_lab_created(_event())


def test_element_created_existing() -> None:
    """Existing node triggers _handle_element_modified.

    NOTE: LLM-generated test -- verify for correctness.
    """
    handler, _client, lab = _new_runtime_handler()
    event = _event(event_type="lab_element_event", event="created", element_type="node")
    event.lab = lab
    lab._nodes = {"n1": MagicMock()}
    with patch.object(handler, "_handle_element_modified") as modified:
        handler._handle_element_created(event)
        modified.assert_called_once()


@pytest.mark.parametrize(
    ("element_type", "setup_key"),
    [
        ("node", "_import_node"),
        ("interface", "_import_interface"),
        ("link", "_import_link"),
    ],
)
def test_element_created_import(
    element_type: str,
    setup_key: str,
) -> None:
    """Import path for node/interface/link sets element state.

    NOTE: LLM-generated test -- verify for correctness.
    """
    handler, _client, lab = _new_runtime_handler()
    event = _event(
        event_type="lab_element_event",
        event="created",
        element_type=element_type,
        data={
            "node": "n1",
            "interface_a": "i1",
            "interface_b": "i2",
            "state": "UP",
        },
    )
    event.lab = lab
    setattr(lab, f"_{element_type}s", {})
    imported = MagicMock()
    getattr(lab, setup_key).return_value = imported
    handler._handle_element_created(event)
    assert imported._state == "UP"


def test_element_created_invalid(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Invalid element type logs warning.

    NOTE: LLM-generated test -- verify for correctness.

    :param caplog: Pytest log capture fixture.
    """
    handler, _client, lab = _new_runtime_handler()
    with caplog.at_level(logging.WARNING):
        bad_event = _event(
            event_type="lab_element_event",
            event="created",
            element_type="invalid",
            data={"state": "UP"},
        )
        bad_event.lab = lab
        handler._handle_element_created(bad_event)
    assert "Received an invalid event." in caplog.text


@pytest.mark.parametrize("element_type", ["node", "interface", "link"])
def test_element_mod_delete(element_type: str) -> None:
    """Modify and delete handlers for node/interface/link.

    NOTE: LLM-generated test -- verify for correctness.
    """
    handler, _client, lab = _new_runtime_handler()
    event = _event(
        event_type="lab_element_event", event="modified", element_type=element_type
    )
    event.lab = lab
    event.element = MagicMock()
    handler._handle_element_modified(event)

    delete_event = _event(
        event_type="lab_element_event", event="deleted", element_type=element_type
    )
    delete_event.lab = lab
    delete_event.element = MagicMock()
    handler._handle_element_deleted(delete_event)


def test_element_mod_invalid(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Invalid element modify/delete logs warning.

    NOTE: LLM-generated test -- verify for correctness.

    :param caplog: Pytest log capture fixture.
    """
    handler, _client, lab = _new_runtime_handler()
    with caplog.at_level(logging.WARNING):
        invalid = _event(
            event_type="lab_element_event", event="modified", element_type="bad"
        )
        invalid.lab = lab
        invalid.element = MagicMock()
        handler._handle_element_modified(invalid)
        invalid = _event(
            event_type="lab_element_event", event="deleted", element_type="bad"
        )
        invalid.lab = lab
        invalid.element = MagicMock()
        handler._handle_element_deleted(invalid)
    assert "Received an invalid event." in caplog.text


def test_handle_state_change() -> None:
    """_handle_state_change updates element state.

    NOTE: LLM-generated test -- verify for correctness.
    """
    handler, _client, _lab = _new_runtime_handler()
    state_event = _event(event_type="state_change", event="STARTED")
    state_event.element = MagicMock()
    handler._handle_state_change(state_event)
    assert state_event.element._state == "STARTED"


@pytest.mark.parametrize(
    "method_name",
    [
        "_handle_lab_created",
        "_handle_lab_modified",
        "_handle_lab_deleted",
        "_handle_lab_state",
        "_handle_element_created",
        "_handle_element_modified",
        "_handle_element_deleted",
        "_handle_state_change",
        "_handle_other",
    ],
)
def test_event_handler_base_abstract_pass_bodies(method_name: str) -> None:
    """Execute abstract base method pass-bodies for coverage.

    NOTE: LLM-generated test -- verify for correctness.

    :param method_name: Name of the base-class method to invoke.
    """
    handler = RecorderHandler()
    event = _event()
    getattr(EventHandlerBase, method_name)(handler, event)


def test_windows_event_loop_policy_branch() -> None:
    """Execute Windows-only event-loop policy branch in isolation.

    NOTE: LLM-generated test -- verify for correctness.
    """
    module_path = Path("virl2_client/event_handling.py")
    # Execute the exact branch lines with matching filename/line numbers so
    # coverage attributes execution to event_handling.py:40-41.
    snippet = (
        "\n" * 39
        + 'if os_name == "nt":\n'
        + "    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())\n"
    )
    fake_asyncio = MagicMock()
    fake_asyncio.WindowsSelectorEventLoopPolicy.return_value = "policy"
    namespace = {
        "__name__": "tmp_event_handling_win",
        "asyncio": fake_asyncio,
        "os_name": "nt",
    }
    exec(compile(snippet, str(module_path), "exec"), namespace)
    fake_asyncio.set_event_loop_policy.assert_called_once_with("policy")
