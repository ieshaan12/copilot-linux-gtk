# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for MessageBubble widget."""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk  # noqa: E402

# Ensure Adw is initialised for tests
Adw.init()

from copilot_gtk.widgets.message_bubble import MessageBubble  # noqa: E402


class TestMessageBubble:
    """Tests for the MessageBubble widget."""

    def test_user_bubble_creation(self):
        bubble = MessageBubble(role="user", content="Hello!")
        assert bubble.role == "user"
        assert bubble.content == "Hello!"
        assert bubble.get_halign() == Gtk.Align.END

    def test_assistant_bubble_creation(self):
        bubble = MessageBubble(role="assistant", content="Hi there!")
        assert bubble.role == "assistant"
        assert bubble.content == "Hi there!"
        assert bubble.get_halign() == Gtk.Align.START

    def test_streaming_bubble(self):
        bubble = MessageBubble(role="assistant", content="", is_streaming=True)
        assert bubble.is_streaming is True
        assert bubble.content == ""

    def test_append_content(self):
        bubble = MessageBubble(role="assistant", content="", is_streaming=True)
        bubble.append_content("Hello")
        assert bubble.content == "Hello"
        bubble.append_content(" world")
        assert bubble.content == "Hello world"

    def test_set_content(self):
        bubble = MessageBubble(role="assistant", content="initial")
        bubble.set_content("replaced")
        assert bubble.content == "replaced"

    def test_finish_streaming(self):
        bubble = MessageBubble(role="assistant", content="done", is_streaming=True)
        assert bubble.is_streaming is True
        bubble.finish_streaming()
        assert bubble.is_streaming is False

    def test_system_bubble_alignment(self):
        bubble = MessageBubble(role="system", content="System message")
        assert bubble.get_halign() == Gtk.Align.START

    def test_show_error_replaces_content(self):
        bubble = MessageBubble(role="assistant", content="", is_streaming=True)
        bubble.show_error("Something went wrong")
        assert bubble.is_streaming is False
        assert "⚠" in bubble.content
        assert "Something went wrong" in bubble.content
        assert bubble.has_css_class("error-bubble")

    def test_show_error_on_bubble_with_content(self):
        bubble = MessageBubble(role="assistant", content="partial", is_streaming=True)
        bubble.append_content(" data")
        bubble.show_error("Connection lost")
        assert "Connection lost" in bubble.content
        assert bubble.is_streaming is False
