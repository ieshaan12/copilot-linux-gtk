# SPDX-License-Identifier: GPL-3.0-or-later
"""ConversationList — Sidebar widget managing all conversation rows."""

from __future__ import annotations

from typing import TYPE_CHECKING

import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import GObject, Gtk  # noqa: E402

if TYPE_CHECKING:
    from ..backend import Conversation

from .conversation_row import ConversationRow  # noqa: E402


class ConversationList(Gtk.Box):
    """A scrollable list of :class:`ConversationRow` widgets.

    Signals:
        conversation-selected(session_id: str):
            Emitted when the user selects a conversation.
        conversation-delete-requested(session_id: str):
            Emitted when the user requests deletion of a conversation.
    """

    __gtype_name__ = "ConversationList"

    __gsignals__ = {
        "conversation-selected": (
            GObject.SignalFlags.RUN_LAST,
            None,
            (str,),  # session_id
        ),
        "conversation-delete-requested": (
            GObject.SignalFlags.RUN_LAST,
            None,
            (str,),  # session_id
        ),
    }

    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.set_vexpand(True)

        # Scrolled window containing the list box
        scrolled = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            vexpand=True,
        )
        self.append(scrolled)

        self._list_box = Gtk.ListBox()
        self._list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._list_box.add_css_class("navigation-sidebar")
        self._list_box.connect("row-selected", self._on_row_selected)
        scrolled.set_child(self._list_box)

        # Track rows by session_id
        self._rows: dict[str, ConversationRow] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_conversation(self, conv: Conversation) -> None:
        """Add a conversation to the list."""
        row = ConversationRow(
            session_id=conv.session_id,
            title=conv.title,
            model=conv.model,
            updated_at=conv.updated_at,
        )
        row.connect("delete-requested", self._on_row_delete_requested)
        self._rows[conv.session_id] = row
        self._list_box.prepend(row)  # newest on top

    def remove_conversation(self, session_id: str) -> None:
        """Remove a conversation row by session_id."""
        row = self._rows.pop(session_id, None)
        if row is not None:
            self._list_box.remove(row)

    def has_conversation(self, session_id: str) -> bool:
        """Check if a conversation is already in the list."""
        return session_id in self._rows

    def update_title(self, session_id: str, title: str) -> None:
        """Update the title of a conversation row."""
        row = self._rows.get(session_id)
        if row is not None:
            row.title = title

    def select_conversation(self, session_id: str) -> None:
        """Programmatically select a conversation row."""
        row = self._rows.get(session_id)
        if row is not None:
            self._list_box.select_row(row)

    def get_selected_session_id(self) -> str | None:
        """Return the session_id of the currently selected conversation."""
        row = self._list_box.get_selected_row()
        if isinstance(row, ConversationRow):
            return row.session_id
        return None

    # ------------------------------------------------------------------
    # Internal signal handlers
    # ------------------------------------------------------------------

    def _on_row_selected(
        self, _list_box: Gtk.ListBox, row: Gtk.ListBoxRow | None
    ) -> None:
        if isinstance(row, ConversationRow):
            self.emit("conversation-selected", row.session_id)

    def _on_row_delete_requested(
        self, row: ConversationRow, session_id: str
    ) -> None:
        self.emit("conversation-delete-requested", session_id)
