# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for the keyboard shortcuts window (Phase 7 — TASK-052)."""

import gi
import pytest

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk  # noqa: E402

Adw.init()

from copilot_gtk.widgets.shortcuts_window import (  # noqa: E402
    build_shortcuts_window,
    _new_shortcut,
)


class TestBuildShortcutsWindow:
    """Tests for build_shortcuts_window()."""

    def test_returns_shortcuts_window(self):
        win = build_shortcuts_window()
        assert isinstance(win, Gtk.ShortcutsWindow)

    def test_has_child_section(self):
        win = build_shortcuts_window()
        child = win.get_child()
        assert child is not None

    def test_section_is_shortcuts_section(self):
        win = build_shortcuts_window()
        child = win.get_child()
        assert isinstance(child, Gtk.ShortcutsSection)

    def test_section_is_visible(self):
        win = build_shortcuts_window()
        child = win.get_child()
        assert child.get_visible()


class TestNewShortcut:
    """Tests for _new_shortcut() helper."""

    def test_returns_shortcuts_shortcut(self):
        sc = _new_shortcut("Test", "<Control>t")
        assert isinstance(sc, Gtk.ShortcutsShortcut)

    def test_has_correct_title(self):
        sc = _new_shortcut("My Shortcut", "<Control>m")
        assert sc.get_property("title") == "My Shortcut"

    def test_has_correct_accelerator(self):
        sc = _new_shortcut("Test", "<Control>t")
        assert sc.get_property("accelerator") == "<Control>t"
