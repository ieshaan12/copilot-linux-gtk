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

from .markdown_renderer import MarkdownTextView  # noqa: E402


class MessageBubble(Gtk.Box):
    """Renders a single message with role-appropriate styling.

    User messages are right-aligned with a coloured background and plain
    text.  Assistant messages are left-aligned and rendered as rich
    Markdown via :class:`MarkdownTextView`.
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

        # Align: user messages to the right, assistant to the left.
        # Content-adaptive sizing: frame.hexpand=False so the bubble
        # shrinks to its content's natural width.
        if role == "user":
            self.set_halign(Gtk.Align.END)
        else:
            self.set_halign(Gtk.Align.START)

        # Avatar
        avatar_name = "You" if role == "user" else "Copilot"
        avatar = Adw.Avatar(size=32, text=avatar_name, show_initials=True)

        # Content frame — hexpand=False lets halign control placement
        frame = Gtk.Frame()
        frame.add_css_class("message-bubble")
        frame.add_css_class(f"message-{role}")
        frame.set_hexpand(False)

        content_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=4,
            margin_top=10,
            margin_bottom=10,
            margin_start=14,
            margin_end=14,
        )
        frame.set_child(content_box)

        # --- Content widget selection ---
        self._markdown_view: MarkdownTextView | None = None
        self._text_label: Gtk.Label | None = None

        if role == "user":
            # User messages: plain label with max_width_chars so
            # short text stays compact and long text wraps.
            self._text_label = Gtk.Label(
                label=content,
                xalign=0,
                wrap=True,
                wrap_mode=Pango.WrapMode.WORD_CHAR,
                selectable=True,
                use_markup=False,
                max_width_chars=60,
            )
            self._text_label.set_natural_wrap_mode(
                Gtk.NaturalWrapMode.WORD
            )
            self._text_label.add_css_class("body")
            content_box.append(self._text_label)
        else:
            # Assistant / system messages: Markdown renderer.
            # MarkdownTextView overrides do_measure() to report a
            # content-aware natural width instead of single-word width.
            self._markdown_view = MarkdownTextView()
            if content:
                self._markdown_view.set_markdown(content)
            content_box.append(self._markdown_view)

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

        frame.add_css_class("message-frame")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def role(self) -> str:
        return self._role

    @property
    def content(self) -> str:
        if self._text_label is not None:
            return self._text_label.get_label()
        if self._markdown_view is not None:
            return self._markdown_view.get_markdown()
        return ""

    def append_content(self, delta: str) -> None:
        """Append streaming content to this bubble."""
        if self._text_label is not None:
            current = self._text_label.get_label()
            self._text_label.set_label(current + delta)
        elif self._markdown_view is not None:
            self._markdown_view.append_markdown_delta(delta)
        self._spinner.set_visible(False)

    def set_content(self, text: str) -> None:
        """Set the full content of this bubble."""
        if self._text_label is not None:
            self._text_label.set_label(text)
        elif self._markdown_view is not None:
            self._markdown_view.set_markdown(text)
        self._spinner.set_visible(False)

    def finish_streaming(self) -> None:
        """Mark this bubble as no longer streaming."""
        self._is_streaming = False
        self._spinner.set_visible(False)

    @property
    def is_streaming(self) -> bool:
        return self._is_streaming
