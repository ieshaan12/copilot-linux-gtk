# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for ConversationList widget."""

import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Adw  # noqa: E402

Adw.init()

from copilot_gtk.backend.conversation import Conversation  # noqa: E402
from copilot_gtk.widgets.conversation_list import ConversationList  # noqa: E402


def _make_conv(session_id: str, title: str = "Chat", model: str = "gpt-4"):
    return Conversation(session_id=session_id, title=title, model=model)


class TestConversationList:
    """Tests for the ConversationList widget."""

    def test_initially_empty(self):
        cl = ConversationList()
        assert not cl.has_conversation("any")

    def test_add_conversation(self):
        cl = ConversationList()
        conv = _make_conv("s1", "Chat 1")
        cl.add_conversation(conv)
        assert cl.has_conversation("s1")

    def test_remove_conversation(self):
        cl = ConversationList()
        cl.add_conversation(_make_conv("s1"))
        cl.remove_conversation("s1")
        assert not cl.has_conversation("s1")

    def test_remove_nonexistent_no_error(self):
        cl = ConversationList()
        cl.remove_conversation("nope")  # should not crash

    def test_update_title(self):
        cl = ConversationList()
        cl.add_conversation(_make_conv("s1", "Old"))
        cl.update_title("s1", "New")
        assert cl._rows["s1"].title == "New"

    def test_multiple_conversations(self):
        cl = ConversationList()
        cl.add_conversation(_make_conv("s1"))
        cl.add_conversation(_make_conv("s2"))
        cl.add_conversation(_make_conv("s3"))
        assert cl.has_conversation("s1")
        assert cl.has_conversation("s2")
        assert cl.has_conversation("s3")

    def test_conversation_selected_signal(self):
        cl = ConversationList()
        cl.add_conversation(_make_conv("s1"))
        received = []
        cl.connect("conversation-selected", lambda _w, sid: received.append(sid))
        cl.select_conversation("s1")
        assert received == ["s1"]

    def test_conversation_delete_requested_signal(self):
        cl = ConversationList()
        cl.add_conversation(_make_conv("s1"))
        received = []
        cl.connect(
            "conversation-delete-requested",
            lambda _w, sid: received.append(sid),
        )
        # Simulate delete from row
        cl._rows["s1"].emit("delete-requested", "s1")
        assert received == ["s1"]
