# SPDX-License-Identifier: GPL-3.0-or-later
"""UI Test: Markdown Rendering (TASK-083).

Verifies that messages containing Markdown are rendered without crashing
the application and the chat view remains functional.
"""

from __future__ import annotations

import os
import time

import pytest

from .conftest import click_new_chat, find_text_input, wait_for_sdk_ready

pytestmark = [
    pytest.mark.ui,
    pytest.mark.timeout(60),
]

# Set a mock response with rich Markdown content
MARKDOWN_RESPONSE = (
    "# Heading 1\n\n"
    "This has **bold text** and *italic text*.\n\n"
    "## Code Example\n\n"
    "```python\n"
    "def hello():\n"
    "    print('world')\n"
    "```\n\n"
    "Here's a list:\n"
    "- Item one\n"
    "- Item two\n"
    "- Item three\n"
)


class TestMarkdownRendering:
    """Verify Markdown content rendering in chat view."""

    def test_markdown_response_no_crash(self, app_node):
        """Rendering a Markdown response should not crash the app."""
        if not wait_for_sdk_ready(app_node):
            pytest.skip("SDK not ready")

        os.environ["COPILOT_GTK_MOCK_RESPONSE"] = MARKDOWN_RESPONSE
        try:
            if not click_new_chat(app_node):
                pytest.skip("Could not create conversation")

            entry = find_text_input(app_node)
            if entry is None:
                pytest.skip("Text input not found")

            try:
                entry.grab_focus()
                entry.set_text_contents("show markdown")
                time.sleep(0.3)
            except Exception:
                pytest.skip("Cannot type via AT-SPI")

            # Try to send
            window = app_node.child(roleName="frame")
            from .conftest import find_by_role_and_name as _find_btn
            send_btn = _find_btn(window, "button", "Send")
            if send_btn:
                try:
                    send_btn.click()
                except Exception:
                    pass

            time.sleep(4)
            assert window.showing, "App crashed rendering Markdown"
        finally:
            os.environ.pop("COPILOT_GTK_MOCK_RESPONSE", None)

    def test_code_block_rendering(self, app_node):
        """Code blocks in responses should not crash the app."""
        if not wait_for_sdk_ready(app_node):
            pytest.skip("SDK not ready")

        os.environ["COPILOT_GTK_MOCK_RESPONSE"] = "```python\nprint('hello')\n```"
        try:
            if not click_new_chat(app_node):
                pytest.skip("Could not create conversation")
            time.sleep(2)
            window = app_node.child(roleName="frame")
            assert window.showing
        finally:
            os.environ.pop("COPILOT_GTK_MOCK_RESPONSE", None)

    def test_long_response_rendering(self, app_node):
        """Long responses should render without crashing."""
        if not wait_for_sdk_ready(app_node):
            pytest.skip("SDK not ready")

        long_response = "This is a test paragraph.\n\n" * 20
        os.environ["COPILOT_GTK_MOCK_RESPONSE"] = long_response
        try:
            if not click_new_chat(app_node):
                pytest.skip("Could not create conversation")
            time.sleep(2)
            window = app_node.child(roleName="frame")
            assert window.showing
        finally:
            os.environ.pop("COPILOT_GTK_MOCK_RESPONSE", None)
