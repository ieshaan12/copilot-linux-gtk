# SPDX-License-Identifier: GPL-3.0-or-later
"""ChatView — Scrollable container displaying a list of message bubbles."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk  # noqa: E402

if TYPE_CHECKING:
    from ..backend import Conversation

from .message_bubble import MessageBubble  # noqa: E402

log = logging.getLogger(__name__)


class ChatView(Gtk.Box):
    """Displays the chat message history with auto-scroll.

    Contains a :class:`Gtk.ScrolledWindow` holding a vertical box
    of :class:`MessageBubble` widgets.
    """

    __gtype_name__ = "ChatView"

    def __init__(self) -> None:
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL,
            vexpand=True,
            hexpand=True,
        )

        self._scrolled = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            vexpand=True,
        )
        self._scrolled.add_css_class("chat-scroll")
        self.append(self._scrolled)

        # Clamp for max content width
        clamp = Adw.Clamp()
        clamp.set_maximum_size(800)
        clamp.set_tightening_threshold(600)

        self._message_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=0,
            margin_top=12,
            margin_bottom=12,
        )
        clamp.set_child(self._message_box)
        self._scrolled.set_child(clamp)

        self._streaming_bubble: MessageBubble | None = None
        self._auto_scroll = True

        # Track scroll position for auto-scroll
        adj = self._scrolled.get_vadjustment()
        adj.connect("value-changed", self._on_scroll_value_changed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_conversation(self, conv: Conversation) -> None:
        """Clear and reload from a conversation's message history."""
        self.clear()
        for msg in conv.messages:
            bubble = MessageBubble(
                role=msg.role.value,
                content=msg.content,
                is_streaming=msg.is_streaming,
            )
            self._message_box.append(bubble)
            if msg.is_streaming:
                self._streaming_bubble = bubble
        self._scroll_to_bottom()

    def add_user_message(self, text: str) -> None:
        """Add a user message bubble."""
        bubble = MessageBubble(role="user", content=text)
        self._message_box.append(bubble)
        self._scroll_to_bottom()

    def add_assistant_placeholder(self) -> None:
        """Add an empty assistant bubble for streaming."""
        bubble = MessageBubble(role="assistant", content="", is_streaming=True)
        self._message_box.append(bubble)
        self._streaming_bubble = bubble
        self._scroll_to_bottom()

    def append_streaming_delta(self, delta: str) -> None:
        """Append a streaming token to the current assistant bubble."""
        if self._streaming_bubble is not None:
            log.debug(
                "append_streaming_delta: delta_len=%d bubble_content_len=%d",
                len(delta),
                len(self._streaming_bubble.content),
            )
            self._streaming_bubble.append_content(delta)
            if self._auto_scroll:
                self._scroll_to_bottom()
        else:
            log.warning("append_streaming_delta called but no streaming bubble!")

    def finish_streaming(self) -> None:
        """Mark the streaming bubble as complete.

        If the bubble has no content (empty response), an informational
        message is shown so the user isn't left staring at a blank box.
        """
        if self._streaming_bubble is not None:
            log.info(
                "finish_streaming: bubble content_len=%d content=%.100r",
                len(self._streaming_bubble.content),
                self._streaming_bubble.content,
            )
            if not self._streaming_bubble.content.strip():
                self._streaming_bubble.show_error("No response received. Please try again.")
            else:
                self._streaming_bubble.finish_streaming()
            self._streaming_bubble = None
        else:
            log.debug("finish_streaming called but no streaming bubble (already finished)")

    def show_streaming_error(self, message: str) -> None:
        """Show an error message in the current streaming bubble.

        If there is no active streaming bubble, one is created first.
        """
        if self._streaming_bubble is None:
            self.add_assistant_placeholder()
        self._streaming_bubble.show_error(message)  # type: ignore[union-attr]
        self._streaming_bubble = None
        self._scroll_to_bottom()

    def clear(self) -> None:
        """Remove all message bubbles."""
        child = self._message_box.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            self._message_box.remove(child)
            child = next_child
        self._streaming_bubble = None

    # ------------------------------------------------------------------
    # Auto-scroll
    # ------------------------------------------------------------------

    def _scroll_to_bottom(self) -> None:
        """Scroll to the bottom of the chat on the next frame."""
        GLib.idle_add(self._do_scroll_to_bottom)

    def _do_scroll_to_bottom(self) -> bool:
        adj = self._scrolled.get_vadjustment()
        adj.set_value(adj.get_upper() - adj.get_page_size())
        return GLib.SOURCE_REMOVE

    def _on_scroll_value_changed(self, adj: Gtk.Adjustment) -> None:
        """Track whether the user has scrolled up (disable auto-scroll)."""
        at_bottom = adj.get_value() >= adj.get_upper() - adj.get_page_size() - 50
        self._auto_scroll = at_bottom
