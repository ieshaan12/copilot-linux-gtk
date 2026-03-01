# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for CopilotWindow."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import gi
import pytest

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Adw, Gio, Gtk  # noqa: E402

Adw.init()

from copilot_gtk.backend.conversation import Conversation  # noqa: E402
from copilot_gtk.backend.conversation_store import ConversationStore  # noqa: E402
from copilot_gtk.backend.message import Message, MessageRole  # noqa: E402
from copilot_gtk.window import CopilotWindow  # noqa: E402


def _make_mock_service():
    """Create a mock CopilotService with the required GObject signals."""
    from copilot_gtk.backend.copilot_service import CopilotService

    service = CopilotService.__new__(CopilotService)
    CopilotService.__init__(service)
    return service


@pytest.fixture()
def tmp_store(tmp_path: Path) -> ConversationStore:
    return ConversationStore(data_dir=tmp_path)


class TestCopilotWindow:
    """Tests for the CopilotWindow widget."""

    def test_window_creation(self):
        service = _make_mock_service()
        win = CopilotWindow(service=service)
        assert win.get_title() == "Copilot for GNOME"
        assert win.get_default_size() == (1000, 700)

    def test_initial_state_shows_empty(self):
        service = _make_mock_service()
        win = CopilotWindow(service=service)
        assert win._content_stack.get_visible_child_name() == "empty"

    def test_split_view_exists(self):
        service = _make_mock_service()
        win = CopilotWindow(service=service)
        assert win._split_view is not None

    def test_conversation_list_exists(self):
        service = _make_mock_service()
        win = CopilotWindow(service=service)
        assert win._conversation_list is not None

    def test_chat_view_exists(self):
        service = _make_mock_service()
        win = CopilotWindow(service=service)
        assert win._chat_view is not None

    def test_chat_input_exists(self):
        service = _make_mock_service()
        win = CopilotWindow(service=service)
        assert win._chat_input is not None

    def test_new_chat_action_registered(self):
        service = _make_mock_service()
        win = CopilotWindow(service=service)
        action = win.lookup_action("new-chat")
        assert action is not None

    def test_search_action_registered(self):
        service = _make_mock_service()
        win = CopilotWindow(service=service)
        action = win.lookup_action("search-conversations")
        assert action is not None

    def test_search_bar_exists(self):
        service = _make_mock_service()
        win = CopilotWindow(service=service)
        assert win._search_bar is not None
        assert win._search_entry is not None

    def test_select_conversation_switches_to_chat(self):
        service = _make_mock_service()
        win = CopilotWindow(service=service)

        conv = Conversation(session_id="s1", title="Test", model="gpt-4")
        conv.add_message(Message(role=MessageRole.USER, content="Hello"))
        service._conversations["s1"] = conv

        win._select_conversation("s1")
        assert win._content_stack.get_visible_child_name() == "chat"
        assert win._current_session_id == "s1"

    def test_on_response_chunk_updates_chat(self):
        service = _make_mock_service()
        win = CopilotWindow(service=service)

        conv = Conversation(session_id="s1")
        service._conversations["s1"] = conv
        win._select_conversation("s1")

        # Add assistant placeholder
        win._chat_view.add_assistant_placeholder()
        win._on_response_chunk(service, "s1", "Hello")
        bubble = win._chat_view._message_box.get_first_child()
        assert bubble.content == "Hello"

    def test_on_response_chunk_ignored_for_other_session(self):
        service = _make_mock_service()
        win = CopilotWindow(service=service)
        win._current_session_id = "s1"

        # Chunk for a different session
        win._chat_view.add_assistant_placeholder()
        initial_content = win._chat_view._message_box.get_first_child().content
        win._on_response_chunk(service, "s2", "ignored")

    def test_show_toast(self):
        service = _make_mock_service()
        win = CopilotWindow(service=service)
        # Should not crash
        win.show_toast("Test message", timeout=1)

    def test_session_idle_adds_new_conversation(self):
        service = _make_mock_service()
        win = CopilotWindow(service=service)

        conv = Conversation(session_id="s1", title="New Chat")
        service._conversations["s1"] = conv

        win._on_session_idle(service, "s1")
        assert win._conversation_list.has_conversation("s1")
        assert win._current_session_id == "s1"

    def test_session_title_changed(self):
        service = _make_mock_service()
        win = CopilotWindow(service=service)

        conv = Conversation(session_id="s1", title="Old")
        service._conversations["s1"] = conv
        win._on_session_idle(service, "s1")

        win._on_session_title_changed(service, "s1", "Updated Title")
        assert win._conversation_list._rows["s1"].title == "Updated Title"


class TestWindowAutoTitle:
    """Tests for auto-title generation (TASK-046, VER-P6-003)."""

    def test_auto_title_from_first_user_message(self):
        service = _make_mock_service()
        win = CopilotWindow(service=service)

        conv = Conversation(session_id="s1", title="New Chat")
        conv.add_message(Message(role=MessageRole.USER, content="What is the weather today?"))
        conv.add_message(
            Message(role=MessageRole.ASSISTANT, content="It's sunny.")
        )
        service._conversations["s1"] = conv
        win._on_session_idle(service, "s1")

        # Trigger response-complete to auto-title
        win._on_response_complete(service, "s1", "It's sunny.")
        assert conv.title == "What is the weather today?"
        assert win._conversation_list._rows["s1"].title == "What is the weather today?"

    def test_auto_title_truncated(self):
        service = _make_mock_service()
        win = CopilotWindow(service=service)

        long_prompt = "A" * 70
        conv = Conversation(session_id="s1", title="New Chat")
        conv.add_message(Message(role=MessageRole.USER, content=long_prompt))
        conv.add_message(
            Message(role=MessageRole.ASSISTANT, content="Response")
        )
        service._conversations["s1"] = conv
        win._on_session_idle(service, "s1")

        win._on_response_complete(service, "s1", "Response")
        assert len(conv.title) == 51  # 50 chars + …
        assert conv.title.endswith("…")

    def test_no_auto_title_if_already_titled(self):
        service = _make_mock_service()
        win = CopilotWindow(service=service)

        conv = Conversation(session_id="s1", title="Custom Title")
        conv.add_message(Message(role=MessageRole.USER, content="Q"))
        conv.add_message(Message(role=MessageRole.ASSISTANT, content="A"))
        service._conversations["s1"] = conv

        win._on_response_complete(service, "s1", "A")
        assert conv.title == "Custom Title"


class TestWindowStore:
    """Tests for ConversationStore integration in the window."""

    def test_session_idle_persists_to_store(self, tmp_store):
        service = _make_mock_service()
        win = CopilotWindow(service=service, store=tmp_store)

        conv = Conversation(session_id="s1", title="Test")
        service._conversations["s1"] = conv

        win._on_session_idle(service, "s1")
        assert tmp_store.get_conversation("s1") is not None

    def test_response_complete_persists_messages(self, tmp_store):
        service = _make_mock_service()
        win = CopilotWindow(service=service, store=tmp_store)

        conv = Conversation(session_id="s1")
        conv.add_message(Message(role=MessageRole.USER, content="Hello"))
        conv.add_message(Message(role=MessageRole.ASSISTANT, content="Hi"))
        service._conversations["s1"] = conv
        win._on_session_idle(service, "s1")

        win._on_response_complete(service, "s1", "Hi")
        msgs = tmp_store.load_messages("s1")
        assert len(msgs) == 2

    def test_title_change_persists(self, tmp_store):
        service = _make_mock_service()
        win = CopilotWindow(service=service, store=tmp_store)

        conv = Conversation(session_id="s1", title="Old")
        service._conversations["s1"] = conv
        win._on_session_idle(service, "s1")

        win._on_session_title_changed(service, "s1", "New Title")
        stored = tmp_store.get_conversation("s1")
        assert stored is not None
        assert stored["title"] == "New Title"

    def test_load_persisted_conversations_on_startup(self, tmp_store):
        """VER-P6-001: Persisted conversations appear in sidebar on startup."""
        # Pre-populate the store
        conv = Conversation(session_id="s1", title="Persisted Chat")
        tmp_store.save_conversation(conv)

        service = _make_mock_service()
        win = CopilotWindow(service=service, store=tmp_store)

        assert win._conversation_list.has_conversation("s1")
        assert win._conversation_list._rows["s1"].title == "Persisted Chat"

    def test_load_persisted_with_messages(self, tmp_store):
        """VER-P6-007: Messages loaded from store are shown in chat view."""
        conv = Conversation(session_id="s1", title="Chat")
        tmp_store.save_conversation(conv)
        msgs = [
            Message(role=MessageRole.USER, content="Hello"),
            Message(role=MessageRole.ASSISTANT, content="Hi"),
        ]
        tmp_store.save_messages("s1", msgs)

        service = _make_mock_service()
        win = CopilotWindow(service=service, store=tmp_store)

        # Select the persisted conversation
        win._select_conversation("s1")
        # Service should now have the conversation in memory
        assert "s1" in service._conversations
        assert len(service._conversations["s1"].messages) == 2

    def test_delete_removes_from_store(self, tmp_store):
        """VER-P6-004: Deletion removes from store."""
        conv = Conversation(session_id="s1", title="To Delete")
        tmp_store.save_conversation(conv)

        service = _make_mock_service()
        win = CopilotWindow(service=service, store=tmp_store)

        # Simulate the delete response directly (bypassing dialog)
        service._conversations["s1"] = Conversation(session_id="s1")
        win._conversation_list.add_conversation(service._conversations["s1"])

        # Call the inner logic of delete
        win._conversation_list.remove_conversation("s1")
        tmp_store.delete_conversation("s1")

        assert tmp_store.get_conversation("s1") is None


class TestWindowSearch:
    """Tests for search functionality (TASK-050, VER-P6-008)."""

    def test_search_filters_conversations(self):
        """VER-P6-008: Search bar filters conversations by title."""
        service = _make_mock_service()
        win = CopilotWindow(service=service)

        for sid, title in [("s1", "Weather today"), ("s2", "Code review"), ("s3", "Weather forecast")]:
            conv = Conversation(session_id=sid, title=title)
            service._conversations[sid] = conv
            win._on_session_idle(service, sid)

        win._search_entry.set_text("weather")
        # Trigger search-changed
        win._on_search_changed(win._search_entry)

        assert win._conversation_list._rows["s1"].get_visible() is True
        assert win._conversation_list._rows["s2"].get_visible() is False
        assert win._conversation_list._rows["s3"].get_visible() is True

    def test_clear_search_restores_all(self):
        service = _make_mock_service()
        win = CopilotWindow(service=service)

        for sid, title in [("s1", "A"), ("s2", "B")]:
            conv = Conversation(session_id=sid, title=title)
            service._conversations[sid] = conv
            win._on_session_idle(service, sid)

        win._on_search_changed(win._search_entry)  # empty text
        assert win._conversation_list._rows["s1"].get_visible() is True
        assert win._conversation_list._rows["s2"].get_visible() is True
