# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for CopilotService with mocked CopilotClient.

These tests exercise the GObject signal bridge without requiring a real
Copilot CLI or network.  The async bridge is NOT installed; instead we
run coroutines directly with ``asyncio.run()`` and verify the service
logic in isolation.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# -- Minimal GI setup -------------------------------------------------------
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import GLib  # noqa: E402

from copilot_gtk.backend.copilot_service import CopilotService  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers — lightweight fakes for the SDK types we interact with
# ---------------------------------------------------------------------------


@dataclass
class FakeData:
    """Mimics the ``Data`` dataclass from copilot.generated.session_events."""

    delta_content: str | None = None
    content: str | None = None
    message: str | None = None
    title: str | None = None


class FakeEventType:
    """Mimics ``SessionEventType`` enum values we care about."""

    ASSISTANT_MESSAGE_DELTA = "assistant.message_delta"
    ASSISTANT_STREAMING_DELTA = "assistant.streaming_delta"
    ASSISTANT_MESSAGE = "assistant.message"
    SESSION_IDLE = "session.idle"
    SESSION_TITLE_CHANGED = "session.title_changed"
    SESSION_ERROR = "session.error"
    ASSISTANT_TURN_START = "assistant.turn_start"
    ASSISTANT_TURN_END = "assistant.turn_end"


@dataclass
class FakeSessionEvent:
    type: Any
    data: FakeData


class FakeModelInfo:
    """Minimal model info stub."""

    def __init__(self, mid: str, name: str) -> None:
        self.id = mid
        self.name = name


class FakeAuthStatus:
    def __init__(self, authenticated: bool, login: str = "") -> None:
        self.isAuthenticated = authenticated
        self.login = login


class FakeSession:
    """Fake CopilotSession that records calls and lets tests fire events."""

    def __init__(self, session_id: str = "fake-session-1") -> None:
        self.session_id = session_id
        self._handler: Any = None
        self.send = AsyncMock(return_value={"messageId": "msg-1"})
        self.destroy = AsyncMock()
        self.abort = AsyncMock()

    def on(self, handler: Any) -> Any:
        self._handler = handler
        return lambda: None

    def fire_event(self, event: FakeSessionEvent) -> None:
        """Simulate the SDK dispatching an event."""
        if self._handler:
            self._handler(event)


def _make_mock_client(
    session: FakeSession | None = None,
    models: list[FakeModelInfo] | None = None,
    auth: FakeAuthStatus | None = None,
) -> MagicMock:
    """Build a mock CopilotClient with sensible defaults."""
    client = MagicMock()
    client.start = AsyncMock()
    client.stop = AsyncMock()
    client.create_session = AsyncMock(
        return_value=session or FakeSession()
    )
    client.list_models = AsyncMock(return_value=models or [])
    client.get_auth_status = AsyncMock(
        return_value=auth or FakeAuthStatus(True, "testuser")
    )
    return client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCopilotServiceStart:
    """TASK-013: CopilotService.start() calls client.start(), emits ready."""

    def test_start_emits_ready(self) -> None:
        mock_client = _make_mock_client()
        service = CopilotService(client=mock_client)

        ready_received = []
        service.connect("ready", lambda _: ready_received.append(True))

        # Run the async start directly
        asyncio.run(service._start_async())

        mock_client.start.assert_awaited_once()

        # Drain pending GLib idle callbacks
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)

        assert ready_received == [True]

    def test_start_error_emits_error(self) -> None:
        mock_client = _make_mock_client()
        mock_client.start = AsyncMock(
            side_effect=RuntimeError("CLI not found")
        )
        service = CopilotService(client=mock_client)

        with pytest.raises(RuntimeError, match="CLI not found"):
            asyncio.run(service._start_async())


class TestCopilotServiceStop:
    """TASK-017: CopilotService.stop() cleans up."""

    def test_stop_calls_client_stop(self) -> None:
        mock_client = _make_mock_client()
        service = CopilotService(client=mock_client)

        asyncio.run(service._start_async())
        asyncio.run(service._stop_async())

        mock_client.stop.assert_awaited_once()
        assert service._client is None
        assert service._sessions == {}


class TestCopilotServiceCreateConversation:
    """TASK-014: create_conversation creates a session and stores it."""

    def test_creates_session_and_conversation(self) -> None:
        fake_session = FakeSession("sess-abc")
        mock_client = _make_mock_client(session=fake_session)
        service = CopilotService(client=mock_client)

        asyncio.run(service._start_async())
        asyncio.run(service._create_conversation_async("gpt-4"))

        mock_client.create_session.assert_awaited_once()
        call_args = mock_client.create_session.call_args[0][0]
        assert call_args["model"] == "gpt-4"
        assert call_args["streaming"] is True

        assert "sess-abc" in service._conversations
        conv = service._conversations["sess-abc"]
        assert conv.session_id == "sess-abc"
        assert conv.model == "gpt-4"

    def test_create_without_model(self) -> None:
        mock_client = _make_mock_client()
        service = CopilotService(client=mock_client)

        asyncio.run(service._start_async())
        asyncio.run(service._create_conversation_async(""))

        call_args = mock_client.create_session.call_args[0][0]
        assert "model" not in call_args


class TestCopilotServiceSendMessage:
    """TASK-015: send_message adds user message and calls session.send."""

    def test_send_stores_user_and_placeholder(self) -> None:
        fake_session = FakeSession("sess-1")
        mock_client = _make_mock_client(session=fake_session)
        service = CopilotService(client=mock_client)

        asyncio.run(service._start_async())
        asyncio.run(service._create_conversation_async("gpt-4"))
        asyncio.run(service._send_message_async("sess-1", "Hello!"))

        conv = service._conversations["sess-1"]
        assert len(conv.messages) == 2
        assert conv.messages[0].role.value == "user"
        assert conv.messages[0].content == "Hello!"
        assert conv.messages[1].role.value == "assistant"
        assert conv.messages[1].is_streaming is True

        fake_session.send.assert_awaited_once_with({"prompt": "Hello!"})


class TestCopilotServiceListModels:
    """TASK-016: list_models fetches and caches models."""

    def test_list_models_caches(self) -> None:
        models = [
            FakeModelInfo("gpt-4", "GPT-4"),
            FakeModelInfo("claude-sonnet-4-20250514", "Claude"),
        ]
        mock_client = _make_mock_client(models=models)
        service = CopilotService(client=mock_client)

        asyncio.run(service._start_async())
        asyncio.run(service._list_models_async())

        assert len(service._models) == 2
        assert service._models[0].id == "gpt-4"


class TestCopilotServiceEventBridge:
    """TASK-012 / VER-P2-004: SDK events are re-emitted as GObject signals."""

    def test_message_delta_emits_response_chunk(self) -> None:
        from copilot.generated.session_events import SessionEventType

        fake_session = FakeSession("sess-1")
        mock_client = _make_mock_client(session=fake_session)
        service = CopilotService(client=mock_client)

        asyncio.run(service._start_async())
        asyncio.run(service._create_conversation_async("gpt-4"))
        asyncio.run(service._send_message_async("sess-1", "Hi"))

        chunks: list[tuple[str, str]] = []
        service.connect(
            "response-chunk",
            lambda _, sid, delta: chunks.append((sid, delta)),
        )

        # Simulate SDK event
        fake_session.fire_event(
            FakeSessionEvent(
                type=SessionEventType.ASSISTANT_MESSAGE_DELTA,
                data=FakeData(delta_content="Hello"),
            )
        )

        # Drain idle queue
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)

        assert ("sess-1", "Hello") in chunks

        # Check streaming message content was updated
        conv = service._conversations["sess-1"]
        streaming = conv.get_streaming_message()
        assert streaming is not None
        assert "Hello" in streaming.content

    def test_streaming_delta_emits_response_chunk(self) -> None:
        """ASSISTANT_STREAMING_DELTA events should also emit response-chunk."""
        from copilot.generated.session_events import SessionEventType

        fake_session = FakeSession("sess-1")
        mock_client = _make_mock_client(session=fake_session)
        service = CopilotService(client=mock_client)

        asyncio.run(service._start_async())
        asyncio.run(service._create_conversation_async("gpt-4"))
        asyncio.run(service._send_message_async("sess-1", "Hi"))

        chunks: list[tuple[str, str]] = []
        service.connect(
            "response-chunk",
            lambda _, sid, delta: chunks.append((sid, delta)),
        )

        # Simulate SDK streaming event
        fake_session.fire_event(
            FakeSessionEvent(
                type=SessionEventType.ASSISTANT_STREAMING_DELTA,
                data=FakeData(delta_content="World"),
            )
        )

        # Drain idle queue
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)

        assert ("sess-1", "World") in chunks

        conv = service._conversations["sess-1"]
        streaming = conv.get_streaming_message()
        assert streaming is not None
        assert "World" in streaming.content

    def test_session_idle_emits_signal(self) -> None:
        from copilot.generated.session_events import SessionEventType

        fake_session = FakeSession("sess-1")
        mock_client = _make_mock_client(session=fake_session)
        service = CopilotService(client=mock_client)

        asyncio.run(service._start_async())
        asyncio.run(service._create_conversation_async("gpt-4"))

        idles: list[str] = []
        service.connect(
            "session-idle", lambda _, sid: idles.append(sid)
        )

        fake_session.fire_event(
            FakeSessionEvent(
                type=SessionEventType.SESSION_IDLE,
                data=FakeData(),
            )
        )

        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)

        assert "sess-1" in idles

    def test_session_error_emits_error(self) -> None:
        from copilot.generated.session_events import SessionEventType

        fake_session = FakeSession("sess-1")
        mock_client = _make_mock_client(session=fake_session)
        service = CopilotService(client=mock_client)

        asyncio.run(service._start_async())
        asyncio.run(service._create_conversation_async("gpt-4"))

        errors: list[str] = []
        service.connect("error", lambda _, msg: errors.append(msg))

        fake_session.fire_event(
            FakeSessionEvent(
                type=SessionEventType.SESSION_ERROR,
                data=FakeData(message="Something broke"),
            )
        )

        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)

        assert any("Something broke" in e for e in errors)

    def test_assistant_message_finalises_streaming(self) -> None:
        from copilot.generated.session_events import SessionEventType

        fake_session = FakeSession("sess-1")
        mock_client = _make_mock_client(session=fake_session)
        service = CopilotService(client=mock_client)

        asyncio.run(service._start_async())
        asyncio.run(service._create_conversation_async("gpt-4"))
        asyncio.run(service._send_message_async("sess-1", "Q"))

        completes: list[tuple[str, str]] = []
        service.connect(
            "response-complete",
            lambda _, sid, content: completes.append((sid, content)),
        )

        fake_session.fire_event(
            FakeSessionEvent(
                type=SessionEventType.ASSISTANT_MESSAGE,
                data=FakeData(content="Full answer"),
            )
        )

        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)

        assert ("sess-1", "Full answer") in completes

        conv = service._conversations["sess-1"]
        last = conv.get_last_assistant_message()
        assert last is not None
        assert last.content == "Full answer"
        assert last.is_streaming is False

    def test_title_changed_updates_conversation(self) -> None:
        from copilot.generated.session_events import SessionEventType

        fake_session = FakeSession("sess-1")
        mock_client = _make_mock_client(session=fake_session)
        service = CopilotService(client=mock_client)

        asyncio.run(service._start_async())
        asyncio.run(service._create_conversation_async("gpt-4"))

        titles: list[tuple[str, str]] = []
        service.connect(
            "session-title-changed",
            lambda _, sid, title: titles.append((sid, title)),
        )

        fake_session.fire_event(
            FakeSessionEvent(
                type=SessionEventType.SESSION_TITLE_CHANGED,
                data=FakeData(title="Weather chat"),
            )
        )

        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)

        assert ("sess-1", "Weather chat") in titles
        assert service._conversations["sess-1"].title == "Weather chat"


class TestCopilotServiceDestroyConversation:
    """Destroying a conversation removes it and calls session.destroy."""

    def test_destroy(self) -> None:
        fake_session = FakeSession("sess-1")
        mock_client = _make_mock_client(session=fake_session)
        service = CopilotService(client=mock_client)

        asyncio.run(service._start_async())
        asyncio.run(service._create_conversation_async("gpt-4"))
        assert "sess-1" in service._conversations

        asyncio.run(service._destroy_conversation_async("sess-1"))

        assert "sess-1" not in service._conversations
        assert "sess-1" not in service._sessions
        fake_session.destroy.assert_awaited_once()


class TestCopilotServiceAuthStatus:
    """check_auth_status emits auth-status signal."""

    def test_auth_status_signal(self) -> None:
        auth = FakeAuthStatus(True, "octocat")
        mock_client = _make_mock_client(auth=auth)
        service = CopilotService(client=mock_client)

        asyncio.run(service._start_async())

        statuses: list[tuple[bool, str]] = []
        service.connect(
            "auth-status",
            lambda _, authed, login: statuses.append((authed, login)),
        )

        asyncio.run(service._check_auth_async())

        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)

        assert (True, "octocat") in statuses
