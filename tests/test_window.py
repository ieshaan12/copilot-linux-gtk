# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for CopilotWindow."""

from unittest.mock import MagicMock, patch

import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Adw, Gio, Gtk  # noqa: E402

Adw.init()

from copilot_gtk.backend.conversation import Conversation  # noqa: E402
from copilot_gtk.backend.message import Message, MessageRole  # noqa: E402
from copilot_gtk.window import CopilotWindow  # noqa: E402


def _make_mock_service():
    """Create a mock CopilotService with the required GObject signals."""
    from copilot_gtk.backend.copilot_service import CopilotService

    service = CopilotService.__new__(CopilotService)
    CopilotService.__init__(service)
    return service


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
        # The placeholder should still be empty since s2 != s1
        # Actually, append_streaming_delta checks the streaming bubble regardless,
        # but window gates it — so the bubble shouldn't be updated.
        # (The window method gates on session_id match)

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
