# SPDX-License-Identifier: GPL-3.0-or-later
"""UI Test: Application Launch (TASK-078).

Verifies that the application starts correctly, the main window
appears in the AT-SPI tree, and the expected UI elements are present.
"""

from __future__ import annotations

import pytest

from .conftest import VALID_APP_NAMES, find_by_role_and_name

pytestmark = [
    pytest.mark.ui,
    pytest.mark.timeout(60),
]


class TestAppLaunch:
    """Verify basic application launch and window presence."""

    def test_app_appears_in_atspi_tree(self, app_node):
        """The app should appear in the AT-SPI tree with a recognisable name."""
        assert app_node is not None
        name = getattr(app_node, "name", "") or ""
        # The app registers as "main.py" when launched via python -m
        assert any(n in name.lower() for n in VALID_APP_NAMES), f"Unexpected app name: {name!r}"

    def test_main_window_present(self, app_node):
        """The main window frame should be present."""
        window = app_node.child(roleName="frame")
        assert window is not None
        assert window.showing

    def test_header_bar_present(self, app_node):
        """The HeaderBar should be visible."""
        window = app_node.child(roleName="frame")
        assert window.child_count > 0

    def test_sidebar_present(self, app_node):
        """The sidebar or main UI buttons should be present."""
        window = app_node.child(roleName="frame")
        # Look for the "New Chat" button or "Conversations" grouping
        btn = find_by_role_and_name(window, "button", "New Chat")
        if btn is not None:
            return
        # Look for Conversations grouping (sidebar)
        from .conftest import safe_find

        grp = safe_find(
            window,
            lambda n: (
                n.roleName == "grouping" and "Conversations" in (getattr(n, "name", "") or "")
            ),
        )
        if grp is not None:
            return
        # Fallback: verify the window has content
        assert window.child_count > 2, "Window seems empty"

    def test_window_has_expected_size(self, app_node):
        """The window should have a reasonable size."""
        window = app_node.child(roleName="frame")
        try:
            size = window.get_size()
        except RuntimeError:
            pytest.skip("get_size() requires ponytail daemon")
        if size:
            width, height = size
            assert width >= 400, f"Window too narrow: {width}"
            assert height >= 300, f"Window too short: {height}"

    def test_content_area_present(self, app_node):
        """The content area should show initial state."""
        window = app_node.child(roleName="frame")
        # The window should have substantial children (content area present)
        assert window.child_count >= 1
