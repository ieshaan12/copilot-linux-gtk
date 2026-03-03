# SPDX-License-Identifier: GPL-3.0-or-later
"""PreferencesDialog — Application settings dialog.

Provides an ``Adw.PreferencesDialog`` with three pages:

- **General** — Default model, streaming toggle, system message.
- **Authentication** — Auth status, token management, sign-in/out.
- **Advanced** — CLI path override, log level, BYOK configuration.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, Gtk  # noqa: E402

if TYPE_CHECKING:
    from ..backend.auth_manager import AuthManager
    from ..backend.copilot_service import CopilotService

log = logging.getLogger(__name__)


class PreferencesDialog(Adw.PreferencesDialog):
    """Application preferences dialog with General, Auth, and Advanced pages."""

    __gtype_name__ = "PreferencesDialog"

    def __init__(
        self,
        settings: Gio.Settings,
        auth_manager: AuthManager,
        service: CopilotService | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._settings = settings
        self._auth_manager = auth_manager
        self._service = service

        self.set_title("Preferences")

        self._build_general_page()
        self._build_auth_page()
        self._build_advanced_page()

    # ==================================================================
    # General Page
    # ==================================================================

    def _build_general_page(self) -> None:
        page = Adw.PreferencesPage(
            title="General",
            icon_name="preferences-system-symbolic",
        )
        self.add(page)

        # --- Model selection ---
        model_group = Adw.PreferencesGroup(
            title="Model",
            description="Choose the default AI model for new conversations.",
        )
        page.add(model_group)

        self._model_row = Adw.ComboRow(title="Default Model")
        self._model_store = Gtk.StringList()

        # Populate from service if available
        models = []
        if self._service:
            models = self._service.models

        current_model = self._settings.get_string("default-model")
        selected_idx = 0

        # Always include an "(Auto)" option
        self._model_store.append("(Auto)")
        for i, m in enumerate(models):
            model_id = getattr(m, "id", str(m))
            self._model_store.append(model_id)
            if model_id == current_model:
                selected_idx = i + 1  # +1 because of "(Auto)"

        self._model_row.set_model(self._model_store)
        self._model_row.set_selected(selected_idx)
        self._model_row.connect("notify::selected", self._on_model_changed)
        model_group.add(self._model_row)

        # --- Streaming ---
        chat_group = Adw.PreferencesGroup(
            title="Chat",
            description="Configure chat behaviour.",
        )
        page.add(chat_group)

        self._streaming_switch = Adw.SwitchRow(
            title="Streaming Responses",
            subtitle="Show responses token-by-token as they arrive.",
        )
        self._streaming_switch.set_active(self._settings.get_boolean("streaming-enabled"))
        self._streaming_switch.connect("notify::active", self._on_streaming_changed)
        chat_group.add(self._streaming_switch)

        # --- System message ---
        self._system_msg_row = Adw.EntryRow(
            title="System Message",
        )
        self._system_msg_row.set_text(self._settings.get_string("system-message"))
        self._system_msg_row.connect("changed", self._on_system_message_changed)
        chat_group.add(self._system_msg_row)

    # ==================================================================
    # Authentication Page
    # ==================================================================

    def _build_auth_page(self) -> None:
        page = Adw.PreferencesPage(
            title="Authentication",
            icon_name="system-users-symbolic",
        )
        self.add(page)

        # --- Status ---
        status_group = Adw.PreferencesGroup(title="Status")
        page.add(status_group)

        self._auth_status_row = Adw.ActionRow(
            title="Authentication Method",
        )
        self._auth_status_icon = Gtk.Image.new_from_icon_name("emblem-ok-symbolic")
        self._auth_status_row.add_prefix(self._auth_status_icon)
        status_group.add(self._auth_status_row)
        self._update_auth_status()

        # --- Token management ---
        token_group = Adw.PreferencesGroup(
            title="Token Management",
            description="Manage your GitHub authentication token.",
        )
        page.add(token_group)

        # Token entry for adding
        self._pref_token_entry = Adw.PasswordEntryRow(title="GitHub Token")
        token_group.add(self._pref_token_entry)

        # Action buttons
        btn_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            halign=Gtk.Align.END,
            margin_top=8,
        )

        save_btn = Gtk.Button(label="Save Token")
        save_btn.add_css_class("suggested-action")
        save_btn.connect("clicked", self._on_save_token)
        btn_box.append(save_btn)

        remove_btn = Gtk.Button(label="Remove Token")
        remove_btn.add_css_class("destructive-action")
        remove_btn.connect("clicked", self._on_remove_token)
        btn_box.append(remove_btn)

        token_group.add(btn_box)

        # GitHub sign-in
        login_group = Adw.PreferencesGroup(
            title="GitHub Sign In",
            description="Sign in using your GitHub account via the browser.",
        )
        page.add(login_group)

        login_row = Adw.ActionRow(
            title="Sign in with GitHub",
            subtitle="Opens the GitHub device activation page.",
        )
        login_row.add_prefix(Gtk.Image.new_from_icon_name("web-browser-symbolic"))
        login_btn = Gtk.Button(label="Sign In")
        login_btn.set_valign(Gtk.Align.CENTER)
        login_btn.connect("clicked", self._on_github_login)
        login_row.add_suffix(login_btn)
        login_row.set_activatable_widget(login_btn)
        login_group.add(login_row)

        # Listen for auth changes
        self._auth_manager.connect("auth-changed", self._on_auth_changed)

    # ==================================================================
    # Advanced Page
    # ==================================================================

    def _build_advanced_page(self) -> None:
        page = Adw.PreferencesPage(
            title="Advanced",
            icon_name="applications-engineering-symbolic",
        )
        self.add(page)

        # --- CLI path ---
        cli_group = Adw.PreferencesGroup(
            title="Copilot CLI",
            description="Configure the Copilot CLI executable.",
        )
        page.add(cli_group)

        self._cli_path_row = Adw.EntryRow(title="CLI Path Override")
        self._cli_path_row.set_text(self._settings.get_string("cli-path"))
        self._cli_path_row.connect("changed", self._on_cli_path_changed)
        cli_group.add(self._cli_path_row)

        # --- Log level ---
        log_group = Adw.PreferencesGroup(
            title="Logging",
            description="Configure application logging.",
        )
        page.add(log_group)

        self._log_level_row = Adw.ComboRow(title="Log Level")
        log_levels = Gtk.StringList()
        for level in ("warning", "info", "debug", "error"):
            log_levels.append(level)
        self._log_level_row.set_model(log_levels)

        current_level = self._settings.get_string("log-level")
        level_map = {"warning": 0, "info": 1, "debug": 2, "error": 3}
        self._log_level_row.set_selected(level_map.get(current_level, 0))
        self._log_level_row.connect("notify::selected", self._on_log_level_changed)
        log_group.add(self._log_level_row)

        # --- BYOK (Bring Your Own Key) ---
        byok_group = Adw.PreferencesGroup(
            title="Custom Provider (BYOK)",
            description=(
                "Connect to a custom OpenAI-compatible API endpoint instead of GitHub Copilot."
            ),
        )
        page.add(byok_group)

        self._byok_enabled_switch = Adw.SwitchRow(
            title="Use Custom Provider",
            subtitle="Override the default Copilot backend.",
        )
        self._byok_enabled_switch.set_active(
            self._settings.get_boolean("byok-enabled") if self._has_key("byok-enabled") else False
        )
        self._byok_enabled_switch.connect("notify::active", self._on_byok_toggled)
        byok_group.add(self._byok_enabled_switch)

        self._byok_url_row = Adw.EntryRow(title="API Base URL")
        self._byok_url_row.set_text(
            self._settings.get_string("byok-base-url") if self._has_key("byok-base-url") else ""
        )
        self._byok_url_row.connect("changed", self._on_byok_url_changed)
        byok_group.add(self._byok_url_row)

        self._byok_key_row = Adw.PasswordEntryRow(title="API Key")
        byok_group.add(self._byok_key_row)

        self._byok_model_row = Adw.EntryRow(title="Model Name")
        self._byok_model_row.set_text(
            self._settings.get_string("byok-model") if self._has_key("byok-model") else ""
        )
        self._byok_model_row.connect("changed", self._on_byok_model_changed)
        byok_group.add(self._byok_model_row)

        save_byok_btn = Gtk.Button(label="Save BYOK Key")
        save_byok_btn.add_css_class("suggested-action")
        save_byok_btn.set_halign(Gtk.Align.END)
        save_byok_btn.set_margin_top(8)
        save_byok_btn.connect("clicked", self._on_save_byok_key)
        byok_group.add(save_byok_btn)

        # Enable/disable BYOK fields
        self._update_byok_sensitivity()

    # ==================================================================
    # GSettings helpers
    # ==================================================================

    def _has_key(self, key: str) -> bool:
        """Check whether the GSettings schema has a given key."""
        schema = self._settings.get_property("settings-schema")
        return schema.has_key(key) if schema else False

    # ==================================================================
    # General page handlers
    # ==================================================================

    def _on_model_changed(self, row: Adw.ComboRow, _pspec: Any) -> None:
        idx = row.get_selected()
        if idx == 0:
            self._settings.set_string("default-model", "")
        else:
            item = self._model_store.get_string(idx)
            if item:
                self._settings.set_string("default-model", item)

    def _on_streaming_changed(self, switch: Adw.SwitchRow, _pspec: Any) -> None:
        self._settings.set_boolean("streaming-enabled", switch.get_active())

    def _on_system_message_changed(self, row: Adw.EntryRow) -> None:
        self._settings.set_string("system-message", row.get_text())

    # ==================================================================
    # Auth page handlers
    # ==================================================================

    def _update_auth_status(self) -> None:
        method = self._auth_manager.method
        login = self._auth_manager.login

        if self._auth_manager.is_authenticated:
            login_str = f" ({login})" if login else ""
            self._auth_status_row.set_subtitle(f"{method.value}{login_str}")
            self._auth_status_icon.set_from_icon_name("emblem-ok-symbolic")
        else:
            self._auth_status_row.set_subtitle("Not authenticated")
            self._auth_status_icon.set_from_icon_name("dialog-warning-symbolic")

    def _on_auth_changed(self, _mgr: Any, method: str, is_auth: bool) -> None:
        self._update_auth_status()

    def _on_save_token(self, _btn: Gtk.Button) -> None:
        token = self._pref_token_entry.get_text().strip()
        if not token:
            self._pref_token_entry.add_css_class("error")
            return
        self._pref_token_entry.remove_css_class("error")
        success = self._auth_manager.store_token(token)
        if success:
            self._pref_token_entry.set_text("")
            self.add_toast(Adw.Toast(title="Token saved to Keyring"))
        else:
            self.add_toast(Adw.Toast(title="Failed to save token — is Keyring available?"))

    def _on_remove_token(self, _btn: Gtk.Button) -> None:
        removed = self._auth_manager.delete_token()
        if removed:
            self.add_toast(Adw.Toast(title="Token removed"))
        else:
            self.add_toast(Adw.Toast(title="No token to remove"))

    def _on_github_login(self, _btn: Gtk.Button) -> None:
        try:
            Gio.AppInfo.launch_default_for_uri("https://github.com/login/device", None)
        except Exception:
            log.exception("Failed to open browser")

    # ==================================================================
    # Advanced page handlers
    # ==================================================================

    def _on_cli_path_changed(self, row: Adw.EntryRow) -> None:
        self._settings.set_string("cli-path", row.get_text())

    def _on_log_level_changed(self, row: Adw.ComboRow, _pspec: Any) -> None:
        idx = row.get_selected()
        levels = ["warning", "info", "debug", "error"]
        if 0 <= idx < len(levels):
            self._settings.set_string("log-level", levels[idx])

    def _on_byok_toggled(self, switch: Adw.SwitchRow, _pspec: Any) -> None:
        if self._has_key("byok-enabled"):
            self._settings.set_boolean("byok-enabled", switch.get_active())
        self._update_byok_sensitivity()

    def _on_byok_url_changed(self, row: Adw.EntryRow) -> None:
        if self._has_key("byok-base-url"):
            self._settings.set_string("byok-base-url", row.get_text())

    def _on_byok_model_changed(self, row: Adw.EntryRow) -> None:
        if self._has_key("byok-model"):
            self._settings.set_string("byok-model", row.get_text())

    def _on_save_byok_key(self, _btn: Gtk.Button) -> None:
        """Save the BYOK API key to the Keyring."""
        key = self._byok_key_row.get_text().strip()
        if not key:
            self._byok_key_row.add_css_class("error")
            return
        self._byok_key_row.remove_css_class("error")

        # Store under a different schema attribute
        from ..backend.auth_manager import _SECRET_AVAILABLE

        if _SECRET_AVAILABLE:
            gi.require_version("Secret", "1")
            from gi.repository import Secret

            schema = Secret.Schema.new(
                "io.github.ieshaan.CopilotGTK.Token",
                Secret.SchemaFlags.NONE,
                {"type": Secret.SchemaAttributeType.STRING},
            )
            success = Secret.password_store_sync(
                schema,
                {"type": "byok_api_key"},
                Secret.COLLECTION_DEFAULT,
                "Copilot for GNOME — BYOK API Key",
                key,
                None,
            )
            if success:
                self._byok_key_row.set_text("")
                self.add_toast(Adw.Toast(title="BYOK API key saved"))
            else:
                self.add_toast(Adw.Toast(title="Failed to save BYOK key"))
        else:
            self.add_toast(Adw.Toast(title="Keyring unavailable — cannot store key"))

    def _update_byok_sensitivity(self) -> None:
        """Enable/disable BYOK fields based on toggle state."""
        active = self._byok_enabled_switch.get_active()
        self._byok_url_row.set_sensitive(active)
        self._byok_key_row.set_sensitive(active)
        self._byok_model_row.set_sensitive(active)
