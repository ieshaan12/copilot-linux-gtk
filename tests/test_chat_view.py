# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for ChatView widget."""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw  # noqa: E402

Adw.init()

from copilot_gtk.backend.conversation import Conversation  # noqa: E402
from copilot_gtk.backend.message import Message, MessageRole  # noqa: E402
from copilot_gtk.widgets.chat_view import ChatView  # noqa: E402
from copilot_gtk.widgets.message_bubble import MessageBubble  # noqa: E402


def _count_children(box):
    """Count direct children of a Gtk.Box-like container."""
    count = 0
    child = box._message_box.get_first_child()
    while child is not None:
        count += 1
        child = child.get_next_sibling()
    return count


class TestChatView:
    """Tests for the ChatView widget."""

    def test_initial_state_empty(self):
        view = ChatView()
        assert _count_children(view) == 0

    def test_add_user_message(self):
        view = ChatView()
        view.add_user_message("Hello")
        assert _count_children(view) == 1
        child = view._message_box.get_first_child()
        assert isinstance(child, MessageBubble)
        assert child.role == "user"
        assert child.content == "Hello"

    def test_add_assistant_placeholder(self):
        view = ChatView()
        view.add_assistant_placeholder()
        assert _count_children(view) == 1
        child = view._message_box.get_first_child()
        assert isinstance(child, MessageBubble)
        assert child.role == "assistant"
        assert child.is_streaming is True

    def test_streaming_delta(self):
        view = ChatView()
        view.add_assistant_placeholder()
        view.append_streaming_delta("Hello")
        view.append_streaming_delta(" world")
        child = view._message_box.get_first_child()
        assert child.content == "Hello world"

    def test_finish_streaming(self):
        view = ChatView()
        view.add_assistant_placeholder()
        view.append_streaming_delta("Done")
        view.finish_streaming()
        child = view._message_box.get_first_child()
        assert child.is_streaming is False
        assert view._streaming_bubble is None

    def test_clear(self):
        view = ChatView()
        view.add_user_message("A")
        view.add_user_message("B")
        assert _count_children(view) == 2
        view.clear()
        assert _count_children(view) == 0

    def test_load_conversation(self):
        conv = Conversation(session_id="s1", title="Test", model="gpt-4")
        conv.add_message(Message(role=MessageRole.USER, content="Q"))
        conv.add_message(Message(role=MessageRole.ASSISTANT, content="A"))

        view = ChatView()
        view.load_conversation(conv)
        assert _count_children(view) == 2

    def test_load_conversation_replaces_old(self):
        view = ChatView()
        view.add_user_message("old")
        assert _count_children(view) == 1

        conv = Conversation(session_id="s2")
        conv.add_message(Message(role=MessageRole.USER, content="new"))

        view.load_conversation(conv)
        assert _count_children(view) == 1
        child = view._message_box.get_first_child()
        assert child.content == "new"
