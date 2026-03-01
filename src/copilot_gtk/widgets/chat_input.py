# SPDX-License-Identifier: GPL-3.0-or-later
"""ChatInput — Message input area with multi-line text entry and send button."""

from __future__ import annotations

import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Adw, Gdk, GObject, Gtk  # noqa: E402


class ChatInput(Gtk.Box):
    """A chat input widget with a multi-line text view and send/stop button.

    Signals:
        message-submitted(text: str):
            Emitted when the user submits a message (Send button or Ctrl+Enter).
        stop-requested():
            Emitted when the user clicks the Stop button during streaming.
    """

    __gtype_name__ = "ChatInput"

    __gsignals__ = {
        "message-submitted": (
            GObject.SignalFlags.RUN_LAST,
            None,
            (str,),  # message text
        ),
        "stop-requested": (
            GObject.SignalFlags.RUN_LAST,
            None,
            (),
        ),
    }

    def __init__(self) -> None:
        super().__init__(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            margin_top=8,
            margin_bottom=12,
            margin_start=12,
            margin_end=12,
        )
        self.add_css_class("chat-input")

        self._is_loading = False

        # Clamp the input to a nice max width
        # The parent (content area) already handles clamping,
        # so we just make this expand horizontally.
        self.set_hexpand(True)
        self.set_halign(Gtk.Align.FILL)

        # Scrolled text view for multi-line input
        scrolled = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            max_content_height=150,
            propagate_natural_height=True,
            hexpand=True,
        )
        scrolled.add_css_class("chat-input-scroll")

        self._text_view = Gtk.TextView()
        self._text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._text_view.set_accepts_tab(False)
        self._text_view.set_top_margin(8)
        self._text_view.set_bottom_margin(8)
        self._text_view.set_left_margin(12)
        self._text_view.set_right_margin(12)
        self._text_view.add_css_class("chat-text-input")
        self._text_view.update_property(
            [Gtk.AccessibleProperty.LABEL], ["Message input"],
        )

        # Placeholder text
        self._placeholder = Gtk.Label(
            label="Type a message… (Ctrl+Enter to send)",
            xalign=0,
            margin_start=12,
            margin_top=8,
        )
        self._placeholder.add_css_class("dim-label")

        # Overlay placeholder on text view
        overlay = Gtk.Overlay()
        overlay.set_child(self._text_view)
        overlay.add_overlay(self._placeholder)
        self._placeholder.set_can_target(False)
        scrolled.set_child(overlay)

        # Frame around the input
        frame = Gtk.Frame()
        frame.add_css_class("chat-input-frame")
        frame.set_child(scrolled)
        frame.set_hexpand(True)
        self.append(frame)

        # Send / Stop button
        self._send_button = Gtk.Button(icon_name="go-up-symbolic")
        self._send_button.set_tooltip_text("Send (Ctrl+Enter)")
        self._send_button.add_css_class("circular")
        self._send_button.add_css_class("suggested-action")
        self._send_button.set_valign(Gtk.Align.END)
        self._send_button.connect("clicked", self._on_send_clicked)
        self._send_button.update_property(
            [Gtk.AccessibleProperty.LABEL], ["Send message"],
        )
        self.append(self._send_button)

        # Key controller for Ctrl+Enter
        key_ctrl = Gtk.EventControllerKey()
        key_ctrl.connect("key-pressed", self._on_key_pressed)
        self._text_view.add_controller(key_ctrl)

        # Track text changes for placeholder visibility
        buf = self._text_view.get_buffer()
        buf.connect("changed", self._on_buffer_changed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_loading(self, loading: bool) -> None:
        """Toggle between send and stop modes."""
        self._is_loading = loading
        if loading:
            self._send_button.set_icon_name("media-playback-stop-symbolic")
            self._send_button.set_tooltip_text("Stop generation")
            self._send_button.remove_css_class("suggested-action")
            self._send_button.add_css_class("destructive-action")
            self._send_button.update_property(
                [Gtk.AccessibleProperty.LABEL], ["Stop generation"],
            )
            self._text_view.set_sensitive(False)
        else:
            self._send_button.set_icon_name("go-up-symbolic")
            self._send_button.set_tooltip_text("Send (Ctrl+Enter)")
            self._send_button.remove_css_class("destructive-action")
            self._send_button.add_css_class("suggested-action")
            self._send_button.update_property(
                [Gtk.AccessibleProperty.LABEL], ["Send message"],
            )
            self._text_view.set_sensitive(True)

    def grab_focus_input(self) -> None:
        """Focus the text input."""
        self._text_view.grab_focus()

    def get_text(self) -> str:
        """Get the current input text."""
        buf = self._text_view.get_buffer()
        start = buf.get_start_iter()
        end = buf.get_end_iter()
        return buf.get_text(start, end, False)

    def clear_text(self) -> None:
        """Clear the input text."""
        buf = self._text_view.get_buffer()
        buf.set_text("")

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------

    def _on_send_clicked(self, _button: Gtk.Button) -> None:
        if self._is_loading:
            self.emit("stop-requested")
            return
        self._submit()

    def _on_key_pressed(
        self,
        _controller: Gtk.EventControllerKey,
        keyval: int,
        keycode: int,
        state: Gdk.ModifierType,
    ) -> bool:
        # Ctrl+Enter to send
        if keyval == Gdk.KEY_Return and (state & Gdk.ModifierType.CONTROL_MASK):
            self._submit()
            return True  # consumed
        return False

    def _on_buffer_changed(self, buf: Gtk.TextBuffer) -> None:
        has_text = buf.get_char_count() > 0
        self._placeholder.set_visible(not has_text)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _submit(self) -> None:
        """Submit the current text if non-empty."""
        text = self.get_text().strip()
        if not text:
            return
        self.clear_text()
        self.emit("message-submitted", text)
