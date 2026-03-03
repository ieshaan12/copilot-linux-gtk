# SPDX-License-Identifier: GPL-3.0-or-later
"""ConversationStore — Persists conversation metadata to disk.

Stores conversation metadata (id, title, model, timestamps) as JSON
in ``~/.local/share/copilot-gtk/conversations.json``.  Messages are
**not** stored here — they are retrieved from the SDK on demand via
``session.get_messages()``.

The store also persists messages per-conversation in separate files
under ``~/.local/share/copilot-gtk/messages/<session_id>.json`` so
that message history can be restored when the SDK session is no longer
available (e.g., after app restart before re-connecting).
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .conversation import Conversation
    from .message import Message

log = logging.getLogger(__name__)

# XDG data directory for our app
_DEFAULT_DATA_DIR = Path.home() / ".local" / "share" / "copilot-gtk"
_CONVERSATIONS_FILE = "conversations.json"
_MESSAGES_DIR = "messages"


class ConversationStore:
    """Manages persistence of conversation metadata and messages to disk.

    Args:
        data_dir: Override the default data directory (useful for testing).
    """

    def __init__(self, data_dir: Path | None = None) -> None:
        self._data_dir = data_dir or _DEFAULT_DATA_DIR
        self._conversations_file = self._data_dir / _CONVERSATIONS_FILE
        self._messages_dir = self._data_dir / _MESSAGES_DIR
        self._conversations: dict[str, dict] = {}

        # Ensure directories exist
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._messages_dir.mkdir(parents=True, exist_ok=True)

        # Load existing data
        self._load()

    # ------------------------------------------------------------------
    # Public API — Conversations
    # ------------------------------------------------------------------

    def list_conversations(self) -> list[dict]:
        """Return all stored conversation metadata, sorted newest-first.

        Returns:
            A list of dicts with keys: session_id, title, model,
            created_at, updated_at.
        """
        convs = list(self._conversations.values())
        convs.sort(
            key=lambda c: c.get("updated_at", ""),
            reverse=True,
        )
        return convs

    def save_conversation(self, conversation: Conversation) -> None:
        """Save or update a conversation's metadata.

        Args:
            conversation: The ``Conversation`` dataclass instance to persist.
        """
        self._conversations[conversation.session_id] = conversation.to_dict()
        self._flush()

    def save_conversation_dict(self, data: dict) -> None:
        """Save or update a conversation from a raw dict.

        Useful when only metadata changes (e.g., title rename).
        """
        sid = data.get("session_id", "")
        if sid:
            self._conversations[sid] = data
            self._flush()

    def delete_conversation(self, session_id: str) -> None:
        """Remove a conversation and its messages from the store.

        Args:
            session_id: The session ID to remove.
        """
        self._conversations.pop(session_id, None)
        self._flush()

        # Remove message file if it exists
        msg_file = self._messages_dir / f"{session_id}.json"
        if msg_file.exists():
            try:
                msg_file.unlink()
            except OSError as exc:
                log.warning("Failed to delete message file %s: %s", msg_file, exc)

    def get_conversation(self, session_id: str) -> dict | None:
        """Get metadata for a specific conversation.

        Returns:
            The conversation dict, or None if not found.
        """
        return self._conversations.get(session_id)

    def update_title(self, session_id: str, title: str) -> None:
        """Update just the title of a stored conversation.

        Args:
            session_id: The session to update.
            title: The new title.
        """
        conv = self._conversations.get(session_id)
        if conv is not None:
            conv["title"] = title
            conv["updated_at"] = datetime.now(UTC).isoformat()
            self._flush()

    def update_timestamp(self, session_id: str) -> None:
        """Touch the updated_at timestamp for a conversation.

        Args:
            session_id: The session to update.
        """
        conv = self._conversations.get(session_id)
        if conv is not None:
            conv["updated_at"] = datetime.now(UTC).isoformat()
            self._flush()

    # ------------------------------------------------------------------
    # Public API — Messages
    # ------------------------------------------------------------------

    def save_messages(self, session_id: str, messages: list[Message]) -> None:
        """Persist all messages for a conversation to disk.

        Args:
            session_id: The conversation's session ID.
            messages: List of ``Message`` dataclass instances.
        """
        msg_file = self._messages_dir / f"{session_id}.json"
        data = [m.to_dict() for m in messages]
        try:
            msg_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError as exc:
            log.error("Failed to write messages for %s: %s", session_id, exc)

    def load_messages(self, session_id: str) -> list[dict]:
        """Load persisted messages for a conversation.

        Args:
            session_id: The conversation's session ID.

        Returns:
            A list of message dicts, or empty list if none found.
        """
        msg_file = self._messages_dir / f"{session_id}.json"
        if not msg_file.exists():
            return []
        try:
            raw = msg_file.read_text(encoding="utf-8")
            data = json.loads(raw)
            if isinstance(data, list):
                return data
            log.warning("Messages file %s is not a list, ignoring", msg_file)
            return []
        except (json.JSONDecodeError, OSError) as exc:
            log.warning(
                "Failed to load messages for %s: %s — returning empty",
                session_id,
                exc,
            )
            return []

    def delete_messages(self, session_id: str) -> None:
        """Delete persisted messages for a conversation.

        Args:
            session_id: The conversation's session ID.
        """
        msg_file = self._messages_dir / f"{session_id}.json"
        if msg_file.exists():
            try:
                msg_file.unlink()
            except OSError as exc:
                log.warning("Failed to delete messages %s: %s", msg_file, exc)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Load conversations from the JSON file on disk."""
        if not self._conversations_file.exists():
            self._conversations = {}
            return

        try:
            raw = self._conversations_file.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (json.JSONDecodeError, OSError) as exc:
            log.warning(
                "Corrupt conversations file %s: %s — starting fresh",
                self._conversations_file,
                exc,
            )
            self._conversations = {}
            # Rename the corrupt file so it's not lost
            try:
                corrupt_path = self._conversations_file.with_suffix(".json.bak")
                self._conversations_file.rename(corrupt_path)
                log.info("Backed up corrupt file to %s", corrupt_path)
            except OSError:
                pass
            return

        # Expected format: list of conversation dicts
        if isinstance(data, list):
            self._conversations = {}
            for entry in data:
                sid = entry.get("session_id", "")
                if sid:
                    self._conversations[sid] = entry
        elif isinstance(data, dict):
            # Also accept a dict keyed by session_id (forward compat)
            self._conversations = data
        else:
            log.warning("Unexpected data type in %s, starting fresh", self._conversations_file)
            self._conversations = {}

    def _flush(self) -> None:
        """Write the current conversations to disk as a JSON list."""
        data = list(self._conversations.values())
        try:
            self._conversations_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError as exc:
            log.error("Failed to write conversations file: %s", exc)
