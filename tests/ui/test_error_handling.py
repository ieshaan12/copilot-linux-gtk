# SPDX-License-Identifier: GPL-3.0-or-later
"""UI Test: Error Handling (TASK-086).

Verifies that errors from the backend don't crash the app,
and the app remains functional after errors.
"""

from __future__ import annotations

import os
import time

import pytest

from .conftest import click_new_chat, wait_for_sdk_ready

pytestmark = [
    pytest.mark.ui,
    pytest.mark.timeout(60),
]


class TestErrorHandling:
    """Verify error display and recovery behavior."""

    def test_app_survives_mock_error(self, app_node):
        """When the mock backend is configured to error, app should not crash."""
        if not wait_for_sdk_ready(app_node):
            pytest.skip("SDK not ready")

        os.environ["COPILOT_GTK_MOCK_ERROR"] = "Network connection failed"
        try:
            click_new_chat(app_node)
            time.sleep(2)
            window = app_node.child(roleName="frame")
            assert window.showing, "App crashed after mock error"
        finally:
            os.environ.pop("COPILOT_GTK_MOCK_ERROR", None)

    def test_app_functional_after_error(self, app_node):
        """The app should remain functional after an error."""
        if not wait_for_sdk_ready(app_node):
            pytest.skip("SDK not ready")

        os.environ["COPILOT_GTK_MOCK_ERROR"] = "Temporary failure"
        try:
            click_new_chat(app_node)
            time.sleep(1)
        finally:
            os.environ.pop("COPILOT_GTK_MOCK_ERROR", None)

        time.sleep(1)
        window = app_node.child(roleName="frame")
        assert window.showing

    def test_no_crash_on_repeated_errors(self, app_node):
        """Repeated errors should not crash the application."""
        if not wait_for_sdk_ready(app_node):
            pytest.skip("SDK not ready")

        os.environ["COPILOT_GTK_MOCK_ERROR"] = "Repeated error"
        try:
            for _ in range(3):
                click_new_chat(app_node)
                time.sleep(0.5)
            time.sleep(2)
            window = app_node.child(roleName="frame")
            assert window.showing
        finally:
            os.environ.pop("COPILOT_GTK_MOCK_ERROR", None)

        os.environ.pop("COPILOT_GTK_MOCK_ERROR", None)
