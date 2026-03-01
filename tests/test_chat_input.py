# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for ChatInput widget."""

import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Adw  # noqa: E402

Adw.init()

from copilot_gtk.widgets.chat_input import ChatInput  # noqa: E402


class TestChatInput:
    """Tests for the ChatInput widget."""

    def test_initial_state(self):
        inp = ChatInput()
        assert inp.get_text() == ""
        assert inp._is_loading is False

    def test_set_loading(self):
        inp = ChatInput()
        inp.set_loading(True)
        assert inp._is_loading is True
        assert inp._send_button.get_icon_name() == "media-playback-stop-symbolic"

    def test_set_loading_off(self):
        inp = ChatInput()
        inp.set_loading(True)
        inp.set_loading(False)
        assert inp._is_loading is False
        assert inp._send_button.get_icon_name() == "go-up-symbolic"

    def test_clear_text(self):
        inp = ChatInput()
        buf = inp._text_view.get_buffer()
        buf.set_text("hello")
        assert inp.get_text() == "hello"
        inp.clear_text()
        assert inp.get_text() == ""

    def test_message_submitted_signal(self):
        inp = ChatInput()
        received = []
        inp.connect("message-submitted", lambda _w, text: received.append(text))

        buf = inp._text_view.get_buffer()
        buf.set_text("test message")
        inp._submit()

        assert received == ["test message"]
        assert inp.get_text() == ""  # should be cleared after submit

    def test_empty_submit_ignored(self):
        inp = ChatInput()
        received = []
        inp.connect("message-submitted", lambda _w, text: received.append(text))
        inp._submit()
        assert received == []

    def test_whitespace_only_submit_ignored(self):
        inp = ChatInput()
        received = []
        inp.connect("message-submitted", lambda _w, text: received.append(text))
        buf = inp._text_view.get_buffer()
        buf.set_text("   \n  ")
        inp._submit()
        assert received == []

    def test_stop_requested_signal(self):
        inp = ChatInput()
        received = []
        inp.connect("stop-requested", lambda _w: received.append(True))

        inp.set_loading(True)
        inp._on_send_clicked(inp._send_button)

        assert received == [True]
