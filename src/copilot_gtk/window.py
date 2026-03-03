# SPDX-License-Identifier: GPL-3.0-or-later
"""CopilotWindow — Main application window with sidebar + chat split view."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, GObject, Gtk  # noqa: E402

if TYPE_CHECKING:
    from .backend import CopilotService
    from .backend.auth_manager import AuthManager
    from .backend.conversation_store import ConversationStore

from .backend.conversation import Conversation  # noqa: E402
from .backend.message import Message, MessageRole  # noqa: E402
from .widgets.chat_input import ChatInput  # noqa: E402
from .widgets.chat_view import ChatView  # noqa: E402
from .widgets.conversation_list import ConversationList  # noqa: E402
from .widgets.shortcuts_window import build_shortcuts_window  # noqa: E402

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
        auth_manager: AuthManager | None = None,
        settings: Gio.Settings | None = None,
        store: ConversationStore | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._service = service
        self._auth_manager = auth_manager
        self._settings = settings
        self._store = store
        self._current_session_id: str | None = None

        self.set_default_size(1000, 700)
        self.set_title("Copilot for GNOME")

        # Keyboard-shortcuts help overlay (F1 / menu item)
        self._shortcuts_window = build_shortcuts_window()
        self._shortcuts_window.set_transient_for(self)
        self._shortcuts_window.set_modal(True)

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

        # --- Load persisted conversations into sidebar ---
        self._load_persisted_conversations()

    # ------------------------------------------------------------------
    # Sidebar
    # ------------------------------------------------------------------

    def _build_sidebar(self) -> None:
        """Build the sidebar navigation page."""
        sidebar_page = Adw.NavigationPage(title="Conversations")
        sidebar_toolbar = Adw.ToolbarView()
        sidebar_page.set_child(sidebar_toolbar)

        # Header bar with "New Chat" button and search toggle
        sidebar_header = Adw.HeaderBar()
        new_chat_btn = Gtk.Button(icon_name="list-add-symbolic")
        new_chat_btn.set_tooltip_text("New Chat (Ctrl+N)")
        new_chat_btn.add_css_class("flat")
        new_chat_btn.set_action_name("win.new-chat")
        new_chat_btn.update_property(
            [Gtk.AccessibleProperty.LABEL],
            ["New Chat"],
        )
        sidebar_header.pack_start(new_chat_btn)

        # Search toggle button
        self._search_button = Gtk.ToggleButton(icon_name="system-search-symbolic")
        self._search_button.set_tooltip_text("Search Conversations (Ctrl+K)")
        self._search_button.add_css_class("flat")
        self._search_button.update_property(
            [Gtk.AccessibleProperty.LABEL],
            ["Search Conversations"],
        )
        sidebar_header.pack_end(self._search_button)

        sidebar_toolbar.add_top_bar(sidebar_header)

        # Search bar
        self._search_bar = Gtk.SearchBar()
        self._search_bar.set_show_close_button(True)
        self._search_entry = Gtk.SearchEntry()
        self._search_entry.set_placeholder_text("Search conversations…")
        self._search_entry.set_hexpand(True)
        self._search_bar.set_child(self._search_entry)
        self._search_bar.connect_entry(self._search_entry)
        self._search_button.bind_property(
            "active",
            self._search_bar,
            "search-mode-enabled",
            GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE,
        )
        self._search_entry.connect("search-changed", self._on_search_changed)
        sidebar_toolbar.add_top_bar(self._search_bar)

        # Conversation list
        self._conversation_list = ConversationList()
        self._conversation_list.connect("conversation-selected", self._on_conversation_selected)
        self._conversation_list.connect(
            "conversation-delete-requested", self._on_conversation_delete_requested
        )
        self._conversation_list.connect(
            "conversation-rename-requested", self._on_conversation_rename_requested
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
        menu_btn.update_property(
            [Gtk.AccessibleProperty.LABEL],
            ["Main Menu"],
        )
        content_header.pack_end(menu_btn)

        content_toolbar.add_top_bar(content_header)

        # Stack: empty state vs chat
        self._content_stack = Gtk.Stack()
        self._content_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
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

        # Startup loading state (TASK-055)
        loading_page = Adw.StatusPage()
        loading_page.set_title("Starting Copilot…")
        loading_page.set_description("Initializing the Copilot SDK")
        loading_spinner = Adw.Spinner() if hasattr(Adw, "Spinner") else Gtk.Spinner(spinning=True)
        loading_spinner.set_halign(Gtk.Align.CENTER)
        loading_spinner.set_size_request(32, 32)
        loading_page.set_child(loading_spinner)
        self._content_stack.add_named(loading_page, "loading")

        # Fatal error state (TASK-056)
        self._error_page = Adw.StatusPage()
        self._error_page.set_icon_name("dialog-error-symbolic")
        self._error_page.set_title("Copilot CLI Not Found")
        self._error_page.set_description(
            "Install GitHub Copilot CLI or set the CLI path in Preferences."
        )
        self._content_stack.add_named(self._error_page, "error")

        # Chat area (chat_view + input)
        chat_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        self._chat_view = ChatView()
        chat_box.append(self._chat_view)

        self._chat_input = ChatInput()
        self._chat_input.connect("message-submitted", self._on_message_submitted)
        self._chat_input.connect("stop-requested", self._on_stop_requested)
        chat_box.append(self._chat_input)

        self._content_stack.add_named(chat_box, "chat")

        # Start with loading state (replaced by empty/chat when SDK is ready)
        self._content_stack.set_visible_child_name("loading")

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
        self._new_chat_action = Gio.SimpleAction(name="new-chat")
        self._new_chat_action.connect("activate", self._on_new_chat_action)
        self._new_chat_action.set_enabled(False)  # disabled until SDK ready
        self.add_action(self._new_chat_action)

        search_action = Gio.SimpleAction(name="search-conversations")
        search_action.connect("activate", self._on_search_action)
        self.add_action(search_action)

        close_action = Gio.SimpleAction(name="close-conversation")
        close_action.connect("activate", self._on_close_conversation_action)
        self.add_action(close_action)

        escape_action = Gio.SimpleAction(name="escape-pressed")
        escape_action.connect("activate", self._on_escape_action)
        self.add_action(escape_action)

        help_action = Gio.SimpleAction(name="show-help-overlay")
        help_action.connect("activate", self._on_show_help_overlay)
        self.add_action(help_action)

    # ------------------------------------------------------------------
    # Service signal handlers
    # ------------------------------------------------------------------

    def _connect_service_signals(self) -> None:
        """Connect to CopilotService GObject signals."""
        self._service.connect("ready", self._on_service_ready)
        self._service.connect("response-chunk", self._on_response_chunk)
        self._service.connect("response-complete", self._on_response_complete)
        self._service.connect("session-idle", self._on_session_idle)
        self._service.connect("session-title-changed", self._on_session_title_changed)
        self._service.connect("turn-start", self._on_turn_start)
        self._service.connect("turn-end", self._on_turn_end)
        self._service.connect("error", self._on_service_error)
        self._service.connect("models-loaded", self._on_models_loaded)

    def _on_service_ready(
        self,
        _service: CopilotService,
    ) -> None:
        """Enable the New Chat button as soon as the SDK is ready."""
        self._new_chat_action.set_enabled(True)
        # Hide startup loading state if visible
        if self._content_stack.get_visible_child_name() == "loading":
            self._content_stack.set_visible_child_name("empty")

    def _on_response_chunk(self, _service: CopilotService, session_id: str, delta: str) -> None:
        if session_id == self._current_session_id:
            self._chat_view.append_streaming_delta(delta)

    def _on_response_complete(
        self, _service: CopilotService, session_id: str, content: str
    ) -> None:
        if session_id == self._current_session_id:
            self._chat_view.finish_streaming()

        # --- Auto-title generation (TASK-046) ---
        conv = self._service.conversations.get(session_id)
        if conv is not None and conv.title == "New Chat" and content:
            # Use the first user message as title source (first ~50 chars)
            first_user_msg = None
            for msg in conv.messages:
                if msg.role == MessageRole.USER:
                    first_user_msg = msg
                    break
            if first_user_msg:
                auto_title = first_user_msg.content[:50].strip()
                if len(first_user_msg.content) > 50:
                    auto_title += "…"
                conv.title = auto_title
                self._conversation_list.update_title(session_id, auto_title)
                if session_id == self._current_session_id:
                    self._content_page.set_title(auto_title)

        # --- Persist conversation + messages (TASK-045) ---
        if conv is not None and self._store is not None:
            self._store.save_conversation(conv)
            self._store.save_messages(session_id, conv.messages)

    def _on_session_idle(self, _service: CopilotService, session_id: str) -> None:
        # If this is from a newly created conversation, select it
        conv = self._service.conversations.get(session_id)
        if conv is None:
            return

        # Add to sidebar if not already there
        if not self._conversation_list.has_conversation(session_id):
            self._conversation_list.add_conversation(conv)
            self._select_conversation(session_id)

            # Persist the new conversation to the store
            if self._store is not None:
                self._store.save_conversation(conv)

        if session_id == self._current_session_id:
            self._chat_input.set_loading(False)

    def _on_session_title_changed(
        self, _service: CopilotService, session_id: str, title: str
    ) -> None:
        self._conversation_list.update_title(session_id, title)
        if session_id == self._current_session_id:
            self._content_page.set_title(title)
        # Persist title change
        if self._store is not None:
            self._store.update_title(session_id, title)

    def _on_turn_start(self, _service: CopilotService, session_id: str) -> None:
        if session_id == self._current_session_id:
            self._chat_input.set_loading(True)

    def _on_turn_end(self, _service: CopilotService, session_id: str) -> None:
        if session_id == self._current_session_id:
            self._chat_input.set_loading(False)

    def _on_service_error(self, _service: CopilotService, message: str) -> None:
        # Fatal errors: show a full-pane StatusPage
        fatal_keywords = ("not found", "cli not found", "no such file", "enoent")
        if any(kw in message.lower() for kw in fatal_keywords):
            self._show_fatal_error(message)
        else:
            toast = Adw.Toast(title=message, timeout=5)
            self._toast_overlay.add_toast(toast)
        self._chat_input.set_loading(False)
        log.error("Service error: %s", message)

    def _on_models_loaded(self, _service: CopilotService, models: object) -> None:
        """Store loaded models for the new-chat dialog."""
        # Enable New Chat now that we have models
        self._new_chat_action.set_enabled(True)

    # ------------------------------------------------------------------
    # User interactions
    # ------------------------------------------------------------------

    def _on_new_chat_action(self, _action: Gio.SimpleAction, _param: GLib.Variant | None) -> None:
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
        dialog.set_response_appearance("create", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("create")
        dialog.set_close_response("cancel")

        def on_response(d: Adw.AlertDialog, response: str) -> None:
            if response != "create":
                return
            selected_model = ""
            for row, mid in model_rows:
                check_btn = row.get_activatable_widget()
                if check_btn is not None and check_btn.get_active():  # type: ignore[attr-defined]
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

        # Persist messages after sending
        if self._store is not None:
            conv = self._service.conversations.get(self._current_session_id)
            if conv is not None:
                self._store.save_messages(self._current_session_id, conv.messages)
                self._store.update_timestamp(self._current_session_id)

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
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")

        def on_response(d: Adw.AlertDialog, response: str) -> None:
            if response != "delete":
                return
            self._service.destroy_conversation(session_id)
            self._conversation_list.remove_conversation(session_id)
            # Remove from persistent store
            if self._store is not None:
                self._store.delete_conversation(session_id)
            if self._current_session_id == session_id:
                self._current_session_id = None
                self._chat_view.clear()
                self._content_stack.set_visible_child_name("empty")

        dialog.connect("response", on_response)
        dialog.present(self)

    def _on_conversation_rename_requested(
        self,
        _list: ConversationList,
        session_id: str,
    ) -> None:
        """Show a rename dialog for the conversation (TASK-048)."""
        conv = self._service.conversations.get(session_id)
        current_title = conv.title if conv else "New Chat"

        dialog = Adw.AlertDialog()
        dialog.set_heading("Rename Conversation")
        dialog.set_body("Enter a new title:")

        entry = Gtk.Entry()
        entry.set_text(current_title)
        entry.set_activates_default(True)
        dialog.set_extra_child(entry)

        dialog.add_response("cancel", "Cancel")
        dialog.add_response("rename", "Rename")
        dialog.set_response_appearance("rename", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("rename")
        dialog.set_close_response("cancel")

        def on_response(d: Adw.AlertDialog, response: str) -> None:
            if response != "rename":
                return
            new_title = entry.get_text().strip()
            if not new_title:
                return
            # Update in-memory model
            if conv is not None:
                conv.title = new_title
            # Update sidebar
            self._conversation_list.update_title(session_id, new_title)
            # Update content header if this is the active conversation
            if session_id == self._current_session_id:
                self._content_page.set_title(new_title)
            # Persist
            if self._store is not None:
                self._store.update_title(session_id, new_title)

        dialog.connect("response", on_response)
        dialog.present(self)

    def _on_search_action(self, _action: Gio.SimpleAction, _param: GLib.Variant | None) -> None:
        """Toggle the search bar (Ctrl+K)."""
        self._search_button.set_active(not self._search_button.get_active())
        if self._search_button.get_active():
            self._search_entry.grab_focus()

    def _on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        """Filter the conversation list as the user types."""
        query = entry.get_text()
        self._conversation_list.filter_by_title(query)

    def _on_close_conversation_action(
        self, _action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        """Close the current conversation (Ctrl+W) — return to empty state."""
        if self._current_session_id is None:
            return
        self._current_session_id = None
        self._chat_view.clear()
        self._content_stack.set_visible_child_name("empty")
        self._content_page.set_title("Chat")
        self._conversation_list.deselect_all()

    def _on_escape_action(self, _action: Gio.SimpleAction, _param: GLib.Variant | None) -> None:
        """Handle Escape: close search bar, or stop generation if streaming."""
        if self._search_button.get_active():
            self._search_button.set_active(False)
            return
        if self._chat_input._is_loading and self._current_session_id:
            self._service.abort_session(self._current_session_id)
            self._chat_input.set_loading(False)

    def _show_fatal_error(self, message: str) -> None:
        """Show a fatal error StatusPage in the content area."""
        self._error_page.set_description(message)
        self._content_stack.set_visible_child_name("error")
        self._new_chat_action.set_enabled(False)

    def _on_show_help_overlay(self, _action: Gio.SimpleAction, _param: GLib.Variant | None) -> None:
        """Present the keyboard shortcuts window (F1)."""
        self._shortcuts_window.present()

    def _select_conversation(self, session_id: str) -> None:
        """Switch the chat view to the given conversation."""
        self._current_session_id = session_id
        conv = self._service.conversations.get(session_id)

        if conv is None:
            # This may be a persisted conversation not yet in CopilotService.
            # Load from store and create an in-memory Conversation object.
            if self._store is not None:
                conv = self._load_conversation_from_store(session_id)
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
    # Persistence helpers
    # ------------------------------------------------------------------

    def _load_persisted_conversations(self) -> None:
        """Load conversations from the store into the sidebar on startup."""
        if self._store is None:
            return
        for conv_data in self._store.list_conversations():
            conv = Conversation.from_dict(conv_data)
            # Load messages from store so they're available in memory
            msg_dicts = self._store.load_messages(conv.session_id)
            for md in msg_dicts:
                conv.messages.append(Message.from_dict(md))
            # Register in service's in-memory map (no SDK session yet)
            self._service._conversations[conv.session_id] = conv
            self._conversation_list.add_conversation(conv)

    def _load_conversation_from_store(self, session_id: str) -> Conversation | None:
        """Load a single conversation + messages from the store into memory."""
        if self._store is None:
            return None
        conv_data = self._store.get_conversation(session_id)
        if conv_data is None:
            return None
        conv = Conversation.from_dict(conv_data)
        msg_dicts = self._store.load_messages(session_id)
        for md in msg_dicts:
            conv.messages.append(Message.from_dict(md))
        # Register in service's in-memory map
        self._service._conversations[session_id] = conv
        return conv

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def show_toast(self, message: str, timeout: int = 3) -> None:
        """Show a transient toast notification."""
        toast = Adw.Toast(title=message, timeout=timeout)
        self._toast_overlay.add_toast(toast)
