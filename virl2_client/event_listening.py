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

import asyncio
import contextlib
import json
import logging
import ssl
import threading
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import aiohttp

from .event_handling import Event, EventHandler

if TYPE_CHECKING:
    from collections.abc import Coroutine

    from .virl2_client import ClientLibrary

_LOGGER = logging.getLogger(__name__)


class EventListener:
    def __init__(self, client_library: ClientLibrary) -> None:
        """
        Initialize an EventListener instance.
        EventListener creates and listens to a websocket connection to the server.
        Events are then sent to the EventHandler instance for handling.
        Use start_listening() to open and stop_listening() to close connection.

        :param client_library: Parent ClientLibrary instance which provides connection
            info and is modified when synchronizing.
        """
        self._thread: threading.Thread | None = None
        self._ws_close: Coroutine | None = None
        self._ws_close_event: asyncio.Event | None = None
        self._ws_connected_event: threading.Event | None = None

        self._listening = False
        self._connected = False
        self._auth_data = None
        self._queue: asyncio.Queue | None = None
        self._ws_url: str | None = None
        self._ssl_context: ssl.SSLContext | None = None

        self._event_handler = EventHandler(client_library)
        self._init_ws_connection_data(client_library)

    def __bool__(self) -> bool:
        """Report whether the listener is currently active.

        :returns: True if actively listening, else False.
        """
        return self._listening

    def _init_ws_connection_data(self, client_library: ClientLibrary) -> None:
        """
        Create an SSL context and Websocket url from client library data.

        :param client_library: The client library instance.
        """
        ssl_verify = client_library._ssl_verify
        # Create an SSL context based on the 'verify' str/bool,
        # since that is what aiohttp asks for.
        if ssl_verify is False:
            # Caller set ssl_verify=False (lab/dev); TLS verification is intentionally off.
            ssl_context = ssl.create_default_context()  # NOSONAR
            ssl_context.check_hostname = False  # NOSONAR
            ssl_context.verify_mode = ssl.CERT_NONE  # NOSONAR
        elif isinstance(ssl_verify, str):
            if not Path(ssl_verify).is_file():
                # Raise explicitly rather than silently falling back to the
                # default trust store: a configured cert path that can't be
                # read is almost always a deployment error.
                raise FileNotFoundError(
                    f"ssl_verify path is not a readable file: {ssl_verify!r}"
                )
            # Custom CA bundle; hostname check remains enabled (create_default_context).
            ssl_context = ssl.create_default_context()  # NOSONAR
            ssl_context.load_verify_locations(ssl_verify)
        else:
            ssl_context = None
        self._ssl_context = ssl_context

        # Take the base URL and modify it into the WS url. Map http->ws and
        # https->wss so allow_http=True deployments also get a working event
        # listener; previously this was hardcoded to wss://.
        url_pieces = urlparse(client_library.url)
        ws_scheme = "ws" if url_pieces.scheme == "http" else "wss"
        ws_url_pieces = url_pieces._replace(scheme=ws_scheme, path="ws/ui")
        self._ws_url = str(ws_url_pieces.geturl())

        self._auth_data = {
            "token": client_library._session.auth.token,
            "client_uuid": client_library.uuid,
        }

    def start_listening(self) -> None:
        """Start listening for events."""
        if self._listening:
            return

        self._ws_connected_event = threading.Event()
        self._listening = True

        self._thread = threading.Thread(
            target=asyncio.run, args=(self._listen(),), daemon=True
        )
        self._thread.start()

    def stop_listening(self) -> None:
        """Stop listening for events."""
        if not self._listening:
            return

        self._ws_connected_event.wait()

        self._ws_close_event.set()
        self._thread.join()

        self._thread = None
        self._ws_connected_event = None
        self._listening = False

    async def _listen(self) -> list[None]:
        """Run websocket client and parser tasks.

        :returns: Gathered task results.
        """
        _LOGGER.info("Starting listening")
        self._queue = asyncio.Queue()
        self._ws_close_event = asyncio.Event()

        client_task = asyncio.create_task(self._ws_client())
        parser_task = asyncio.create_task(self._parse())
        result = await asyncio.gather(client_task, parser_task)

        self._ws_close_event = None
        self._queue = None
        _LOGGER.info("Listening over")
        return result

    async def _parse(self) -> None:
        """Parse queue messages into events and dispatch them."""
        close_wait = asyncio.create_task(self._ws_close_event.wait())
        # Wrap close_wait in a single shield so asyncio.wait() doesn't cancel
        # the underlying task when the queue task completes first.
        close_sentinel = asyncio.shield(close_wait)
        try:
            while True:
                queue_get = asyncio.create_task(self._queue.get())
                await asyncio.wait(
                    {queue_get, close_sentinel},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if close_wait.done():
                    _LOGGER.info("Closing connection")
                    # Cancel and drain the pending queue_get so asyncio
                    # doesn't emit "Task was destroyed but it is pending"
                    # warnings at shutdown.
                    if not queue_get.done():
                        queue_get.cancel()
                        with contextlib.suppress(asyncio.CancelledError):
                            await queue_get
                    if self._ws_close is not None:
                        with contextlib.suppress(
                            asyncio.CancelledError, OSError, aiohttp.ClientError
                        ):
                            await self._ws_close
                    return
                event = Event(json.loads(queue_get.result()))
                self._event_handler.handle_event(event)
                self._queue.task_done()
        finally:
            if not close_wait.done():
                close_wait.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await close_wait

    async def _ws_client(self) -> None:
        """Run websocket client loop and enqueue received messages."""
        try:
            async with (
                aiohttp.ClientSession() as session,
                session.ws_connect(
                    self._ws_url,
                    ssl=self._ssl_context,
                    heartbeat=30,
                ) as ws,
            ):
                await ws.send_json(self._auth_data)
                self._connected = True
                _LOGGER.info("Connected successfully")
                self._ws_close = ws.close()
                self._ws_connected_event.set()
                async for msg in ws:
                    self._queue.put_nowait(msg.data)
        except aiohttp.ClientError:
            _LOGGER.exception("Connection closed unexpectedly")
        finally:
            # ws.close() returns a coroutine. Clear our reference BEFORE
            # cancelling it so _parse() cannot observe a half-closed coroutine
            # and await it (which would raise). Any awaiter reading
            # self._ws_close while holding the previous reference is fine:
            # after the `async with` exited, the websocket is already closed.
            pending_close = self._ws_close
            self._ws_close = None
            if pending_close is not None:
                pending_close.close()
            self._ws_close_event.set()
            self._ws_connected_event.set()
            self._connected = False
        _LOGGER.info("Disconnected")
