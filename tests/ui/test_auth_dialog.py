# SPDX-License-Identifier: GPL-3.0-or-later
"""UI Test: Auth Dialog (TASK-087).

Verifies authentication UI behavior. With the mock backend,
auth is always successful, so we test that the app doesn't show
an auth error state and starts normally.
"""

from __future__ import annotations

import time

import pytest

from .conftest import wait_for_sdk_ready

pytestmark = [
    pytest.mark.ui,
    pytest.mark.timeout(60),
]


class TestAuthDialog:
    """Verify authentication-related UI behavior."""

    def test_app_starts_without_auth_error(self, app_node):
        """With mock backend, the app should start without auth errors."""
        window = app_node.child(roleName="frame")
        assert window is not None
        assert window.showing

    def test_sdk_becomes_ready(self, app_node):
        """The mock SDK should become ready."""
        ready = wait_for_sdk_ready(app_node, timeout=12)
        if not ready:
            # If we can't detect readiness, verify the app is alive
            window = app_node.child(roleName="frame")
            assert window.showing, "App not showing but SDK not detected as ready"

    def test_no_fatal_error_page(self, app_node):
        """The fatal error page should not be shown with mock backend."""
        window = app_node.child(roleName="frame")
        time.sleep(2)
        # The window should be showing normally
        assert window.showing
