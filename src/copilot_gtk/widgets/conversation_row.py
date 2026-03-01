# SPDX-License-Identifier: GPL-3.0-or-later
"""ConversationRow — A sidebar row representing a single conversation."""

from __future__ import annotations

from datetime import datetime, timezone

import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Adw, GObject, Gtk  # noqa: E402


class ConversationRow(Gtk.ListBoxRow):
    """A single conversation entry in the sidebar list.

    Displays the conversation title, model badge, and relative timestamp.

    Signals:
        delete-requested(session_id: str):
            Emitted when the user requests deletion of this conversation.
    """

    __gtype_name__ = "ConversationRow"

    __gsignals__ = {
        "delete-requested": (
            GObject.SignalFlags.RUN_LAST,
            None,
            (str,),  # session_id
        ),
        "rename-requested": (
            GObject.SignalFlags.RUN_LAST,
            None,
            (str,),  # session_id
        ),
    }

    def __init__(
        self,
        session_id: str,
        title: str = "New Chat",
        model: str = "",
        updated_at: datetime | None = None,
    ) -> None:
        super().__init__()
        self._session_id = session_id

        self.add_css_class("conversation-row")
        self.update_property(
            [Gtk.AccessibleProperty.LABEL], [f"Conversation: {title}"],
        )

        # Main box
        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=4,
            margin_top=8,
            margin_bottom=8,
            margin_start=12,
            margin_end=12,
        )
        self.set_child(box)

        # Top row: title + timestamp
        top_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=6,
        )
        box.append(top_box)

        self._title_label = Gtk.Label(
            label=title,
            xalign=0,
            ellipsize=3,  # PANGO_ELLIPSIZE_END
            hexpand=True,
        )
        self._title_label.add_css_class("heading")
        top_box.append(self._title_label)

        ts = updated_at or datetime.now(timezone.utc)
        self._time_label = Gtk.Label(
            label=self._format_time(ts),
            xalign=1,
        )
        self._time_label.add_css_class("dim-label")
        self._time_label.add_css_class("caption")
        top_box.append(self._time_label)

        # Bottom row: model badge
        bottom_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=6,
        )
        box.append(bottom_box)

        if model:
            model_label = Gtk.Label(label=model, xalign=0)
            model_label.add_css_class("dim-label")
            model_label.add_css_class("caption")
            bottom_box.append(model_label)

        # Right-click / long-press gesture for context menu
        self._setup_context_menu()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def title(self) -> str:
        return self._title_label.get_label()

    @title.setter
    def title(self, value: str) -> None:
        self._title_label.set_label(value)
        self.update_property(
            [Gtk.AccessibleProperty.LABEL], [f"Conversation: {value}"],
        )

    # ------------------------------------------------------------------
    # Context menu
    # ------------------------------------------------------------------

    def _setup_context_menu(self) -> None:
        """Add a right-click context menu with Rename and Delete options."""
        menu_model = __import__("gi").repository.Gio.Menu()
        menu_model.append("Rename", "row.rename")
        menu_model.append("Delete", "row.delete")

        popover = Gtk.PopoverMenu(menu_model=menu_model)
        popover.set_parent(self)
        popover.set_has_arrow(False)

        # Register actions
        action_group = __import__("gi").repository.Gio.SimpleActionGroup()

        delete_action = __import__("gi").repository.Gio.SimpleAction(name="delete")
        delete_action.connect("activate", self._on_delete)
        action_group.add_action(delete_action)

        rename_action = __import__("gi").repository.Gio.SimpleAction(name="rename")
        rename_action.connect("activate", self._on_rename)
        action_group.add_action(rename_action)

        self.insert_action_group("row", action_group)

        # Right-click gesture
        gesture = Gtk.GestureClick(button=3)  # secondary button
        gesture.connect("pressed", lambda g, n, x, y: popover.popup())
        self.add_controller(gesture)

        # Long-press gesture (touch)
        long_press = Gtk.GestureLongPress()
        long_press.connect("pressed", lambda g, x, y: popover.popup())
        self.add_controller(long_press)

        self._popover = popover

    def _on_delete(self, _action, _param) -> None:
        self.emit("delete-requested", self._session_id)

    def _on_rename(self, _action, _param) -> None:
        self.emit("rename-requested", self._session_id)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_time(dt: datetime) -> str:
        """Format a datetime as a short relative/absolute string."""
        now = datetime.now(timezone.utc)
        diff = now - dt
        if diff.days == 0:
            return dt.strftime("%H:%M")
        elif diff.days == 1:
            return "Yesterday"
        elif diff.days < 7:
            return dt.strftime("%A")
        else:
            return dt.strftime("%b %d")
