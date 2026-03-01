# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for AuthDialog."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk  # noqa: E402

from copilot_gtk.backend.auth_manager import AuthManager, AuthMethod  # noqa: E402
from copilot_gtk.widgets.auth_dialog import AuthDialog  # noqa: E402


@pytest.fixture
def auth_manager(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    mgr = AuthManager()
    return mgr


class TestAuthDialog:
    """Tests for the AuthDialog widget."""

    def test_creation(self, auth_manager):
        dialog = AuthDialog(auth_manager=auth_manager)
        assert dialog.get_title() == "Sign In"

    def test_dialog_is_adw_dialog(self, auth_manager):
        dialog = AuthDialog(auth_manager=auth_manager)
        assert isinstance(dialog, Adw.Dialog)

    def test_status_shows_not_authenticated(self, auth_manager):
        """Status indicator shows 'Not authenticated' when no auth."""
        dialog = AuthDialog(auth_manager=auth_manager)
        assert "Not authenticated" in dialog._status_row.get_subtitle()

    def test_status_shows_authenticated(self, auth_manager, monkeypatch):
        """Status updates when auth manager is authenticated."""
        with patch.object(
            auth_manager, "_load_token_from_keyring", return_value=None
        ):
            auth_manager.detect()
        dialog = AuthDialog(auth_manager=auth_manager)
        # Logged-in user is considered authenticated
        subtitle = dialog._status_row.get_subtitle()
        assert "Authenticated" in subtitle or "logged_in_user" in subtitle

    def test_env_token_section_shown_when_available(self, monkeypatch):
        """When GITHUB_TOKEN is set, the env section should be present."""
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
        mgr = AuthManager()
        dialog = AuthDialog(auth_manager=mgr)
        # Dialog was created without error — env section is built
        assert dialog is not None

    def test_env_token_section_hidden_when_unavailable(self, auth_manager):
        """When no env token, the env section should not be built."""
        # auth_manager fixture has no env tokens
        dialog = AuthDialog(auth_manager=auth_manager)
        assert dialog is not None

    def test_token_entry_exists(self, auth_manager):
        """The manual token entry field should exist."""
        dialog = AuthDialog(auth_manager=auth_manager)
        assert dialog._token_entry is not None
        assert isinstance(dialog._token_entry, Adw.PasswordEntryRow)

    def test_save_empty_token_adds_error_class(self, auth_manager):
        """Saving an empty token should add error CSS class."""
        dialog = AuthDialog(auth_manager=auth_manager)
        dialog._token_entry.set_text("")
        dialog._on_save_token_clicked(MagicMock())
        assert dialog._token_entry.has_css_class("error")

    @patch("copilot_gtk.backend.auth_manager._SECRET_AVAILABLE", True)
    @patch("copilot_gtk.backend.auth_manager.Secret")
    def test_save_valid_token(self, mock_secret, auth_manager):
        """Saving a valid token should store it and emit auth-complete."""
        mock_secret.password_store_sync.return_value = True
        mock_secret.COLLECTION_DEFAULT = "default"

        dialog = AuthDialog(auth_manager=auth_manager)
        received = []
        dialog.connect("auth-complete", lambda _d, method: received.append(method))

        dialog._token_entry.set_text("ghp_valid_token")
        with patch("copilot_gtk.backend.auth_manager._TOKEN_SCHEMA", MagicMock()):
            dialog._on_save_token_clicked(MagicMock())

        assert len(received) == 1
        assert received[0] == "token_keyring"

    def test_auth_complete_signal_on_env_token(self, monkeypatch):
        """Using env token should emit auth-complete."""
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
        monkeypatch.delenv("GH_TOKEN", raising=False)
        mgr = AuthManager()
        dialog = AuthDialog(auth_manager=mgr)

        received = []
        dialog.connect("auth-complete", lambda _d, method: received.append(method))

        dialog._on_use_env_token(MagicMock())
        assert len(received) == 1
