# SPDX-License-Identifier: GPL-3.0-or-later
"""Message data model for Copilot for GNOME."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class MessageRole(Enum):
    """The role of a message sender."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class Message:
    """A single message in a conversation.

    Attributes:
        role: The sender role (user, assistant, or system).
        content: The text content of the message.
        timestamp: When the message was created.
        message_id: The SDK message ID (from session events), if any.
        is_streaming: Whether the message is still being streamed.
        turn_id: The SDK turn ID grouping related events.
    """

    role: MessageRole
    content: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    message_id: str | None = None
    is_streaming: bool = False
    turn_id: str | None = None

    def append_content(self, delta: str) -> None:
        """Append a streaming delta to this message's content."""
        self.content += delta

    def finish_streaming(self) -> None:
        """Mark this message as no longer streaming."""
        self.is_streaming = False

    def to_dict(self) -> dict:
        """Serialize to a dictionary for persistence."""
        return {
            "role": self.role.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "message_id": self.message_id,
            "turn_id": self.turn_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Message:
        """Deserialize from a dictionary."""
        return cls(
            role=MessageRole(data["role"]),
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            message_id=data.get("message_id"),
            is_streaming=False,
            turn_id=data.get("turn_id"),
        )
