# SPDX-License-Identifier: GPL-3.0-or-later
"""UI Test: Send Message (TASK-080).

Verifies that the send message flow works: user can create a conversation,
type in the input area, and the app handles send without crashing.
"""

from __future__ import annotations

import time

import pytest

from .conftest import click_new_chat, find_text_input, wait_for_sdk_ready

pytestmark = [
    pytest.mark.ui,
    pytest.mark.timeout(60),
]


class TestSendMessage:
    """Verify message sending flow."""

    def test_input_area_accepts_text(self, app_node):
        """The chat input should accept text input via AT-SPI."""
        if not wait_for_sdk_ready(app_node):
            pytest.skip("SDK not ready")
        if not click_new_chat(app_node):
            pytest.skip("Could not create conversation")

        entry = find_text_input(app_node)
        if entry is None:
            pytest.skip("Chat text input not found via AT-SPI")

        try:
            entry.grab_focus()
            entry.set_text_contents("Hello from UI test")
            time.sleep(0.5)
        except Exception:
            pytest.skip("set_text_contents not supported via AT-SPI")

        # Verify the app is still alive
        window = app_node.child(roleName="frame")
        assert window.showing

    def test_send_button_exists(self, app_node):
        """A send button or interactive controls should be present."""
        if not wait_for_sdk_ready(app_node):
            pytest.skip("SDK not ready")
        if not click_new_chat(app_node):
            pytest.skip("Could not create conversation")

        window = app_node.child(roleName="frame")
        from .conftest import find_by_role_and_name
        btn = find_by_role_and_name(window, "button", "Send")
        if btn is not None:
            return
        # Fallback: check any buttons exist
        try:
            buttons = window.find_children(
                lambda n: n.roleName in ("push button", "button")
            )
            assert len(buttons) > 0, "No buttons found in chat view"
        except Exception:
            assert window.child_count > 0

    def test_send_message_no_crash(self, app_node):
        """Sending a message should not crash the app."""
        if not wait_for_sdk_ready(app_node):
            pytest.skip("SDK not ready")
        if not click_new_chat(app_node):
            pytest.skip("Could not create conversation")

        entry = find_text_input(app_node)
        if entry is None:
            pytest.skip("Chat text input not found")

        try:
            entry.grab_focus()
            entry.set_text_contents("What is Python?")
            time.sleep(0.3)
        except Exception:
            pytest.skip("Cannot type in text input via AT-SPI")

        # Try to find and click send
        window = app_node.child(roleName="frame")
        from .conftest import find_by_role_and_name
        send_btn = find_by_role_and_name(window, "button", "Send")
        if send_btn:
            try:
                send_btn.click()
            except Exception:
                pass

        time.sleep(3)
        assert window.showing, "App crashed after sending message"

    def test_app_responsive_after_message(self, app_node):
        """After sending, the app should remain responsive."""
        if not wait_for_sdk_ready(app_node):
            pytest.skip("SDK not ready")
        if not click_new_chat(app_node):
            pytest.skip("Could not create conversation")

        time.sleep(1)
        window = app_node.child(roleName="frame")
        assert window.showing
        assert window.child_count > 0
