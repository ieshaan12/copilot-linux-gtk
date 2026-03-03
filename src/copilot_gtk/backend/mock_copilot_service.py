# SPDX-License-Identifier: GPL-3.0-or-later
"""MockCopilotService — Drop-in replacement for CopilotService with canned responses.

Activated when the environment variable ``COPILOT_GTK_MOCK_BACKEND=1`` is set.
This provides the same GObject signal interface as :class:`CopilotService` but
returns deterministic, configurable responses without requiring the Copilot CLI.

Mock responses can be configured via:
    * ``COPILOT_GTK_MOCK_RESPONSE`` — single-string response text
    * ``COPILOT_GTK_MOCK_DELAY`` — simulated streaming delay in ms (default: 50)
    * ``COPILOT_GTK_MOCK_CHUNKS`` — number of streaming chunks (default: 5)
    * ``COPILOT_GTK_MOCK_ERROR`` — if set, emit an error instead of a response
    * A JSON fixture file path via ``COPILOT_GTK_MOCK_FIXTURE``
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from pathlib import Path

import gi

gi.require_version('GLib', '2.0')
from gi.repository import GLib, GObject  # noqa: E402

from .conversation import Conversation  # noqa: E402
from .message import Message, MessageRole  # noqa: E402

log = logging.getLogger(__name__)

# Default mock response when none is configured
_DEFAULT_RESPONSE = (
    "Hello! I'm a **mock** Copilot assistant.\n\n"
    "Here's a code example:\n\n"
    "```python\ndef greet(name: str) -> str:\n"
    '    return f"Hello, {name}!"\n```\n\n'
    "How can I help you today?"
)

# Default model list
_DEFAULT_MODELS = [
    {"id": "gpt-4o", "name": "GPT-4o"},
    {"id": "gpt-4o-mini", "name": "GPT-4o Mini"},
    {"id": "claude-sonnet-4", "name": "Claude Sonnet 4"},
]


class _MockModelInfo:
    """Minimal model info object matching the SDK's ModelInfo interface."""

    def __init__(self, model_id: str, name: str) -> None:
        self.id = model_id
        self.name = name

    def __repr__(self) -> str:
        return f"MockModelInfo(id={self.id!r}, name={self.name!r})"


class MockCopilotService(GObject.Object):
    """Mock CopilotService that emits the same GObject signals with canned data.

    Implements the identical signal interface as :class:`CopilotService` so the
    rest of the application can use it transparently.
    """

    __gsignals__ = {
        "ready": (GObject.SignalFlags.RUN_LAST, None, ()),
        "response-chunk": (
            GObject.SignalFlags.RUN_LAST,
            None,
            (str, str),
        ),
        "response-complete": (
            GObject.SignalFlags.RUN_LAST,
            None,
            (str, str),
        ),
        "session-idle": (
            GObject.SignalFlags.RUN_LAST,
            None,
            (str,),
        ),
        "session-title-changed": (
            GObject.SignalFlags.RUN_LAST,
            None,
            (str, str),
        ),
        "error": (
            GObject.SignalFlags.RUN_LAST,
            None,
            (str,),
        ),
        "models-loaded": (
            GObject.SignalFlags.RUN_LAST,
            None,
            (object,),
        ),
        "auth-status": (
            GObject.SignalFlags.RUN_LAST,
            None,
            (bool, str),
        ),
        "turn-start": (
            GObject.SignalFlags.RUN_LAST,
            None,
            (str,),
        ),
        "turn-end": (
            GObject.SignalFlags.RUN_LAST,
            None,
            (str,),
        ),
    }

    def __init__(self) -> None:
        super().__init__()
        self._started = False
        self._conversations: dict[str, Conversation] = {}
        self._models: list[_MockModelInfo] = []
        self._fixture_responses: list[dict] | None = None

        # Load fixture file if configured
        fixture_path = os.environ.get("COPILOT_GTK_MOCK_FIXTURE")
        if fixture_path and Path(fixture_path).exists():
            with open(fixture_path) as f:
                self._fixture_responses = json.load(f)
            log.info("Loaded mock fixture from %s", fixture_path)

    # ------------------------------------------------------------------
    # Properties (mirror CopilotService)
    # ------------------------------------------------------------------

    @property
    def conversations(self) -> dict[str, Conversation]:
        return dict(self._conversations)

    @property
    def models(self) -> list[_MockModelInfo]:
        return list(self._models)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self, client_options: dict | None = None) -> None:
        """Simulate SDK startup — emits ``ready`` after a short delay."""
        delay_ms = int(os.environ.get("COPILOT_GTK_MOCK_DELAY", "50"))

        def _emit_ready() -> bool:
            self._started = True
            log.info("MockCopilotService ready")
            self.emit("ready")
            return GLib.SOURCE_REMOVE

        GLib.timeout_add(delay_ms, _emit_ready)

    def stop(self) -> None:
        """Stop the mock service."""
        self._started = False
        self._conversations.clear()
        log.info("MockCopilotService stopped")

    # ------------------------------------------------------------------
    # Model listing
    # ------------------------------------------------------------------

    def list_models(self) -> None:
        """Emit a canned list of models."""
        model_defs = _DEFAULT_MODELS
        if self._fixture_responses:
            model_defs = self._fixture_responses.get("models", _DEFAULT_MODELS)  # type: ignore[union-attr]

        self._models = [_MockModelInfo(m["id"], m["name"]) for m in model_defs]

        def _emit() -> bool:
            self.emit("models-loaded", self._models)
            return GLib.SOURCE_REMOVE

        GLib.idle_add(_emit)

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def check_auth_status(self) -> None:
        """Always report as authenticated."""
        def _emit() -> bool:
            self.emit("auth-status", True, "mock-user")
            return GLib.SOURCE_REMOVE

        GLib.idle_add(_emit)

    # ------------------------------------------------------------------
    # Conversation / session management
    # ------------------------------------------------------------------

    def create_conversation(self, model: str = "") -> None:
        """Create a mock conversation and emit session-idle."""
        sid = f"mock-{uuid.uuid4().hex[:8]}"
        conv = Conversation(session_id=sid, model=model or "gpt-4o")
        self._conversations[sid] = conv

        log.info("MockCopilotService: created conversation %s", sid)

        def _emit() -> bool:
            self.emit("session-idle", sid)
            return GLib.SOURCE_REMOVE

        GLib.idle_add(_emit)

    def send_message(self, session_id: str, prompt: str) -> None:
        """Simulate sending a message with canned streaming response."""
        conv = self._conversations.get(session_id)
        if conv is None:
            self.emit("error", f"Unknown session: {session_id}")
            return

        # Add user message to conversation model
        user_msg = Message(role=MessageRole.USER, content=prompt)
        conv.add_message(user_msg)

        # Create assistant message placeholder
        assistant_msg = Message(
            role=MessageRole.ASSISTANT, content="", is_streaming=True
        )
        conv.add_message(assistant_msg)

        # Check for error simulation
        mock_error = os.environ.get("COPILOT_GTK_MOCK_ERROR")
        if mock_error:
            def _emit_error() -> bool:
                self.emit("error", mock_error)
                return GLib.SOURCE_REMOVE
            GLib.idle_add(_emit_error)
            return

        # Get response text
        response_text = self._get_response_text(prompt)
        n_chunks = int(os.environ.get("COPILOT_GTK_MOCK_CHUNKS", "5"))
        delay_ms = int(os.environ.get("COPILOT_GTK_MOCK_DELAY", "50"))

        # Split response into chunks
        chunks = self._split_into_chunks(response_text, n_chunks)

        # Emit turn-start
        GLib.idle_add(self.emit, "turn-start", session_id)

        # Schedule streaming chunks
        for i, chunk in enumerate(chunks):
            GLib.timeout_add(
                delay_ms * (i + 1),
                self._emit_chunk,
                session_id,
                chunk,
                assistant_msg,
            )

        # Schedule completion
        GLib.timeout_add(
            delay_ms * (len(chunks) + 1),
            self._emit_complete,
            session_id,
            response_text,
            assistant_msg,
            conv,
        )

    def abort_session(self, session_id: str) -> None:
        """Simulate aborting a session."""
        log.info("MockCopilotService: abort session %s", session_id)
        GLib.idle_add(self.emit, "session-idle", session_id)

    def destroy_conversation(self, session_id: str) -> None:
        """Remove a mock conversation."""
        self._conversations.pop(session_id, None)
        log.info("MockCopilotService: destroyed conversation %s", session_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_response_text(self, prompt: str) -> str:
        """Determine the response text based on configuration."""
        # Environment variable override
        env_response = os.environ.get("COPILOT_GTK_MOCK_RESPONSE")
        if env_response:
            return env_response

        # Fixture-based response matching
        if self._fixture_responses and isinstance(self._fixture_responses, list):
            for fixture in self._fixture_responses:
                trigger = fixture.get("trigger", "")
                if trigger and trigger.lower() in prompt.lower():
                    return fixture.get("response", _DEFAULT_RESPONSE)

        return _DEFAULT_RESPONSE

    @staticmethod
    def _split_into_chunks(text: str, n: int) -> list[str]:
        """Split text into roughly equal chunks for simulated streaming."""
        if n <= 1:
            return [text]
        chunk_size = max(1, len(text) // n)
        chunks = []
        for i in range(0, len(text), chunk_size):
            chunks.append(text[i:i + chunk_size])
        return chunks

    def _emit_chunk(
        self,
        session_id: str,
        chunk: str,
        assistant_msg: Message,
    ) -> bool:
        """Emit a single streaming chunk."""
        assistant_msg.append_content(chunk)
        self.emit("response-chunk", session_id, chunk)
        return GLib.SOURCE_REMOVE

    def _emit_complete(
        self,
        session_id: str,
        full_content: str,
        assistant_msg: Message,
        conv: Conversation,
    ) -> bool:
        """Emit response completion and session idle."""
        assistant_msg.content = full_content
        assistant_msg.finish_streaming()
        self.emit("response-complete", session_id, full_content)

        # Auto-generate title from first user message
        if conv.title == "New Chat":
            for msg in conv.messages:
                if msg.role == MessageRole.USER:
                    title = msg.content[:50].strip()
                    if len(msg.content) > 50:
                        title += "…"
                    conv.title = title
                    self.emit("session-title-changed", session_id, title)
                    break

        self.emit("turn-end", session_id)
        self.emit("session-idle", session_id)
        return GLib.SOURCE_REMOVE


def is_mock_backend_enabled() -> bool:
    """Check whether the mock backend is requested via environment variable."""
    return os.environ.get("COPILOT_GTK_MOCK_BACKEND", "").strip() in ("1", "true", "yes")


def create_service() -> GObject.Object:
    """Factory: return MockCopilotService or real CopilotService based on env.

    Usage in main.py::

        from copilot_gtk.backend.mock_copilot_service import create_service
        service = create_service()
    """
    if is_mock_backend_enabled():
        log.info("Using MockCopilotService (COPILOT_GTK_MOCK_BACKEND=1)")
        return MockCopilotService()
    from .copilot_service import CopilotService
    return CopilotService()
