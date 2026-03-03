# SPDX-License-Identifier: GPL-3.0-or-later
"""Shortcuts window for Copilot for GNOME."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk  # noqa: E402


def build_shortcuts_window() -> Gtk.ShortcutsWindow:
    """Build and return a ``Gtk.ShortcutsWindow`` listing all app shortcuts."""
    window = Gtk.ShortcutsWindow()

    # --- Main section ---
    section = Gtk.ShortcutsSection(section_name="shortcuts", title="Shortcuts")
    section.set_visible(True)

    # -- Conversations group --
    conv_group = Gtk.ShortcutsGroup(title="Conversations")
    conv_group.append(_new_shortcut("New Chat", "<Control>n"))
    conv_group.append(_new_shortcut("Close Conversation", "<Control>w"))
    conv_group.append(_new_shortcut("Search Conversations", "<Control>k"))
    section.append(conv_group)

    # -- Messaging group --
    msg_group = Gtk.ShortcutsGroup(title="Messaging")
    msg_group.append(_new_shortcut("Send Message", "<Control>Return"))
    msg_group.append(_new_shortcut("Stop Generation", "Escape"))
    section.append(msg_group)

    # -- General group --
    general_group = Gtk.ShortcutsGroup(title="General")
    general_group.append(_new_shortcut("Keyboard Shortcuts", "F1"))
    general_group.append(_new_shortcut("Quit", "<Control>q"))
    section.append(general_group)

    window.set_child(section)
    return window


def _new_shortcut(title: str, accelerator: str) -> Gtk.ShortcutsShortcut:
    """Create a single ``Gtk.ShortcutsShortcut`` entry."""
    shortcut = Gtk.ShortcutsShortcut(
        title=title,
        accelerator=accelerator,
    )
    return shortcut
