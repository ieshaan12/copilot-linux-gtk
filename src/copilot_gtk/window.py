# SPDX-License-Identifier: GPL-3.0-or-later
"""CopilotWindow — Main application window with sidebar + chat split view."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Adw, Gio, GLib, GObject, Gtk  # noqa: E402

if TYPE_CHECKING:
    from .backend import CopilotService

from .widgets.chat_input import ChatInput  # noqa: E402
from .widgets.chat_view import ChatView  # noqa: E402
from .widgets.conversation_list import ConversationList  # noqa: E402

log = logging.getLogger(__name__)


class CopilotWindow(Adw.ApplicationWindow):
    """The main application window.

    Uses :class:`Adw.NavigationSplitView` to present a sidebar
    (conversation list) on the left and the chat view on the right.
    """

    __gtype_name__ = "CopilotWindow"

    def __init__(
        self,
        service: CopilotService,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._service = service
        self._current_session_id: str | None = None

        self.set_default_size(1000, 700)
        self.set_title("Copilot for GNOME")

        # --- Toast overlay (wraps everything for transient notifications) ---
        self._toast_overlay = Adw.ToastOverlay()
        self.set_content(self._toast_overlay)

        # --- Navigation split view ---
        self._split_view = Adw.NavigationSplitView()
        self._split_view.set_min_sidebar_width(260)
        self._split_view.set_max_sidebar_width(360)
        self._toast_overlay.set_child(self._split_view)

        # ---- Sidebar pane ----
        self._build_sidebar()

        # ---- Content pane ----
        self._build_content()

        # --- Wire up service signals ---
        self._connect_service_signals()

        # --- Actions ---
        self._setup_actions()

    # ------------------------------------------------------------------
    # Sidebar
    # ------------------------------------------------------------------

    def _build_sidebar(self) -> None:
        """Build the sidebar navigation page."""
        sidebar_page = Adw.NavigationPage(title="Conversations")
        sidebar_toolbar = Adw.ToolbarView()
        sidebar_page.set_child(sidebar_toolbar)

        # Header bar with "New Chat" button
        sidebar_header = Adw.HeaderBar()
        new_chat_btn = Gtk.Button(icon_name="list-add-symbolic")
        new_chat_btn.set_tooltip_text("New Chat (Ctrl+N)")
        new_chat_btn.add_css_class("flat")
        new_chat_btn.set_action_name("win.new-chat")
        sidebar_header.pack_start(new_chat_btn)
        sidebar_toolbar.add_top_bar(sidebar_header)

        # Conversation list
        self._conversation_list = ConversationList()
        self._conversation_list.connect(
            "conversation-selected", self._on_conversation_selected
        )
        self._conversation_list.connect(
            "conversation-delete-requested", self._on_conversation_delete_requested
        )
        sidebar_toolbar.set_content(self._conversation_list)

        self._split_view.set_sidebar(sidebar_page)

    # ------------------------------------------------------------------
    # Content
    # ------------------------------------------------------------------

    def _build_content(self) -> None:
        """Build the content (chat) navigation page."""
        self._content_page = Adw.NavigationPage(title="Chat")
        content_toolbar = Adw.ToolbarView()
        self._content_page.set_child(content_toolbar)

        # Header bar with hamburger menu
        content_header = Adw.HeaderBar()

        # Hamburger menu
        menu_btn = Gtk.MenuButton(icon_name="open-menu-symbolic")
        menu_btn.set_tooltip_text("Main Menu")
        menu_btn.add_css_class("flat")
        menu_btn.set_menu_model(self._build_menu_model())
        content_header.pack_end(menu_btn)

        content_toolbar.add_top_bar(content_header)

        # Stack: empty state vs chat
        self._content_stack = Gtk.Stack()
        self._content_stack.set_transition_type(
            Gtk.StackTransitionType.CROSSFADE
        )
        content_toolbar.set_content(self._content_stack)

        # Empty state
        empty_page = Adw.StatusPage()
        empty_page.set_title("Copilot for GNOME")
        empty_page.set_description("Start a new conversation to get going")
        empty_page.set_icon_name("io.github.ieshaan.CopilotGTK-symbolic")

        new_chat_action_btn = Gtk.Button(label="New Chat")
        new_chat_action_btn.add_css_class("pill")
        new_chat_action_btn.add_css_class("suggested-action")
        new_chat_action_btn.set_action_name("win.new-chat")
        new_chat_action_btn.set_halign(Gtk.Align.CENTER)
        empty_page.set_child(new_chat_action_btn)

        self._content_stack.add_named(empty_page, "empty")

        # Chat area (chat_view + input)
        chat_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        self._chat_view = ChatView()
        chat_box.append(self._chat_view)

        self._chat_input = ChatInput()
        self._chat_input.connect("message-submitted", self._on_message_submitted)
        self._chat_input.connect("stop-requested", self._on_stop_requested)
        chat_box.append(self._chat_input)

        self._content_stack.add_named(chat_box, "chat")

        # Start with empty state
        self._content_stack.set_visible_child_name("empty")

        self._split_view.set_content(self._content_page)

    # ------------------------------------------------------------------
    # Menu model
    # ------------------------------------------------------------------

    def _build_menu_model(self) -> Gio.Menu:
        """Build the hamburger menu model."""
        menu = Gio.Menu()
        menu.append("Preferences", "app.preferences")
        menu.append("Keyboard Shortcuts", "win.show-help-overlay")
        menu.append("About Copilot for GNOME", "app.about")
        return menu

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _setup_actions(self) -> None:
        """Register window-level GActions."""
        new_chat_action = Gio.SimpleAction(name="new-chat")
        new_chat_action.connect("activate", self._on_new_chat_action)
        self.add_action(new_chat_action)

    # ------------------------------------------------------------------
    # Service signal handlers
    # ------------------------------------------------------------------

    def _connect_service_signals(self) -> None:
        """Connect to CopilotService GObject signals."""
        self._service.connect("response-chunk", self._on_response_chunk)
        self._service.connect("response-complete", self._on_response_complete)
        self._service.connect("session-idle", self._on_session_idle)
        self._service.connect(
            "session-title-changed", self._on_session_title_changed
        )
        self._service.connect("turn-start", self._on_turn_start)
        self._service.connect("turn-end", self._on_turn_end)
        self._service.connect("error", self._on_service_error)
        self._service.connect("models-loaded", self._on_models_loaded)

    def _on_response_chunk(
        self, _service: CopilotService, session_id: str, delta: str
    ) -> None:
        if session_id == self._current_session_id:
            self._chat_view.append_streaming_delta(delta)

    def _on_response_complete(
        self, _service: CopilotService, session_id: str, content: str
    ) -> None:
        if session_id == self._current_session_id:
            self._chat_view.finish_streaming()

    def _on_session_idle(
        self, _service: CopilotService, session_id: str
    ) -> None:
        # If this is from a newly created conversation, select it
        conv = self._service.conversations.get(session_id)
        if conv is None:
            return

        # Add to sidebar if not already there
        if not self._conversation_list.has_conversation(session_id):
            self._conversation_list.add_conversation(conv)
            self._select_conversation(session_id)

        if session_id == self._current_session_id:
            self._chat_input.set_loading(False)

    def _on_session_title_changed(
        self, _service: CopilotService, session_id: str, title: str
    ) -> None:
        self._conversation_list.update_title(session_id, title)

    def _on_turn_start(
        self, _service: CopilotService, session_id: str
    ) -> None:
        if session_id == self._current_session_id:
            self._chat_input.set_loading(True)

    def _on_turn_end(
        self, _service: CopilotService, session_id: str
    ) -> None:
        if session_id == self._current_session_id:
            self._chat_input.set_loading(False)

    def _on_service_error(
        self, _service: CopilotService, message: str
    ) -> None:
        toast = Adw.Toast(title=message, timeout=5)
        self._toast_overlay.add_toast(toast)
        self._chat_input.set_loading(False)
        log.error("Service error: %s", message)

    def _on_models_loaded(
        self, _service: CopilotService, models: object
    ) -> None:
        """Store loaded models for the new-chat dialog."""
        pass  # models are cached on the service; dialog reads from there

    # ------------------------------------------------------------------
    # User interactions
    # ------------------------------------------------------------------

    def _on_new_chat_action(
        self, _action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        """Handle "New Chat" action — show model selection dialog."""
        self._show_new_chat_dialog()

    def _show_new_chat_dialog(self) -> None:
        """Present a dialog to select a model and start a new conversation."""
        models = self._service.models

        if not models:
            # No models cached yet — just create with default
            self._service.create_conversation()
            return

        dialog = Adw.AlertDialog()
        dialog.set_heading("New Chat")
        dialog.set_body("Select a model for this conversation:")

        # Build a list of model choices
        group = Adw.PreferencesGroup()
        model_rows: list[tuple[Adw.ActionRow, str]] = []

        check_group: Gtk.CheckButton | None = None

        for m in models:
            model_id = getattr(m, "id", str(m))
            model_name = getattr(m, "name", model_id)

            row = Adw.ActionRow(title=model_name, subtitle=model_id)
            check = Gtk.CheckButton()
            if check_group is None:
                check_group = check
                check.set_active(True)
            else:
                check.set_group(check_group)
            row.add_prefix(check)
            row.set_activatable_widget(check)
            group.add(row)
            model_rows.append((row, model_id))

        dialog.set_extra_child(group)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("create", "Create")
        dialog.set_response_appearance(
            "create", Adw.ResponseAppearance.SUGGESTED
        )
        dialog.set_default_response("create")
        dialog.set_close_response("cancel")

        def on_response(d: Adw.AlertDialog, response: str) -> None:
            if response != "create":
                return
            selected_model = ""
            for row, mid in model_rows:
                check_btn = row.get_activatable_widget()
                if check_btn is not None and check_btn.get_active():
                    selected_model = mid
                    break
            self._service.create_conversation(selected_model)

        dialog.connect("response", on_response)
        dialog.present(self)

    def _on_message_submitted(self, _input: ChatInput, text: str) -> None:
        """Handle a user message submission."""
        if not self._current_session_id:
            return
        # Display user bubble immediately
        self._chat_view.add_user_message(text)
        # Add assistant placeholder
        self._chat_view.add_assistant_placeholder()
        # Send to backend
        self._service.send_message(self._current_session_id, text)
        self._chat_input.set_loading(True)

    def _on_stop_requested(self, _input: ChatInput) -> None:
        """Handle stop-generation request."""
        if self._current_session_id:
            self._service.abort_session(self._current_session_id)
            self._chat_input.set_loading(False)

    def _on_conversation_selected(
        self,
        _list: ConversationList,
        session_id: str,
    ) -> None:
        """Switch to a selected conversation."""
        self._select_conversation(session_id)

    def _on_conversation_delete_requested(
        self,
        _list: ConversationList,
        session_id: str,
    ) -> None:
        """Delete a conversation after confirmation."""
        dialog = Adw.AlertDialog()
        dialog.set_heading("Delete Conversation?")
        dialog.set_body("This conversation will be permanently removed.")
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("delete", "Delete")
        dialog.set_response_appearance(
            "delete", Adw.ResponseAppearance.DESTRUCTIVE
        )
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")

        def on_response(d: Adw.AlertDialog, response: str) -> None:
            if response != "delete":
                return
            self._service.destroy_conversation(session_id)
            self._conversation_list.remove_conversation(session_id)
            if self._current_session_id == session_id:
                self._current_session_id = None
                self._chat_view.clear()
                self._content_stack.set_visible_child_name("empty")

        dialog.connect("response", on_response)
        dialog.present(self)

    def _select_conversation(self, session_id: str) -> None:
        """Switch the chat view to the given conversation."""
        self._current_session_id = session_id
        conv = self._service.conversations.get(session_id)
        if conv is None:
            return

        self._content_page.set_title(conv.title)
        self._chat_view.load_conversation(conv)
        self._content_stack.set_visible_child_name("chat")
        self._chat_input.set_loading(False)
        self._chat_input.grab_focus_input()

        # Collapse sidebar on narrow layout
        self._split_view.set_show_content(True)

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def show_toast(self, message: str, timeout: int = 3) -> None:
        """Show a transient toast notification."""
        toast = Adw.Toast(title=message, timeout=timeout)
        self._toast_overlay.add_toast(toast)
