#!/usr/bin/env python3
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

"""Subscribe to controller websocket events.

The built-in ``EventListener`` opens a websocket to the controller,
parses each frame into an ``Event`` and dispatches it through an
``EventHandler`` that also updates the locally-cached lab/node/link
state. This example plugs a trivial logging handler on top so every
event is printed as it arrives.

Run against an active controller::

    CML_URL=https://cml.example \\
    CML_USERNAME=admin CML_PASSWORD=... \\
    python examples/events.py

Press Ctrl-C to stop.
"""

from __future__ import annotations

import getpass
import os
import sys
import time

from virl2_client import ClientLibrary
from virl2_client.event_handling import Event, EventHandler
from virl2_client.event_listening import EventListener


def _prompt(env_var: str, prompt: str, *, secret: bool = False) -> str:
    value = os.environ.get(env_var)
    if value is not None:
        return value
    reader = getpass.getpass if secret else input
    return reader(prompt)


class LoggingEventHandler(EventHandler):
    """``EventHandler`` that prints every event before dispatching it.

    Inheriting from ``EventHandler`` (rather than ``EventHandlerBase``)
    lets us keep the default bookkeeping that updates the local model,
    while layering extra logging on top.
    """

    def handle_event(self, event: Event) -> None:
        """Print a one-line summary then delegate to the base handler."""
        print(
            f"[event] type={event.type or '?':<18} "
            f"subtype={event.subtype or '?':<10} "
            f"element={event.element_type or '-':<10} "
            f"lab={event.lab_id or '-'} "
            f"element_id={event.element_id or '-'}"
        )
        super().handle_event(event)


def main() -> int:
    url = _prompt("CML_URL", "controller URL or hostname: ")
    username = _prompt("CML_USERNAME", "username: ")
    password = _prompt("CML_PASSWORD", "password: ", secret=True)

    client = ClientLibrary(url, username, password, ssl_verify=False)

    # Wire up the custom handler *before* calling start_event_listening(),
    # following the pattern documented on ClientLibrary.start_event_listening:
    # build a listener, attach the handler, assign it to the client, then
    # start. Starting first and swapping the handler afterwards would race
    # with events that arrive between start and swap.
    listener = EventListener(client)
    listener._event_handler = LoggingEventHandler(client)
    client.event_listener = listener
    client.start_event_listening()
    print("Listening for events. Press Ctrl-C to stop.")

    try:
        while True:
            # Keep the main thread alive; the listener runs in its own
            # background thread and delivers events via the handler.
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping listener...")
    finally:
        client.stop_event_listening()
    return 0


if __name__ == "__main__":
    sys.exit(main())
