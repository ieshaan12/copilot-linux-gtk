# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for the Message data model."""

from datetime import datetime, timezone

from copilot_gtk.backend.message import Message, MessageRole


class TestMessage:
    def test_create_user_message(self) -> None:
        msg = Message(role=MessageRole.USER, content="Hello")
        assert msg.role == MessageRole.USER
        assert msg.content == "Hello"
        assert msg.is_streaming is False
        assert msg.message_id is None

    def test_create_streaming_assistant_message(self) -> None:
        msg = Message(
            role=MessageRole.ASSISTANT, content="", is_streaming=True
        )
        assert msg.is_streaming is True
        assert msg.content == ""

    def test_append_content(self) -> None:
        msg = Message(
            role=MessageRole.ASSISTANT, content="Hello", is_streaming=True
        )
        msg.append_content(" world")
        assert msg.content == "Hello world"
        assert msg.is_streaming is True

    def test_finish_streaming(self) -> None:
        msg = Message(
            role=MessageRole.ASSISTANT, content="Done", is_streaming=True
        )
        msg.finish_streaming()
        assert msg.is_streaming is False

    def test_to_dict_roundtrip(self) -> None:
        original = Message(
            role=MessageRole.ASSISTANT,
            content="test content",
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
            message_id="msg-123",
            turn_id="turn-456",
        )
        d = original.to_dict()
        restored = Message.from_dict(d)

        assert restored.role == original.role
        assert restored.content == original.content
        assert restored.timestamp == original.timestamp
        assert restored.message_id == original.message_id
        assert restored.turn_id == original.turn_id
        assert restored.is_streaming is False  # Never persisted as streaming

    def test_to_dict_excludes_is_streaming(self) -> None:
        msg = Message(
            role=MessageRole.USER, content="hi", is_streaming=True
        )
        d = msg.to_dict()
        assert "is_streaming" not in d

    def test_message_role_values(self) -> None:
        assert MessageRole.USER.value == "user"
        assert MessageRole.ASSISTANT.value == "assistant"
        assert MessageRole.SYSTEM.value == "system"
