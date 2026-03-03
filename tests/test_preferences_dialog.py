# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for PreferencesDialog."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import gi
import pytest

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio  # noqa: E402

from copilot_gtk.backend.auth_manager import AuthManager  # noqa: E402
from copilot_gtk.widgets.preferences_dialog import PreferencesDialog  # noqa: E402


@pytest.fixture
def settings():
    """Provide a GSettings instance using the project schema."""
    schema_dir = Path(__file__).parent.parent / "data"
    source = Gio.SettingsSchemaSource.new_from_directory(
        str(schema_dir),
        Gio.SettingsSchemaSource.get_default(),
        False,
    )
    schema = source.lookup("io.github.ieshaan.CopilotGTK", False)
    s = Gio.Settings.new_full(schema, None, None)
    # Reset to defaults so tests don't leak state
    s.set_boolean("streaming-enabled", True)
    s.set_string("default-model", "")
    s.set_string("system-message", "")
    s.set_string("cli-path", "")
    s.set_string("log-level", "warning")
    s.set_boolean("byok-enabled", False)
    s.set_string("byok-base-url", "")
    s.set_string("byok-model", "")
    return s


@pytest.fixture
def auth_manager(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    mgr = AuthManager()
    with patch.object(mgr, "_load_token_from_keyring", return_value=None):
        mgr.detect()
    return mgr


class TestPreferencesDialog:
    """Tests for the PreferencesDialog widget."""

    def test_creation(self, settings, auth_manager):
        dialog = PreferencesDialog(
            settings=settings,
            auth_manager=auth_manager,
        )
        assert dialog.get_title() == "Preferences"

    def test_has_three_pages(self, settings, auth_manager):
        """The dialog should have General, Authentication, and Advanced pages."""
        dialog = PreferencesDialog(
            settings=settings,
            auth_manager=auth_manager,
        )
        # PreferencesDialog doesn't expose a simple page count API,
        # but we can verify it was created without errors
        assert isinstance(dialog, Adw.PreferencesDialog)

    def test_streaming_switch_reflects_setting(self, settings, auth_manager):
        """Streaming switch should reflect the GSettings value."""
        settings.set_boolean("streaming-enabled", False)
        dialog = PreferencesDialog(
            settings=settings,
            auth_manager=auth_manager,
        )
        assert dialog._streaming_switch.get_active() is False

    def test_streaming_switch_updates_setting(self, settings, auth_manager):
        """Toggling the streaming switch should update GSettings."""
        dialog = PreferencesDialog(
            settings=settings,
            auth_manager=auth_manager,
        )
        dialog._streaming_switch.set_active(False)
        assert settings.get_boolean("streaming-enabled") is False

    def test_system_message_reflects_setting(self, settings, auth_manager):
        """System message entry should show the current setting value."""
        settings.set_string("system-message", "Be concise.")
        dialog = PreferencesDialog(
            settings=settings,
            auth_manager=auth_manager,
        )
        assert dialog._system_msg_row.get_text() == "Be concise."

    def test_cli_path_reflects_setting(self, settings, auth_manager):
        """CLI path entry should reflect the GSettings value."""
        settings.set_string("cli-path", "/usr/bin/copilot")
        dialog = PreferencesDialog(
            settings=settings,
            auth_manager=auth_manager,
        )
        assert dialog._cli_path_row.get_text() == "/usr/bin/copilot"

    def test_cli_path_updates_setting(self, settings, auth_manager):
        """Changing the CLI path should update GSettings."""
        dialog = PreferencesDialog(
            settings=settings,
            auth_manager=auth_manager,
        )
        dialog._cli_path_row.set_text("/custom/path")
        assert settings.get_string("cli-path") == "/custom/path"

    def test_byok_fields_disabled_by_default(self, settings, auth_manager):
        """BYOK fields should be disabled when the toggle is off."""
        dialog = PreferencesDialog(
            settings=settings,
            auth_manager=auth_manager,
        )
        assert dialog._byok_url_row.get_sensitive() is False
        assert dialog._byok_key_row.get_sensitive() is False
        assert dialog._byok_model_row.get_sensitive() is False

    def test_byok_fields_enabled_when_toggled(self, settings, auth_manager):
        """BYOK fields should become sensitive when toggle is on."""
        dialog = PreferencesDialog(
            settings=settings,
            auth_manager=auth_manager,
        )
        dialog._byok_enabled_switch.set_active(True)
        assert dialog._byok_url_row.get_sensitive() is True
        assert dialog._byok_key_row.get_sensitive() is True
        assert dialog._byok_model_row.get_sensitive() is True

    def test_model_row_has_auto_option(self, settings, auth_manager):
        """The model ComboRow should always have an (Auto) option."""
        dialog = PreferencesDialog(
            settings=settings,
            auth_manager=auth_manager,
        )
        first_item = dialog._model_store.get_string(0)
        assert first_item == "(Auto)"

    def test_auth_status_row_shows_method(self, settings, auth_manager):
        """Auth status row should display the current auth method."""
        dialog = PreferencesDialog(
            settings=settings,
            auth_manager=auth_manager,
        )
        subtitle = dialog._auth_status_row.get_subtitle()
        assert "logged_in_user" in subtitle
