# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for ConversationStore — persistence layer."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from copilot_gtk.backend.conversation import Conversation
from copilot_gtk.backend.conversation_store import ConversationStore
from copilot_gtk.backend.message import Message, MessageRole


@pytest.fixture()
def tmp_store(tmp_path: Path) -> ConversationStore:
    """Create a ConversationStore using a temp directory."""
    return ConversationStore(data_dir=tmp_path)


def _make_conv(
    session_id: str = "sess-1",
    title: str = "Test Chat",
    model: str = "gpt-4",
) -> Conversation:
    return Conversation(
        session_id=session_id,
        title=title,
        model=model,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 2, tzinfo=UTC),
    )


def _make_messages() -> list[Message]:
    return [
        Message(role=MessageRole.USER, content="Hello"),
        Message(role=MessageRole.ASSISTANT, content="Hi there!"),
        Message(role=MessageRole.USER, content="How are you?"),
    ]


# ------------------------------------------------------------------
# Conversation persistence
# ------------------------------------------------------------------


class TestConversationStore:
    """Basic CRUD tests for ConversationStore."""

    def test_initially_empty(self, tmp_store: ConversationStore) -> None:
        assert tmp_store.list_conversations() == []

    def test_save_and_list(self, tmp_store: ConversationStore) -> None:
        conv = _make_conv()
        tmp_store.save_conversation(conv)
        result = tmp_store.list_conversations()
        assert len(result) == 1
        assert result[0]["session_id"] == "sess-1"
        assert result[0]["title"] == "Test Chat"

    def test_save_multiple_sorted_by_updated(self, tmp_store: ConversationStore) -> None:
        c1 = _make_conv("s1", "First")
        c1.updated_at = datetime(2026, 1, 1, tzinfo=UTC)
        c2 = _make_conv("s2", "Second")
        c2.updated_at = datetime(2026, 1, 3, tzinfo=UTC)

        tmp_store.save_conversation(c1)
        tmp_store.save_conversation(c2)

        result = tmp_store.list_conversations()
        assert result[0]["session_id"] == "s2"  # newest first
        assert result[1]["session_id"] == "s1"

    def test_get_conversation(self, tmp_store: ConversationStore) -> None:
        conv = _make_conv()
        tmp_store.save_conversation(conv)
        result = tmp_store.get_conversation("sess-1")
        assert result is not None
        assert result["title"] == "Test Chat"

    def test_get_nonexistent(self, tmp_store: ConversationStore) -> None:
        assert tmp_store.get_conversation("nope") is None

    def test_delete_conversation(self, tmp_store: ConversationStore) -> None:
        conv = _make_conv()
        tmp_store.save_conversation(conv)
        tmp_store.delete_conversation("sess-1")
        assert tmp_store.list_conversations() == []
        assert tmp_store.get_conversation("sess-1") is None

    def test_delete_nonexistent_no_error(self, tmp_store: ConversationStore) -> None:
        tmp_store.delete_conversation("nope")  # should not crash

    def test_update_title(self, tmp_store: ConversationStore) -> None:
        conv = _make_conv()
        tmp_store.save_conversation(conv)
        tmp_store.update_title("sess-1", "Renamed")
        result = tmp_store.get_conversation("sess-1")
        assert result is not None
        assert result["title"] == "Renamed"

    def test_update_title_updates_timestamp(self, tmp_store: ConversationStore) -> None:
        conv = _make_conv()
        tmp_store.save_conversation(conv)
        old_updated = tmp_store.get_conversation("sess-1")["updated_at"]
        tmp_store.update_title("sess-1", "New Title")
        new_updated = tmp_store.get_conversation("sess-1")["updated_at"]
        assert new_updated >= old_updated

    def test_update_timestamp(self, tmp_store: ConversationStore) -> None:
        conv = _make_conv()
        tmp_store.save_conversation(conv)
        old = tmp_store.get_conversation("sess-1")["updated_at"]
        tmp_store.update_timestamp("sess-1")
        new = tmp_store.get_conversation("sess-1")["updated_at"]
        assert new >= old

    def test_save_conversation_dict(self, tmp_store: ConversationStore) -> None:
        data = {
            "session_id": "s99",
            "title": "Dict Chat",
            "model": "gpt-3.5",
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-02T00:00:00+00:00",
        }
        tmp_store.save_conversation_dict(data)
        assert tmp_store.get_conversation("s99") is not None


# ------------------------------------------------------------------
# Persistence to disk
# ------------------------------------------------------------------


class TestConversationStoreDisk:
    """Tests that verify on-disk persistence."""

    def test_json_file_created(self, tmp_path: Path) -> None:
        store = ConversationStore(data_dir=tmp_path)
        store.save_conversation(_make_conv())
        json_file = tmp_path / "conversations.json"
        assert json_file.exists()

    def test_json_is_valid(self, tmp_path: Path) -> None:
        store = ConversationStore(data_dir=tmp_path)
        store.save_conversation(_make_conv("s1"))
        store.save_conversation(_make_conv("s2"))
        json_path = tmp_path / "conversations.json"
        data = json.loads(json_path.read_text())
        assert isinstance(data, list)
        assert len(data) == 2

    def test_reload_from_disk(self, tmp_path: Path) -> None:
        store1 = ConversationStore(data_dir=tmp_path)
        store1.save_conversation(_make_conv("s1", "First"))
        store1.save_conversation(_make_conv("s2", "Second"))

        # Create a new store from the same directory
        store2 = ConversationStore(data_dir=tmp_path)
        result = store2.list_conversations()
        assert len(result) == 2
        ids = {c["session_id"] for c in result}
        assert ids == {"s1", "s2"}

    def test_persist_across_restarts(self, tmp_path: Path) -> None:
        """VER-P6-001: Conversations persist across restarts."""
        store = ConversationStore(data_dir=tmp_path)
        for i in range(3):
            store.save_conversation(_make_conv(f"s{i}", f"Chat #{i}"))

        store2 = ConversationStore(data_dir=tmp_path)
        assert len(store2.list_conversations()) == 3

    def test_delete_removes_from_disk(self, tmp_path: Path) -> None:
        """VER-P6-004: Deleted conversation removed from JSON store."""
        store = ConversationStore(data_dir=tmp_path)
        store.save_conversation(_make_conv("s1"))
        store.delete_conversation("s1")

        store2 = ConversationStore(data_dir=tmp_path)
        assert store2.get_conversation("s1") is None

    def test_directories_created(self, tmp_path: Path) -> None:
        data_dir = tmp_path / "subdir" / "nested"
        _ = ConversationStore(data_dir=data_dir)
        assert data_dir.exists()
        assert (data_dir / "messages").exists()


# ------------------------------------------------------------------
# Corrupt file recovery (VER-P6-010)
# ------------------------------------------------------------------


class TestConversationStoreRecovery:
    """Tests for corrupt file handling."""

    def test_corrupt_json_starts_fresh(self, tmp_path: Path) -> None:
        """VER-P6-010: App starts with empty store if JSON is corrupt."""
        json_file = tmp_path / "conversations.json"
        json_file.write_text("{invalid json!!!}")

        store = ConversationStore(data_dir=tmp_path)
        assert store.list_conversations() == []

    def test_corrupt_file_backed_up(self, tmp_path: Path) -> None:
        json_file = tmp_path / "conversations.json"
        json_file.write_text("not valid json")

        ConversationStore(data_dir=tmp_path)
        bak = tmp_path / "conversations.json.bak"
        assert bak.exists()

    def test_empty_file_starts_fresh(self, tmp_path: Path) -> None:
        json_file = tmp_path / "conversations.json"
        json_file.write_text("")

        store = ConversationStore(data_dir=tmp_path)
        assert store.list_conversations() == []

    def test_non_list_non_dict_starts_fresh(self, tmp_path: Path) -> None:
        json_file = tmp_path / "conversations.json"
        json_file.write_text('"just a string"')

        store = ConversationStore(data_dir=tmp_path)
        assert store.list_conversations() == []

    def test_dict_format_accepted(self, tmp_path: Path) -> None:
        """Accept dict keyed by session_id as an alternative format."""
        data = {
            "s1": {
                "session_id": "s1",
                "title": "Chat",
                "model": "",
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-02T00:00:00+00:00",
            }
        }
        json_file = tmp_path / "conversations.json"
        json_file.write_text(json.dumps(data))

        store = ConversationStore(data_dir=tmp_path)
        assert len(store.list_conversations()) == 1


# ------------------------------------------------------------------
# Message persistence
# ------------------------------------------------------------------


class TestConversationStoreMessages:
    """Tests for message persistence."""

    def test_save_and_load_messages(self, tmp_store: ConversationStore) -> None:
        msgs = _make_messages()
        tmp_store.save_messages("sess-1", msgs)

        loaded = tmp_store.load_messages("sess-1")
        assert len(loaded) == 3
        assert loaded[0]["role"] == "user"
        assert loaded[0]["content"] == "Hello"
        assert loaded[1]["role"] == "assistant"
        assert loaded[1]["content"] == "Hi there!"

    def test_load_nonexistent_returns_empty(self, tmp_store: ConversationStore) -> None:
        assert tmp_store.load_messages("nonexistent") == []

    def test_messages_file_is_valid_json(self, tmp_path: Path) -> None:
        store = ConversationStore(data_dir=tmp_path)
        store.save_messages("sess-1", _make_messages())

        msg_file = tmp_path / "messages" / "sess-1.json"
        assert msg_file.exists()
        data = json.loads(msg_file.read_text())
        assert isinstance(data, list)
        assert len(data) == 3

    def test_delete_messages(self, tmp_path: Path) -> None:
        store = ConversationStore(data_dir=tmp_path)
        store.save_messages("sess-1", _make_messages())

        msg_file = tmp_path / "messages" / "sess-1.json"
        assert msg_file.exists()

        store.delete_messages("sess-1")
        assert not msg_file.exists()

    def test_delete_conversation_removes_messages(self, tmp_path: Path) -> None:
        store = ConversationStore(data_dir=tmp_path)
        store.save_conversation(_make_conv("sess-1"))
        store.save_messages("sess-1", _make_messages())

        store.delete_conversation("sess-1")
        msg_file = tmp_path / "messages" / "sess-1.json"
        assert not msg_file.exists()

    def test_corrupt_messages_returns_empty(self, tmp_path: Path) -> None:
        store = ConversationStore(data_dir=tmp_path)
        msg_file = tmp_path / "messages" / "sess-1.json"
        msg_file.parent.mkdir(parents=True, exist_ok=True)
        msg_file.write_text("{not a list}")

        result = store.load_messages("sess-1")
        assert result == []

    def test_overwrite_messages(self, tmp_path: Path) -> None:
        store = ConversationStore(data_dir=tmp_path)
        store.save_messages("sess-1", _make_messages())

        new_msgs = [Message(role=MessageRole.USER, content="Only one")]
        store.save_messages("sess-1", new_msgs)

        loaded = store.load_messages("sess-1")
        assert len(loaded) == 1
        assert loaded[0]["content"] == "Only one"
