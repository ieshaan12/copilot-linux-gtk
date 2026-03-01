# SPDX-License-Identifier: GPL-3.0-or-later
"""Conversation data model for Copilot for GNOME."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from .message import Message


@dataclass
class Conversation:
    """Represents a single conversation (session) with Copilot.

    Attributes:
        session_id: The SDK session ID returned by create_session().
        title: A human-readable title for the conversation.
        model: The model ID used for this conversation.
        messages: Ordered list of messages in the conversation.
        created_at: When the conversation was first created.
        updated_at: When the conversation was last updated (message sent/received).
    """

    session_id: str
    title: str = "New Chat"
    model: str = ""
    messages: list[Message] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def add_message(self, message: Message) -> None:
        """Add a message and update the timestamp."""
        self.messages.append(message)
        self.updated_at = datetime.now(timezone.utc)

    def get_last_assistant_message(self) -> Message | None:
        """Get the most recent assistant message, if any."""
        for msg in reversed(self.messages):
            if msg.role.value == "assistant":
                return msg
        return None

    def get_streaming_message(self) -> Message | None:
        """Get the currently streaming message, if any."""
        for msg in reversed(self.messages):
            if msg.is_streaming:
                return msg
        return None

    def to_dict(self) -> dict:
        """Serialize to a dictionary for persistence (metadata only, no messages)."""
        return {
            "session_id": self.session_id,
            "title": self.title,
            "model": self.model,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> Conversation:
        """Deserialize from a dictionary (metadata only)."""
        return cls(
            session_id=data["session_id"],
            title=data.get("title", "New Chat"),
            model=data.get("model", ""),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )
