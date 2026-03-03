# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for AuthManager — authentication management.

Tests exercise auth detection, token storage, and client options
generation using mocked libsecret calls.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from copilot_gtk.backend.auth_manager import (  # noqa: E402
    AuthManager,
    AuthMethod,
)


class TestAuthManagerDetection:
    """Tests for the detect() method."""

    def test_detect_env_token_github_token(self, monkeypatch):
        """GITHUB_TOKEN env var is detected."""
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test123")
        monkeypatch.delenv("GH_TOKEN", raising=False)
        mgr = AuthManager()
        # Patch keyring to return nothing
        with patch.object(mgr, "_load_token_from_keyring", return_value=None):
            result = mgr.detect()
        assert result == AuthMethod.TOKEN_ENV
        assert mgr.is_authenticated
        assert mgr.method == AuthMethod.TOKEN_ENV

    def test_detect_env_token_gh_token(self, monkeypatch):
        """GH_TOKEN env var is detected."""
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.setenv("GH_TOKEN", "ghp_test456")
        mgr = AuthManager()
        with patch.object(mgr, "_load_token_from_keyring", return_value=None):
            result = mgr.detect()
        assert result == AuthMethod.TOKEN_ENV

    def test_detect_keyring_token(self, monkeypatch):
        """Token from GNOME Keyring takes priority over env vars."""
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_env")
        mgr = AuthManager()
        with patch.object(mgr, "_load_token_from_keyring", return_value="ghp_keyring"):
            result = mgr.detect()
        assert result == AuthMethod.TOKEN_KEYRING

    def test_detect_fallback_logged_in_user(self, monkeypatch):
        """Falls back to logged_in_user when no tokens are available."""
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GH_TOKEN", raising=False)
        mgr = AuthManager()
        with patch.object(mgr, "_load_token_from_keyring", return_value=None):
            result = mgr.detect()
        assert result == AuthMethod.LOGGED_IN_USER
        assert mgr.is_authenticated  # Logged-in user is considered "authenticated"

    def test_detect_emits_auth_changed(self, monkeypatch):
        """detect() emits the auth-changed signal."""
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GH_TOKEN", raising=False)
        mgr = AuthManager()
        received = []
        mgr.connect("auth-changed", lambda _m, method, auth: received.append((method, auth)))
        with patch.object(mgr, "_load_token_from_keyring", return_value=None):
            mgr.detect()
        assert len(received) == 1
        assert received[0] == ("logged_in_user", True)


class TestAuthManagerClientOptions:
    """Tests for get_client_options()."""

    def test_options_with_keyring_token(self, monkeypatch):
        mgr = AuthManager()
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GH_TOKEN", raising=False)
        with patch.object(mgr, "_load_token_from_keyring", return_value="ghp_secret"):
            mgr.detect()
        opts = mgr.get_client_options()
        assert opts["github_token"] == "ghp_secret"
        assert opts["use_logged_in_user"] is False

    def test_options_with_env_token(self, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_env")
        monkeypatch.delenv("GH_TOKEN", raising=False)
        mgr = AuthManager()
        with patch.object(mgr, "_load_token_from_keyring", return_value=None):
            mgr.detect()
        opts = mgr.get_client_options()
        assert opts["github_token"] == "ghp_env"
        assert opts["use_logged_in_user"] is False

    def test_options_with_logged_in_user(self, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GH_TOKEN", raising=False)
        mgr = AuthManager()
        with patch.object(mgr, "_load_token_from_keyring", return_value=None):
            mgr.detect()
        opts = mgr.get_client_options()
        assert "github_token" not in opts
        assert opts["use_logged_in_user"] is True


class TestAuthManagerTokenStorage:
    """Tests for store_token() and delete_token() with mocked libsecret."""

    @patch("copilot_gtk.backend.auth_manager._SECRET_AVAILABLE", True)
    @patch("copilot_gtk.backend.auth_manager.Secret")
    def test_store_token_success(self, mock_secret):
        mock_secret.password_store_sync.return_value = True
        mock_secret.COLLECTION_DEFAULT = "default"
        mgr = AuthManager()
        with patch("copilot_gtk.backend.auth_manager._TOKEN_SCHEMA", MagicMock()):
            result = mgr.store_token("ghp_new_token")
        assert result is True
        assert mgr.method == AuthMethod.TOKEN_KEYRING

    @patch("copilot_gtk.backend.auth_manager._SECRET_AVAILABLE", False)
    def test_store_token_no_libsecret(self):
        mgr = AuthManager()
        result = mgr.store_token("ghp_token")
        assert result is False

    @patch("copilot_gtk.backend.auth_manager._SECRET_AVAILABLE", True)
    @patch("copilot_gtk.backend.auth_manager.Secret")
    def test_delete_token(self, mock_secret, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GH_TOKEN", raising=False)
        mock_secret.password_clear_sync.return_value = True
        mgr = AuthManager()
        with (
            patch("copilot_gtk.backend.auth_manager._TOKEN_SCHEMA", MagicMock()),
            patch.object(mgr, "_load_token_from_keyring", return_value=None),
        ):
            result = mgr.delete_token()
        assert result is True
        # After deletion, should re-detect and fall back
        assert mgr.method != AuthMethod.TOKEN_KEYRING


class TestAuthManagerEnvHelpers:
    """Tests for environment variable helpers."""

    def test_has_env_token_true(self, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "test")
        assert AuthManager.has_env_token() is True

    def test_has_env_token_false(self, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GH_TOKEN", raising=False)
        assert AuthManager.has_env_token() is False

    def test_get_env_token_name_github(self, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "test")
        assert AuthManager.get_env_token_name() == "GITHUB_TOKEN"

    def test_get_env_token_name_gh(self, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.setenv("GH_TOKEN", "test")
        assert AuthManager.get_env_token_name() == "GH_TOKEN"

    def test_get_env_token_name_none(self, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GH_TOKEN", raising=False)
        assert AuthManager.get_env_token_name() is None


class TestAuthManagerProperties:
    """Tests for basic properties."""

    def test_initial_state(self):
        mgr = AuthManager()
        assert mgr.method == AuthMethod.NONE
        assert mgr.is_authenticated is False
        assert mgr.login is None

    def test_login_property(self):
        mgr = AuthManager()
        mgr.login = "testuser"
        assert mgr.login == "testuser"

    def test_auth_method_enum_values(self):
        assert AuthMethod.NONE.value == "none"
        assert AuthMethod.TOKEN_KEYRING.value == "token_keyring"
        assert AuthMethod.TOKEN_ENV.value == "token_env"
        assert AuthMethod.LOGGED_IN_USER.value == "logged_in_user"
