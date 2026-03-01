# SPDX-License-Identifier: GPL-3.0-or-later
"""CopilotService — GObject wrapper around the copilot-sdk CopilotClient.

This module provides ``CopilotService``, a ``GObject.Object`` subclass that
manages the full lifecycle of the Copilot SDK client and exposes GObject
signals that GTK widgets can connect to.

The service is the **only** layer that touches the copilot-sdk directly.
All UI code should interact exclusively with this service via its public
methods and signals.

Signals:
    ready():
        Emitted when the SDK client has started and is ready to create sessions.
    response-chunk(session_id: str, delta: str):
        Emitted for each streaming token from the assistant.
    response-complete(session_id: str, content: str):
        Emitted when the assistant finishes a complete message.
    session-idle(session_id: str):
        Emitted when a session returns to idle after processing.
    session-title-changed(session_id: str, title: str):
        Emitted when the SDK auto-generates or changes a session title.
    error(message: str):
        Emitted when any SDK or service-level error occurs.
    models-loaded(models: object):
        Emitted when the available model list has been fetched.
        The ``models`` parameter is a Python ``list[ModelInfo]``.
    auth-status(is_authenticated: bool, login: str):
        Emitted after checking authentication status.
    turn-start(session_id: str):
        Emitted when the assistant starts a new turn (begins processing).
    turn-end(session_id: str):
        Emitted when the assistant ends a turn.
"""

from __future__ import annotations

import logging
from typing import Any

import gi

gi.require_version('GLib', '2.0')
from gi.repository import GLib, GObject  # noqa: E402

from copilot import (  # noqa: E402
    CopilotClient,
    CopilotSession,
    ModelInfo,
    PermissionHandler,
    SessionConfig,
)
from copilot.generated.session_events import (  # noqa: E402
    SessionEvent,
    SessionEventType,
)

from .async_bridge import run_async  # noqa: E402
from .conversation import Conversation  # noqa: E402
from .message import Message, MessageRole  # noqa: E402

log = logging.getLogger(__name__)


class CopilotService(GObject.Object):
    """Manages the copilot-sdk client and exposes GObject signals for the UI."""

    __gsignals__ = {
        "ready": (GObject.SignalFlags.RUN_LAST, None, ()),
        "response-chunk": (
            GObject.SignalFlags.RUN_LAST,
            None,
            (str, str),  # session_id, delta_content
        ),
        "response-complete": (
            GObject.SignalFlags.RUN_LAST,
            None,
            (str, str),  # session_id, full_content
        ),
        "session-idle": (
            GObject.SignalFlags.RUN_LAST,
            None,
            (str,),  # session_id
        ),
        "session-title-changed": (
            GObject.SignalFlags.RUN_LAST,
            None,
            (str, str),  # session_id, title
        ),
        "error": (
            GObject.SignalFlags.RUN_LAST,
            None,
            (str,),  # error_message
        ),
        "models-loaded": (
            GObject.SignalFlags.RUN_LAST,
            None,
            (object,),  # list[ModelInfo]
        ),
        "auth-status": (
            GObject.SignalFlags.RUN_LAST,
            None,
            (bool, str),  # is_authenticated, login
        ),
        "turn-start": (
            GObject.SignalFlags.RUN_LAST,
            None,
            (str,),  # session_id
        ),
        "turn-end": (
            GObject.SignalFlags.RUN_LAST,
            None,
            (str,),  # session_id
        ),
    }

    def __init__(self, client: CopilotClient | None = None) -> None:
        """Initialise the service.

        Args:
            client: An optional pre-built ``CopilotClient``.  If *None*
                (the default), a new client is created with sensible defaults
                when :meth:`start` is called.
        """
        super().__init__()
        self._client: CopilotClient | None = client
        self._started: bool = False
        self._sessions: dict[str, CopilotSession] = {}
        self._conversations: dict[str, Conversation] = {}
        self._models: list[ModelInfo] = []

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def conversations(self) -> dict[str, Conversation]:
        """Return a read-only view of active conversations keyed by session_id."""
        return dict(self._conversations)

    @property
    def models(self) -> list[ModelInfo]:
        """Return the cached list of available models."""
        return list(self._models)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the Copilot SDK client (async, non-blocking).

        Emits ``ready`` on success, ``error`` on failure.
        """
        run_async(self._start_async(), error_callback=self._on_error)

    async def _start_async(self) -> None:
        client = self._client or CopilotClient()

        try:
            await client.start()
        except Exception:
            # Don't keep a half-started client around
            self._client = None
            self._started = False
            raise

        self._client = client
        self._started = True
        log.info("CopilotClient started")

        # Emit ready on the main thread
        GLib.idle_add(self.emit, "ready")

    def stop(self) -> None:
        """Stop the client and destroy all sessions (async, non-blocking)."""
        run_async(self._stop_async(), error_callback=self._on_error)

    async def _stop_async(self) -> None:
        if self._client is not None:
            await self._client.stop()
            self._client = None
        self._started = False
        self._sessions.clear()
        log.info("CopilotClient stopped")

    # ------------------------------------------------------------------
    # Model listing
    # ------------------------------------------------------------------

    def list_models(self) -> None:
        """Fetch available models (async).

        Emits ``models-loaded`` with the list on success.
        """
        run_async(self._list_models_async(), error_callback=self._on_error)

    async def _list_models_async(self) -> None:
        if not self._started or self._client is None:
            raise RuntimeError("Copilot is still connecting — please wait a moment")

        models = await self._client.list_models()
        self._models = models

        GLib.idle_add(self.emit, "models-loaded", models)

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def check_auth_status(self) -> None:
        """Check the current authentication status (async).

        Emits ``auth-status`` with the result.
        """
        run_async(self._check_auth_async(), error_callback=self._on_error)

    async def _check_auth_async(self) -> None:
        if not self._started or self._client is None:
            raise RuntimeError("Copilot is still connecting — please wait a moment")

        status = await self._client.get_auth_status()
        login = status.login or ""
        GLib.idle_add(
            self.emit, "auth-status", status.isAuthenticated, login
        )

    # ------------------------------------------------------------------
    # Conversation / session management
    # ------------------------------------------------------------------

    def create_conversation(self, model: str = "") -> None:
        """Create a new conversation session (async).

        Args:
            model: The model ID to use, or empty for the default.

        On success the conversation is stored internally and
        ``session-idle`` is emitted once the session is ready.
        """
        run_async(
            self._create_conversation_async(model),
            error_callback=self._on_error,
        )

    async def _create_conversation_async(self, model: str) -> None:
        if not self._started or self._client is None:
            raise RuntimeError("Copilot is still connecting — please wait a moment")

        config: SessionConfig = {
            "on_permission_request": PermissionHandler.approve_all,
            "streaming": True,
        }
        if model:
            config["model"] = model

        session = await self._client.create_session(config)
        sid = session.session_id

        # Wire up event handler
        session.on(lambda event: self._on_session_event(sid, event))

        self._sessions[sid] = session

        conv = Conversation(session_id=sid, model=model)
        self._conversations[sid] = conv

        log.info("Created conversation %s (model=%s)", sid, model)

        # Notify UI that the session exists and is idle
        GLib.idle_add(self.emit, "session-idle", sid)

    def send_message(self, session_id: str, prompt: str) -> None:
        """Send a user message to an existing conversation (async).

        Args:
            session_id: The session to send to.
            prompt: The user's message text.

        Emits ``response-chunk`` and ``response-complete``/``session-idle``
        as the assistant responds.
        """
        run_async(
            self._send_message_async(session_id, prompt),
            error_callback=self._on_error,
        )

    async def _send_message_async(self, session_id: str, prompt: str) -> None:
        session = self._sessions.get(session_id)
        if session is None:
            raise RuntimeError(f"Unknown session: {session_id}")

        conv = self._conversations.get(session_id)
        if conv is not None:
            user_msg = Message(role=MessageRole.USER, content=prompt)
            conv.add_message(user_msg)

            # Pre-create a streaming assistant message placeholder
            assistant_msg = Message(
                role=MessageRole.ASSISTANT, content="", is_streaming=True
            )
            conv.add_message(assistant_msg)

        await session.send({"prompt": prompt})

    def abort_session(self, session_id: str) -> None:
        """Abort the currently processing message in a session."""
        session = self._sessions.get(session_id)
        if session is not None:
            run_async(session.abort(), error_callback=self._on_error)

    def destroy_conversation(self, session_id: str) -> None:
        """Destroy a conversation and its SDK session (async)."""
        run_async(
            self._destroy_conversation_async(session_id),
            error_callback=self._on_error,
        )

    async def _destroy_conversation_async(self, session_id: str) -> None:
        session = self._sessions.pop(session_id, None)
        self._conversations.pop(session_id, None)

        if session is not None:
            await session.destroy()
            log.info("Destroyed conversation %s", session_id)

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------

    def _on_session_event(self, session_id: str, event: SessionEvent) -> None:
        """Handle a raw SDK session event and re-emit as GObject signals.

        This is called on the asyncio/GLib thread — signal emission is
        safe because gbulb uses the GLib main loop.
        """
        etype = event.type
        data = event.data

        if etype in (
            SessionEventType.ASSISTANT_MESSAGE_DELTA,
            SessionEventType.ASSISTANT_STREAMING_DELTA,
        ):
            delta = getattr(data, "delta_content", None) or ""
            if delta:
                # Append to conversation model
                conv = self._conversations.get(session_id)
                if conv is not None:
                    streaming_msg = conv.get_streaming_message()
                    if streaming_msg is not None:
                        streaming_msg.append_content(delta)
                GLib.idle_add(self.emit, "response-chunk", session_id, delta)

        elif etype == SessionEventType.ASSISTANT_MESSAGE:
            content = getattr(data, "content", None) or ""
            # Finalise the streaming message
            conv = self._conversations.get(session_id)
            if conv is not None:
                streaming_msg = conv.get_streaming_message()
                if streaming_msg is not None:
                    streaming_msg.content = content
                    streaming_msg.finish_streaming()
            GLib.idle_add(
                self.emit, "response-complete", session_id, content
            )

        elif etype == SessionEventType.SESSION_IDLE:
            GLib.idle_add(self.emit, "session-idle", session_id)

        elif etype == SessionEventType.SESSION_TITLE_CHANGED:
            title = getattr(data, "title", None) or ""
            conv = self._conversations.get(session_id)
            if conv is not None:
                conv.title = title
            GLib.idle_add(
                self.emit, "session-title-changed", session_id, title
            )

        elif etype == SessionEventType.SESSION_ERROR:
            msg = getattr(data, "message", None) or "Unknown session error"
            log.error("Session %s error: %s", session_id, msg)
            GLib.idle_add(self.emit, "error", msg)

        elif etype == SessionEventType.ASSISTANT_TURN_START:
            GLib.idle_add(self.emit, "turn-start", session_id)

        elif etype == SessionEventType.ASSISTANT_TURN_END:
            GLib.idle_add(self.emit, "turn-end", session_id)

        else:
            log.debug("Unhandled event %s for session %s", etype, session_id)

    # ------------------------------------------------------------------
    # Error helpers
    # ------------------------------------------------------------------

    def _on_error(self, exc: Exception) -> bool:
        """Emit an error signal from an exception. Returns False for GLib.idle_add."""
        msg = str(exc)
        log.error("CopilotService error: %s", msg)
        self.emit("error", msg)
        return GLib.SOURCE_REMOVE
