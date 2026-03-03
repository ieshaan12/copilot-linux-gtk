# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for ConversationRow widget."""

from datetime import UTC, datetime, timedelta

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk  # noqa: E402

Adw.init()

from copilot_gtk.widgets.conversation_row import ConversationRow  # noqa: E402


class TestConversationRow:
    """Tests for the ConversationRow widget."""

    def test_creation(self):
        row = ConversationRow(session_id="s1", title="My Chat", model="gpt-4")
        assert row.session_id == "s1"
        assert row.title == "My Chat"

    def test_title_update(self):
        row = ConversationRow(session_id="s1", title="Old")
        row.title = "New Title"
        assert row.title == "New Title"

    def test_default_title(self):
        row = ConversationRow(session_id="s1")
        assert row.title == "New Chat"

    def test_delete_signal(self):
        row = ConversationRow(session_id="s1")
        received = []
        row.connect("delete-requested", lambda _r, sid: received.append(sid))
        row._on_delete(None, None)
        assert received == ["s1"]

    def test_rename_signal(self):
        row = ConversationRow(session_id="s1")
        received = []
        row.connect("rename-requested", lambda _r, sid: received.append(sid))
        row._on_rename(None, None)
        assert received == ["s1"]

    def test_today_timestamp_format(self):
        now = datetime.now(UTC)
        row = ConversationRow(session_id="s1", updated_at=now)
        # Should show HH:MM
        assert ":" in row._time_label.get_label()

    def test_yesterday_timestamp_format(self):
        yesterday = datetime.now(UTC) - timedelta(days=1)
        row = ConversationRow(session_id="s1", updated_at=yesterday)
        assert row._time_label.get_label() == "Yesterday"

    def test_is_list_box_row(self):
        row = ConversationRow(session_id="s1")
        assert isinstance(row, Gtk.ListBoxRow)
