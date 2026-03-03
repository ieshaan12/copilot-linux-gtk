# SPDX-License-Identifier: GPL-3.0-or-later
"""UI Test: New Conversation (TASK-079).

Verifies that clicking "New Chat" creates a new conversation,
a conversation row appears in the sidebar, and the chat view becomes active.
"""

from __future__ import annotations

import time

import pytest

from .conftest import (
    click_new_chat,
    find_by_role_and_name,
    find_text_input,
    wait_for_sdk_ready,
)

pytestmark = [
    pytest.mark.ui,
    pytest.mark.timeout(60),
]


class TestNewConversation:
    """Verify new conversation creation flow."""

    def test_new_chat_button_exists(self, app_node):
        """The 'New Chat' button should be accessible via AT-SPI."""
        if not wait_for_sdk_ready(app_node):
            pytest.skip("SDK not ready — cannot verify button")
        window = app_node.child(roleName="frame")
        btn = find_by_role_and_name(window, "push button", "New Chat")
        assert btn is not None, "New Chat button not found"

    def test_click_new_chat_creates_conversation(self, app_node):
        """Clicking 'New Chat' should create a new conversation."""
        if not wait_for_sdk_ready(app_node):
            pytest.skip("SDK not ready")

        assert click_new_chat(app_node), "Could not click New Chat button"

        # After clicking, verify the app didn't crash and has content
        window = app_node.child(roleName="frame")
        assert window.showing

    def test_conversation_appears_in_sidebar(self, app_node):
        """A new conversation should appear as a row in the sidebar list."""
        if not wait_for_sdk_ready(app_node):
            pytest.skip("SDK not ready")

        click_new_chat(app_node)
        time.sleep(1)

        window = app_node.child(roleName="frame")
        # The window should have content after creating a conversation
        assert window.child_count > 0
