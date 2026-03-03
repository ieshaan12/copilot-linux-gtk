# SPDX-License-Identifier: GPL-3.0-or-later
"""UI Test: Dark Mode (TASK-090).

Verifies that toggling the color scheme (dark/light mode) does not
crash the application. Uses dconf/gsettings to toggle the GNOME
color scheme preference.
"""

from __future__ import annotations

import subprocess
import time

import pytest

pytestmark = [
    pytest.mark.ui,
    pytest.mark.timeout(60),
]


def _set_color_scheme(prefer_dark: bool) -> bool:
    """Set the GNOME color scheme preference via gsettings.

    Returns True if successful, False if gsettings is not available.
    """
    value = "prefer-dark" if prefer_dark else "default"
    try:
        subprocess.run(
            [
                "gsettings", "set",
                "org.gnome.desktop.interface",
                "color-scheme",
                value,
            ],
            timeout=5,
            capture_output=True,
            check=True,
        )
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def _get_color_scheme() -> str | None:
    """Get the current GNOME color scheme preference."""
    try:
        result = subprocess.run(
            [
                "gsettings", "get",
                "org.gnome.desktop.interface",
                "color-scheme",
            ],
            timeout=5,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip().strip("'")
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None


class TestDarkMode:
    """Verify dark/light mode transitions."""

    def test_toggle_to_dark_mode(self, app_node):
        """Switching to dark mode should not crash the app."""
        original = _get_color_scheme()
        if original is None:
            pytest.skip("gsettings not available")

        try:
            success = _set_color_scheme(prefer_dark=True)
            if not success:
                pytest.skip("Could not set color scheme")

            time.sleep(1)

            # App should still be alive
            window = app_node.child(roleName="frame")
            assert window is not None
            assert window.showing
        finally:
            # Restore original
            if original:
                _set_color_scheme(prefer_dark=("dark" in original))

    def test_toggle_to_light_mode(self, app_node):
        """Switching to light mode should not crash the app."""
        original = _get_color_scheme()
        if original is None:
            pytest.skip("gsettings not available")

        try:
            success = _set_color_scheme(prefer_dark=False)
            if not success:
                pytest.skip("Could not set color scheme")

            time.sleep(1)

            window = app_node.child(roleName="frame")
            assert window is not None
            assert window.showing
        finally:
            if original:
                _set_color_scheme(prefer_dark=("dark" in original))

    def test_rapid_toggle_no_crash(self, app_node):
        """Rapidly toggling between modes should not crash."""
        original = _get_color_scheme()
        if original is None:
            pytest.skip("gsettings not available")

        try:
            for _ in range(3):
                _set_color_scheme(prefer_dark=True)
                time.sleep(0.3)
                _set_color_scheme(prefer_dark=False)
                time.sleep(0.3)

            time.sleep(1)

            # App should still be alive
            window = app_node.child(roleName="frame")
            assert window is not None
            assert window.showing
        finally:
            if original:
                _set_color_scheme(prefer_dark=("dark" in original))
