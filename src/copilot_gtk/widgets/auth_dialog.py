# SPDX-License-Identifier: GPL-3.0-or-later
"""AuthDialog — Authentication setup dialog for Copilot for GNOME.

Shown on first launch when no authentication is detected, or when
the user clicks "Sign In" from the preferences dialog.
"""

from __future__ import annotations

import logging
import subprocess
from typing import TYPE_CHECKING

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, GObject, Gtk  # noqa: E402

if TYPE_CHECKING:
    from ..backend.auth_manager import AuthManager

log = logging.getLogger(__name__)


class AuthDialog(Adw.Dialog):
    """Authentication dialog with three auth paths.

    1. **GitHub sign-in** — launches ``copilot auth`` in the browser.
    2. **Environment variable** — detected automatically.
    3. **Manual token entry** — stored in GNOME Keyring.

    Signals:
        auth-complete(method: str):
            Emitted when authentication succeeds via any method.
    """

    __gtype_name__ = "AuthDialog"

    __gsignals__ = {
        "auth-complete": (
            GObject.SignalFlags.RUN_LAST,
            None,
            (str,),  # auth method name
        ),
    }

    def __init__(self, auth_manager: AuthManager, **kwargs) -> None:
        super().__init__(**kwargs)
        self._auth_manager = auth_manager

        self.set_title("Sign In")
        self.set_content_width(480)
        self.set_content_height(520)

        self._build_ui()

    def _build_ui(self) -> None:
        """Construct the dialog UI."""
        toolbar = Adw.ToolbarView()
        self.set_child(toolbar)

        header = Adw.HeaderBar()
        header.set_show_end_title_buttons(False)
        header.set_show_start_title_buttons(False)
        toolbar.add_top_bar(header)

        content = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=24,
            margin_top=24,
            margin_bottom=24,
            margin_start=24,
            margin_end=24,
        )
        toolbar.set_content(content)

        # --- Status page ---
        status = Adw.StatusPage(
            title="Welcome to Copilot for GNOME",
            description="Sign in with your GitHub account to get started.",
            icon_name="io.github.ieshaan.CopilotGTK-symbolic",
        )
        status.set_vexpand(True)
        content.append(status)

        # --- Auth status indicator ---
        self._status_row = Adw.ActionRow(
            title="Authentication Status",
            subtitle="Not authenticated",
        )
        self._status_icon = Gtk.Image.new_from_icon_name(
            "dialog-warning-symbolic"
        )
        self._status_icon.add_css_class("warning")
        self._status_row.add_prefix(self._status_icon)

        status_group = Adw.PreferencesGroup(title="Status")
        status_group.add(self._status_row)
        content.append(status_group)

        # --- Option 1: GitHub Sign In (copilot CLI) ---
        login_group = Adw.PreferencesGroup(
            title="GitHub Account",
            description="Sign in using your GitHub account via the Copilot CLI.",
        )

        login_row = Adw.ActionRow(
            title="Sign in with GitHub",
            subtitle="Opens your browser for GitHub OAuth",
        )
        login_row.add_prefix(
            Gtk.Image.new_from_icon_name("web-browser-symbolic")
        )
        login_btn = Gtk.Button(label="Sign In")
        login_btn.set_valign(Gtk.Align.CENTER)
        login_btn.add_css_class("suggested-action")
        login_btn.connect("clicked", self._on_github_login_clicked)
        login_row.add_suffix(login_btn)
        login_row.set_activatable_widget(login_btn)
        login_group.add(login_row)
        content.append(login_group)

        # --- Option 2: Environment variable status ---
        if self._auth_manager.has_env_token():
            env_name = self._auth_manager.get_env_token_name()
            env_group = Adw.PreferencesGroup(
                title="Environment Variable",
                description=f"A token was detected in ${env_name}.",
            )
            env_row = Adw.ActionRow(
                title=f"${env_name} detected",
                subtitle="This token will be used automatically.",
            )
            env_row.add_prefix(
                Gtk.Image.new_from_icon_name("emblem-ok-symbolic")
            )
            use_env_btn = Gtk.Button(label="Use This")
            use_env_btn.set_valign(Gtk.Align.CENTER)
            use_env_btn.add_css_class("suggested-action")
            use_env_btn.connect("clicked", self._on_use_env_token)
            env_row.add_suffix(use_env_btn)
            env_row.set_activatable_widget(use_env_btn)
            env_group.add(env_row)
            content.append(env_group)

        # --- Option 3: Manual token entry ---
        token_group = Adw.PreferencesGroup(
            title="Personal Access Token",
            description="Enter a GitHub personal access token with Copilot scope.",
        )

        self._token_entry = Adw.PasswordEntryRow(title="Token")
        token_group.add(self._token_entry)

        token_btn_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            halign=Gtk.Align.END,
            margin_top=8,
        )
        save_token_btn = Gtk.Button(label="Save Token")
        save_token_btn.add_css_class("suggested-action")
        save_token_btn.connect("clicked", self._on_save_token_clicked)
        token_btn_box.append(save_token_btn)
        token_group.add(token_btn_box)

        content.append(token_group)

        # Update status if already authenticated
        self._refresh_status()

    # ------------------------------------------------------------------
    # Status refresh
    # ------------------------------------------------------------------

    def _refresh_status(self) -> None:
        """Update the status indicator based on the auth manager."""
        method = self._auth_manager.method
        login = self._auth_manager.login

        if self._auth_manager.is_authenticated:
            login_str = f" ({login})" if login else ""
            self._status_row.set_subtitle(
                f"Authenticated via {method.value}{login_str}"
            )
            self._status_icon.set_from_icon_name("emblem-ok-symbolic")
            self._status_icon.remove_css_class("warning")
            self._status_icon.add_css_class("success")
        else:
            self._status_row.set_subtitle("Not authenticated")
            self._status_icon.set_from_icon_name("dialog-warning-symbolic")
            self._status_icon.remove_css_class("success")
            self._status_icon.add_css_class("warning")

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _on_github_login_clicked(self, _btn: Gtk.Button) -> None:
        """Launch copilot CLI auth in the user's browser."""
        from ..backend.auth_manager import AuthMethod

        try:
            Gio.AppInfo.launch_default_for_uri(
                "https://github.com/login/device", None
            )
        except Exception:
            log.exception("Failed to open browser")

        # Assume logged_in_user will work after browser auth completes
        self._auth_manager._method = AuthMethod.LOGGED_IN_USER  # noqa: SLF001
        self._auth_manager.emit(
            "auth-changed", AuthMethod.LOGGED_IN_USER.value, True
        )
        self._refresh_status()
        self.emit("auth-complete", AuthMethod.LOGGED_IN_USER.value)

    def _on_use_env_token(self, _btn: Gtk.Button) -> None:
        """Use the detected environment variable token."""
        self._auth_manager.detect()
        self._refresh_status()
        self.emit("auth-complete", self._auth_manager.method.value)

    def _on_save_token_clicked(self, _btn: Gtk.Button) -> None:
        """Save the manually entered token to GNOME Keyring."""
        token = self._token_entry.get_text().strip()
        if not token:
            self._token_entry.add_css_class("error")
            return

        self._token_entry.remove_css_class("error")
        success = self._auth_manager.store_token(token)

        if success:
            self._refresh_status()
            self.emit("auth-complete", self._auth_manager.method.value)
            self._token_entry.set_text("")
        else:
            # Show error toast — find the nearest toast overlay
            self._token_entry.add_css_class("error")
