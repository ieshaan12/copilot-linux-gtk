# SPDX-License-Identifier: GPL-3.0-or-later
"""MessageBubble — A widget rendering a single chat message."""

from __future__ import annotations

from typing import TYPE_CHECKING

import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Adw, Gtk, Pango  # noqa: E402

if TYPE_CHECKING:
    from ..backend import MessageRole


class MessageBubble(Gtk.Box):
    """Renders a single message with role-appropriate styling.

    User messages are right-aligned with a coloured background.
    Assistant messages are left-aligned with a different background.
    """

    __gtype_name__ = "MessageBubble"

    def __init__(
        self,
        role: str,  # "user" | "assistant" | "system"
        content: str = "",
        is_streaming: bool = False,
    ) -> None:
        super().__init__(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
            margin_top=6,
            margin_bottom=6,
            margin_start=12,
            margin_end=12,
        )

        self._role = role
        self._is_streaming = is_streaming

        # Align: user messages to the right, assistant to the left
        if role == "user":
            self.set_halign(Gtk.Align.END)
        else:
            self.set_halign(Gtk.Align.START)

        # Avatar
        avatar_char = "Y" if role == "user" else "C"
        avatar_name = "You" if role == "user" else "Copilot"
        avatar = Adw.Avatar(size=32, text=avatar_name, show_initials=True)

        # Content frame
        frame = Gtk.Frame()
        frame.add_css_class("message-bubble")
        frame.add_css_class(f"message-{role}")

        content_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=4,
            margin_top=10,
            margin_bottom=10,
            margin_start=14,
            margin_end=14,
        )
        frame.set_child(content_box)

        # Text label (supports wrapping)
        self._text_label = Gtk.Label(
            label=content,
            xalign=0,
            wrap=True,
            wrap_mode=Pango.WrapMode.WORD_CHAR,
            selectable=True,
            use_markup=False,
        )
        self._text_label.add_css_class("body")
        content_box.append(self._text_label)

        # Spinner for streaming
        self._spinner = Adw.Spinner()
        self._spinner.set_visible(is_streaming and not content)
        content_box.append(self._spinner)

        # Layout order: assistant = avatar+content, user = content+avatar
        if role == "user":
            self.append(frame)
            self.append(avatar)
        else:
            self.append(avatar)
            self.append(frame)

        # Constrain max width
        frame.set_size_request(-1, -1)
        self.set_hexpand(False)
        # We'll use CSS max-width via a size class
        frame.add_css_class("message-frame")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def role(self) -> str:
        return self._role

    @property
    def content(self) -> str:
        return self._text_label.get_label()

    def append_content(self, delta: str) -> None:
        """Append streaming content to this bubble."""
        current = self._text_label.get_label()
        self._text_label.set_label(current + delta)
        self._spinner.set_visible(False)

    def set_content(self, text: str) -> None:
        """Set the full content of this bubble."""
        self._text_label.set_label(text)
        self._spinner.set_visible(False)

    def finish_streaming(self) -> None:
        """Mark this bubble as no longer streaming."""
        self._is_streaming = False
        self._spinner.set_visible(False)

    @property
    def is_streaming(self) -> bool:
        return self._is_streaming
