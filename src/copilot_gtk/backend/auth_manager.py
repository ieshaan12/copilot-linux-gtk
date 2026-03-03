# SPDX-License-Identifier: GPL-3.0-or-later
"""AuthManager — Manages authentication tokens for the Copilot SDK.

Supports three authentication methods (in priority order):

1. **Explicit token** — ``github_token`` passed to ``CopilotClientOptions``.
   Stored/retrieved from GNOME Keyring via ``libsecret``.
2. **Environment variable** — ``GITHUB_TOKEN`` or ``GH_TOKEN`` in the
   process environment.
3. **Logged-in user** — The copilot CLI's built-in OAuth / ``gh`` auth
   (``use_logged_in_user=True`` in ``CopilotClientOptions``).
"""

from __future__ import annotations

import logging
import os
from enum import Enum
from typing import Any

import gi

gi.require_version("GLib", "2.0")
from gi.repository import GObject  # noqa: E402

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# libsecret schema
# ---------------------------------------------------------------------------

_SECRET_AVAILABLE = False
try:
    gi.require_version("Secret", "1")
    from gi.repository import Secret  # noqa: E402

    _SECRET_AVAILABLE = True
except (ValueError, ImportError):
    log.warning("libsecret not available — token storage disabled")
    Secret = None  # type: ignore[assignment, misc]

# Schema for storing GitHub tokens in GNOME Keyring
_TOKEN_SCHEMA: Secret.Schema | None = None
if _SECRET_AVAILABLE:
    _TOKEN_SCHEMA = Secret.Schema.new(
        "io.github.ieshaan.CopilotGTK.Token",
        Secret.SchemaFlags.NONE,
        {
            "type": Secret.SchemaAttributeType.STRING,
        },
    )


class AuthMethod(Enum):
    """How the application is authenticating."""

    NONE = "none"
    TOKEN_KEYRING = "token_keyring"  # Stored in GNOME Keyring
    TOKEN_ENV = "token_env"  # GITHUB_TOKEN / GH_TOKEN env var
    LOGGED_IN_USER = "logged_in_user"  # copilot CLI OAuth


class AuthManager(GObject.Object):
    """Manages authentication state and token storage.

    Signals:
        auth-changed(method: str, is_authenticated: bool):
            Emitted whenever the effective auth method changes.
    """

    __gsignals__ = {
        "auth-changed": (
            GObject.SignalFlags.RUN_LAST,
            None,
            (str, bool),  # method name, is_authenticated
        ),
    }

    def __init__(self) -> None:
        super().__init__()
        self._method: AuthMethod = AuthMethod.NONE
        self._token: str | None = None
        self._login: str | None = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def method(self) -> AuthMethod:
        """The currently active authentication method."""
        return self._method

    @property
    def is_authenticated(self) -> bool:
        return self._method != AuthMethod.NONE

    @property
    def login(self) -> str | None:
        return self._login

    @login.setter
    def login(self, value: str | None) -> None:
        self._login = value

    # ------------------------------------------------------------------
    # Detection — figure out which auth source is available
    # ------------------------------------------------------------------

    def detect(self) -> AuthMethod:
        """Detect the best available auth method (synchronous).

        Priority order:
        1. Token stored in GNOME Keyring
        2. GITHUB_TOKEN or GH_TOKEN environment variable
        3. Logged-in user (always available as a fallback — the SDK
           itself will verify when ``start()`` is called)

        Returns the detected :class:`AuthMethod`.
        """
        # 1) Keyring token
        token = self._load_token_from_keyring()
        if token:
            self._token = token
            self._method = AuthMethod.TOKEN_KEYRING
            self.emit("auth-changed", self._method.value, True)
            return self._method

        # 2) Environment variable
        env_token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if env_token:
            self._token = env_token
            self._method = AuthMethod.TOKEN_ENV
            self.emit("auth-changed", self._method.value, True)
            return self._method

        # 3) Logged-in user is always attempted as a last resort
        self._token = None
        self._method = AuthMethod.LOGGED_IN_USER
        self.emit("auth-changed", self._method.value, True)
        return self._method

    # ------------------------------------------------------------------
    # CopilotClientOptions helper
    # ------------------------------------------------------------------

    def get_client_options(self) -> dict[str, Any]:
        """Return a dict suitable for ``CopilotClientOptions``.

        Merges the detected auth config with any user-set preferences
        (e.g. CLI path override).
        """
        opts: dict[str, Any] = {}

        has_token = (
            self._method == AuthMethod.TOKEN_KEYRING
            and self._token
            or self._method == AuthMethod.TOKEN_ENV
            and self._token
        )
        if has_token:
            opts["github_token"] = self._token
            opts["use_logged_in_user"] = False
        else:
            # Logged-in user — let the SDK handle it
            opts["use_logged_in_user"] = True

        return opts

    # ------------------------------------------------------------------
    # Token management — GNOME Keyring (libsecret)
    # ------------------------------------------------------------------

    def store_token(self, token: str) -> bool:
        """Store a GitHub token in the GNOME Keyring.

        Returns *True* on success, *False* if libsecret is unavailable
        or an error occurs.
        """
        if not _SECRET_AVAILABLE or _TOKEN_SCHEMA is None:
            log.warning("Cannot store token — libsecret not available")
            return False

        try:
            success = Secret.password_store_sync(
                _TOKEN_SCHEMA,
                {"type": "github_token"},
                Secret.COLLECTION_DEFAULT,
                "Copilot for GNOME — GitHub Token",
                token,
                None,
            )
            if success:
                self._token = token
                self._method = AuthMethod.TOKEN_KEYRING
                self.emit("auth-changed", self._method.value, True)
                log.info("Token stored in GNOME Keyring")
            return success
        except Exception:
            log.exception("Failed to store token in Keyring")
            return False

    def delete_token(self) -> bool:
        """Remove the stored token from GNOME Keyring.

        Returns *True* on success.
        """
        if not _SECRET_AVAILABLE or _TOKEN_SCHEMA is None:
            return False

        try:
            removed = Secret.password_clear_sync(
                _TOKEN_SCHEMA,
                {"type": "github_token"},
                None,
            )
            if removed:
                self._token = None
                # Re-detect to fall back to env or logged-in user
                self.detect()
                log.info("Token removed from GNOME Keyring")
            return removed
        except Exception:
            log.exception("Failed to remove token from Keyring")
            return False

    def _load_token_from_keyring(self) -> str | None:
        """Try to load a stored token from GNOME Keyring (sync)."""
        if not _SECRET_AVAILABLE or _TOKEN_SCHEMA is None:
            return None

        try:
            token = Secret.password_lookup_sync(
                _TOKEN_SCHEMA,
                {"type": "github_token"},
                None,
            )
            return token or None
        except Exception:
            log.exception("Failed to load token from Keyring")
            return None

    def has_stored_token(self) -> bool:
        """Check whether a token exists in the Keyring without loading it."""
        return self._load_token_from_keyring() is not None

    # ------------------------------------------------------------------
    # Environment variable helpers
    # ------------------------------------------------------------------

    @staticmethod
    def has_env_token() -> bool:
        """Check whether a GitHub token is set via environment variables."""
        return bool(os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN"))

    @staticmethod
    def get_env_token_name() -> str | None:
        """Return the name of the environment variable providing a token."""
        if os.environ.get("GITHUB_TOKEN"):
            return "GITHUB_TOKEN"
        if os.environ.get("GH_TOKEN"):
            return "GH_TOKEN"
        return None
