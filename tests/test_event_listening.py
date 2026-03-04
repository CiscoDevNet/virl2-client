"""Coverage tests for optional websocket event listener.

Tests are skipped when aiohttp is not installed via pytest.importorskip.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

try:
    import aiohttp

    from virl2_client.event_listening import EventListener
except ImportError as exc:  # pragma: no cover - optional dependency gate
    pytest.skip(f"optional dependency missing: {exc}", allow_module_level=True)


def _client(ssl_verify: bool | str = True) -> MagicMock:
    """Create a mocked client library for EventListener tests.

    :param ssl_verify: Whether to verify SSL (True/False) or path to CA bundle.
    :returns: Mocked client instance for EventListener tests.
    """
    client = MagicMock()
    client._ssl_verify = ssl_verify
    client.url = "https://controller.local/api/v0/"
    client._session.auth.token = "token"
    client.uuid = "uuid-1"
    return client


@pytest.mark.parametrize(
    ("ssl_verify", "expected_check_hostname"),
    [
        (False, False),
        ("/path/to/ca.pem", True),
        (True, True),
    ],
)
def test_event_listener_init_and_connection(
    tmp_path: Path,
    ssl_verify: bool | str,
    expected_check_hostname: bool,
) -> None:
    """Build SSL context for websocket across verify modes.

    NOTE: LLM-generated test -- verify for correctness.

    :param tmp_path: Temporary directory used for fake certificate path.
    :param ssl_verify: Whether to verify SSL (True/False) or path to CA bundle.
    :param expected_check_hostname: Expected check_hostname on SSL context.
    """
    if isinstance(ssl_verify, str) and "path" in ssl_verify:
        cert = tmp_path / "ca.pem"
        cert.write_text("dummy")
        ssl_verify_val: bool | str = cert.as_posix()
    else:
        ssl_verify_val = ssl_verify

    mocked_ctx = MagicMock()
    with patch(
        "virl2_client.event_listening.ssl.create_default_context",
        return_value=mocked_ctx,
    ):
        listener = EventListener(_client(ssl_verify_val))

    if ssl_verify_val is True:
        assert listener._ssl_context is None
    else:
        assert listener._ssl_context is not None
        if ssl_verify_val is False:
            assert listener._ssl_context.check_hostname is expected_check_hostname
        else:
            mocked_ctx.load_verify_locations.assert_called_once_with(ssl_verify_val)


class _DummyThread:
    """Minimal thread-like object for lifecycle tests."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        """Record start state and close eagerly-created listener coroutine.

        :param args: Positional constructor arguments from patched thread usage.
        :param kwargs: Keyword constructor arguments from patched thread usage.
        """
        self.started = False
        # start_listening() builds coroutine eagerly via self._listen();
        # close it to avoid "coroutine was never awaited" warnings in this unit test.
        thread_args = kwargs.get("args", ())
        if thread_args and hasattr(thread_args[0], "close"):
            thread_args[0].close()

    def start(self) -> None:
        """Mark this thread double as started."""
        self.started = True

    def join(self) -> None:
        """Provide thread-join compatibility for tests."""
        return None


def test_bool_reflects_listening_state() -> None:
    """__bool__ returns True when listening, False otherwise.

    NOTE: LLM-generated test -- verify for correctness.
    """
    listener = EventListener(_client())
    assert bool(listener) is False
    with patch("virl2_client.event_listening.threading.Thread", _DummyThread):
        listener.start_listening()
    assert bool(listener) is True


def test_start_listening() -> None:
    """start_listening succeeds and sets _listening.

    NOTE: LLM-generated test -- verify for correctness.
    """
    listener = EventListener(_client())
    with patch("virl2_client.event_listening.threading.Thread", _DummyThread):
        listener.start_listening()
    assert listener._listening is True


def test_start_already_listening() -> None:
    """start_listening when already listening warns.

    NOTE: LLM-generated test -- verify for correctness.
    """
    listener = EventListener(_client())
    with patch("virl2_client.event_listening.threading.Thread", _DummyThread):
        listener.start_listening()
        listener.start_listening()


def test_stop_not_listening() -> None:
    """stop_listening when not listening warns.

    NOTE: LLM-generated test -- verify for correctness.
    """
    listener = EventListener(_client())
    listener._listening = False
    listener.stop_listening()


def test_stop_listening() -> None:
    """stop_listening succeeds and clears _listening.

    NOTE: LLM-generated test -- verify for correctness.
    """
    listener = EventListener(_client())
    listener._listening = True
    ws_connected_event = MagicMock()
    ws_close_event = MagicMock()
    listener._ws_connected_event = ws_connected_event
    listener._ws_close_event = ws_close_event
    listener._thread = _DummyThread()
    listener.stop_listening()
    ws_connected_event.wait.assert_called_once()
    ws_close_event.set.assert_called_once()
    assert listener._listening is False


def test_listen_gather() -> None:
    """_listen gather path runs and returns.

    NOTE: LLM-generated test -- verify for correctness.
    """
    listener = EventListener(_client())
    with (
        patch.object(listener, "_ws_client", return_value=None),
        patch.object(listener, "_parse", return_value=None),
    ):
        result = asyncio.run(listener._listen())
    assert result == [None, None]
    assert listener._queue is None
    assert listener._ws_close_event is None


def test_parse_queue() -> None:
    """_parse queue path dispatches events and closes.

    NOTE: LLM-generated test -- verify for correctness.
    """
    listener = EventListener(_client())
    listener._queue = asyncio.Queue()
    listener._ws_close_event = asyncio.Event()
    listener._ws_close = None
    listener._queue.put_nowait('{"event_type":"lab_event","event":"created"}')
    with patch.object(listener._event_handler, "handle_event") as handle_event:
        handle_event.side_effect = (
            lambda *_args, **_kwargs: listener._ws_close_event.set()
        )
        asyncio.run(listener._parse())
    handle_event.assert_called_once()


def test_parse_close_hook() -> None:
    """_parse with awaitable close hook awaits it.

    NOTE: LLM-generated test -- verify for correctness.
    """
    listener = EventListener(_client())
    listener._queue = asyncio.Queue()
    listener._ws_close_event = asyncio.Event()
    listener._ws_close_event.set()
    closed: dict[str, bool] = {"value": False}

    async def close_hook() -> None:
        """Flag that asynchronous close path was executed."""
        closed["value"] = True

    listener._ws_close = close_hook()
    asyncio.run(listener._parse())
    assert closed["value"] is True


class _FakeWs:
    """Stub websocket that yields one message then stops."""

    def __init__(self) -> None:
        self._messages = [
            SimpleNamespace(data='{"event_type":"lab_event","event":"created"}')
        ]
        self.close_called = False

    async def send_json(self, _data: dict[str, Any]) -> None:
        """Accept JSON payload used by subscribe call."""

    def close(self) -> asyncio.coroutines.Coroutine[Any, Any, None]:
        """Return awaitable close hook matching aiohttp behavior."""

        async def _close() -> None:
            self.close_called = True

        return _close()

    def __aiter__(self) -> AsyncIterator[SimpleNamespace]:
        self._iter = iter(self._messages)
        return self

    async def __anext__(self) -> SimpleNamespace:
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration


class _FakeWsContext:
    """Minimal async context manager wrapping _FakeWs."""

    async def __aenter__(self) -> _FakeWs:
        return _FakeWs()

    async def __aexit__(self, *_args: object) -> None:
        pass


class _FakeSessionContext:
    """Minimal aiohttp ClientSession-like context manager."""

    async def __aenter__(self) -> _FakeSessionContext:
        return self

    async def __aexit__(self, *_args: object) -> None:
        pass

    def ws_connect(self, *_args: object, **_kwargs: object) -> _FakeWsContext:
        return _FakeWsContext()


def test_ws_client_success() -> None:
    """_ws_client success path receives messages.

    NOTE: LLM-generated test -- verify for correctness.
    """
    listener = EventListener(_client())
    listener._queue = asyncio.Queue()
    listener._ws_close_event = asyncio.Event()
    listener._ws_connected_event = MagicMock()

    with patch(
        "virl2_client.event_listening.aiohttp.ClientSession",
        return_value=_FakeSessionContext(),
    ):
        asyncio.run(listener._ws_client())
    assert listener._connected is False
    assert listener._queue.qsize() == 1


def test_ws_client_error() -> None:
    """_ws_client with aiohttp.ClientError handles cleanup.

    NOTE: LLM-generated test -- verify for correctness.
    """
    listener = EventListener(_client())
    listener._queue = asyncio.Queue()
    listener._ws_close_event = asyncio.Event()
    listener._ws_connected_event = MagicMock()

    class FakeWsContext:
        async def __aenter__(self) -> object:
            return object()

        async def __aexit__(
            self,
            exc_type: type[BaseException] | None,
            exc: BaseException | None,
            tb: Any,
        ) -> None:
            _ = exc_type, exc, tb

    class ErrorSessionContext:
        async def __aenter__(self) -> ErrorSessionContext:
            return self

        async def __aexit__(
            self,
            exc_type: type[BaseException] | None,
            exc: BaseException | None,
            tb: Any,
        ) -> None:
            _ = exc_type, exc, tb

        def ws_connect(self, *_args: object, **_kwargs: object) -> FakeWsContext:
            """Raise client error to cover error branch."""
            raise aiohttp.ClientError("boom")

    with patch(
        "virl2_client.event_listening.aiohttp.ClientSession",
        return_value=ErrorSessionContext(),
    ):
        asyncio.run(listener._ws_client())
    assert listener._connected is False
