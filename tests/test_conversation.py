# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for the Conversation data model."""

from datetime import UTC, datetime

from copilot_gtk.backend.conversation import Conversation
from copilot_gtk.backend.message import Message, MessageRole


class TestConversation:
    def test_create_default(self) -> None:
        conv = Conversation(session_id="sess-1")
        assert conv.session_id == "sess-1"
        assert conv.title == "New Chat"
        assert conv.model == ""
        assert conv.messages == []

    def test_add_message(self) -> None:
        conv = Conversation(session_id="sess-1")
        old_ts = conv.updated_at

        msg = Message(role=MessageRole.USER, content="Hi")
        conv.add_message(msg)

        assert len(conv.messages) == 1
        assert conv.messages[0] is msg
        assert conv.updated_at >= old_ts

    def test_get_last_assistant_message(self) -> None:
        conv = Conversation(session_id="sess-1")
        conv.add_message(Message(role=MessageRole.USER, content="Q"))
        conv.add_message(Message(role=MessageRole.ASSISTANT, content="A1"))
        conv.add_message(Message(role=MessageRole.USER, content="Q2"))
        conv.add_message(Message(role=MessageRole.ASSISTANT, content="A2"))

        last = conv.get_last_assistant_message()
        assert last is not None
        assert last.content == "A2"

    def test_get_last_assistant_message_none(self) -> None:
        conv = Conversation(session_id="sess-1")
        conv.add_message(Message(role=MessageRole.USER, content="Q"))
        assert conv.get_last_assistant_message() is None

    def test_get_streaming_message(self) -> None:
        conv = Conversation(session_id="sess-1")
        conv.add_message(Message(role=MessageRole.USER, content="Q"))
        streaming = Message(role=MessageRole.ASSISTANT, content="", is_streaming=True)
        conv.add_message(streaming)

        result = conv.get_streaming_message()
        assert result is streaming

    def test_get_streaming_message_none(self) -> None:
        conv = Conversation(session_id="sess-1")
        conv.add_message(Message(role=MessageRole.USER, content="Q"))
        conv.add_message(Message(role=MessageRole.ASSISTANT, content="A"))
        assert conv.get_streaming_message() is None

    def test_to_dict_roundtrip(self) -> None:
        original = Conversation(
            session_id="sess-42",
            title="Test Chat",
            model="gpt-4",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            updated_at=datetime(2026, 1, 2, tzinfo=UTC),
        )
        d = original.to_dict()
        restored = Conversation.from_dict(d)

        assert restored.session_id == original.session_id
        assert restored.title == original.title
        assert restored.model == original.model
        assert restored.created_at == original.created_at
        assert restored.updated_at == original.updated_at
        assert restored.messages == []  # Messages not persisted in metadata

    def test_to_dict_excludes_messages(self) -> None:
        conv = Conversation(session_id="sess-1")
        conv.add_message(Message(role=MessageRole.USER, content="hi"))
        d = conv.to_dict()
        assert "messages" not in d
