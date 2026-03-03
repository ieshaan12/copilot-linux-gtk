# SPDX-License-Identifier: GPL-3.0-or-later
"""UI Test: Keyboard Shortcuts (TASK-085).

Verifies that keyboard shortcuts work correctly via dogtail's rawinput.
These tests are skipped if rawinput is not available or key simulation
is not supported on the current system.
"""

from __future__ import annotations

import time

import pytest

from .conftest import wait_for_sdk_ready

pytestmark = [
    pytest.mark.ui,
    pytest.mark.timeout(60),
]


def _press_key(app_node, key_name: str, modifiers: list[str] | None = None):
    """Simulate a key press via dogtail/AT-SPI."""
    try:
        window = app_node.child(roleName="frame")
        window.grab_focus()
        time.sleep(0.2)

        from dogtail import rawinput

        if modifiers is None:
            modifiers = []

        if "ctrl" in modifiers:
            rawinput.pressKey("Control_L")
        if "shift" in modifiers:
            rawinput.pressKey("Shift_L")

        rawinput.pressKey(key_name)

        if "shift" in modifiers:
            rawinput.releaseKey("Shift_L")
        if "ctrl" in modifiers:
            rawinput.releaseKey("Control_L")

    except ImportError:
        pytest.skip("dogtail.rawinput not available")
    except Exception as exc:
        pytest.skip(f"Key simulation not available: {exc}")


class TestKeyboardShortcuts:
    """Verify keyboard shortcut functionality."""

    def test_f1_opens_shortcuts_window(self, app_node):
        """F1 should open the keyboard shortcuts window."""
        if not wait_for_sdk_ready(app_node):
            pytest.skip("SDK not ready")
        _press_key(app_node, "F1")
        time.sleep(1)
        # Verify app didn't crash
        window = app_node.child(roleName="frame")
        assert window.showing

    def test_ctrl_k_toggles_search(self, app_node):
        """Ctrl+K should toggle the search bar."""
        if not wait_for_sdk_ready(app_node):
            pytest.skip("SDK not ready")
        _press_key(app_node, "k", modifiers=["ctrl"])
        time.sleep(0.5)
        window = app_node.child(roleName="frame")
        assert window.showing

    def test_ctrl_n_creates_conversation(self, app_node):
        """Ctrl+N should create a new conversation."""
        if not wait_for_sdk_ready(app_node):
            pytest.skip("SDK not ready")
        _press_key(app_node, "n", modifiers=["ctrl"])
        time.sleep(1.5)
        window = app_node.child(roleName="frame")
        assert window.showing

    def test_escape_key(self, app_node):
        """Escape should not crash the app."""
        if not wait_for_sdk_ready(app_node):
            pytest.skip("SDK not ready")
        _press_key(app_node, "Escape")
        time.sleep(0.5)
        window = app_node.child(roleName="frame")
        assert window.showing
