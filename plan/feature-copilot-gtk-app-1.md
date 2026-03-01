---
goal: Build a GNOME-native Linux Desktop App (GTK4 + Libadwaita) for interacting with GitHub Copilot via the copilot-sdk
version: 1.0
date_created: 2026-03-01
last_updated: 2026-03-01
owner: ieshaan
status: 'Planned'
tags: [feature, architecture, desktop-app, gtk, gnome, copilot-sdk]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

This plan describes the full implementation of **Copilot for GNOME** — a native Linux desktop application built with GTK4 and Libadwaita that provides a conversational AI interface powered by the GitHub Copilot SDK. The app will feel like a first-class GNOME citizen: adaptive layouts, dark/light mode, GNOME HIG-compliant, and distributable as a Flatpak.

---

## Technology Stack Evaluation

Before diving into the plan, the following options were evaluated for the frontend (GTK binding language) and backend (copilot-sdk language).

### Candidate Stacks

| Stack | GTK Binding | Copilot SDK | SDK Status | Verdict |
|-------|-------------|-------------|------------|---------|
| **Python + PyGObject** | PyGObject (GTK4 + Libadwaita) | `github-copilot-sdk` | **Official (1st party)** | **SELECTED** |
| Rust + gtk4-rs | gtk4-rs + libadwaita-rs | `copilot-sdk-rust` | Community (unofficial) | Runner-up |
| Go + gotk4 | gotk4 | `github.com/github/copilot-sdk/go` | Official | Rejected — gotk4 bindings less mature |
| C / Vala + GTK4 | Native | None | N/A | Rejected — no SDK, too low-level |
| TypeScript + GJS | GJS (GNOME JS) | `@github/copilot-sdk` | Official (Node.js only) | Rejected — GJS ≠ Node.js; npm packages incompatible |
| .NET + GTK | gir.core / GtkSharp | `GitHub.Copilot.SDK` | Official | Rejected — poor GNOME ecosystem fit |

### Decision: Python + PyGObject + GTK4 + Libadwaita

**Rationale:**

1. **First-party copilot-sdk** — `github-copilot-sdk` (Python) is officially maintained by GitHub. No risk of community SDK breakage or abandonment.
2. **Mature GTK4/Libadwaita bindings** — PyGObject is the most battle-tested binding for GTK4. Typing stubs available (`PyGObject-stubs`).
3. **Async alignment** — The copilot-sdk is `async/await`-native. Python's `asyncio` can be integrated with the GLib main loop via the `gbulb` library or manual `GLib.idle_add` bridging.
4. **GNOME ecosystem fit** — Many flagship GNOME apps are Python-based (Dialect, Apostrophe, Bottles, etc.). Excellent tooling with GNOME Builder.
5. **Rapid development** — Python enables fast iteration; ideal for a Technical Preview SDK.
6. **Flatpak solves distribution** — Python dependency management is handled cleanly inside Flatpak sandboxes.

**Why not Rust (runner-up)?** — While `gtk4-rs` is excellent and Rust offers performance/safety advantages, the copilot-sdk for Rust is community-maintained and explicitly labeled "use at your own risk." For an app whose primary value is the Copilot backend, an unofficial SDK introduces unacceptable risk. If the Rust SDK becomes official, a port would be viable in future.

---

## Architecture

```
┌──────────────────────────────────────────────┐
│            GTK4 + Libadwaita UI              │
│   (Adw.ApplicationWindow, NavigationSplit,   │
│    Chat View, Markdown Renderer, Settings)   │
├──────────────────────────────────────────────┤
│           Application Controller             │
│   (ConversationManager, EventDispatcher,     │
│    SettingsManager, AuthManager)              │
├──────────────────────────────────────────────┤
│          copilot-sdk (Python)                │
│   (CopilotClient → Sessions → Events)       │
├──────────────────────────────────────────────┤
│          Copilot CLI (JSON-RPC)              │
│   (Managed automatically by SDK, or          │
│    connect to external --headless server)     │
└──────────────────────────────────────────────┘
```

### Key Architectural Decisions

- **Async bridge**: Use `gbulb` (or a custom `GLib.MainLoop` ↔ `asyncio` bridge) so that copilot-sdk's `async` calls run on the GTK main loop without blocking the UI.
- **Event-driven**: The copilot-sdk emits events (`assistant.message_delta`, `session.idle`, etc.) — the UI subscribes and updates reactively.
- **Conversation persistence**: Leverage the SDK's built-in `infinite_sessions` workspace (`~/.copilot/session-state/`) for state; additionally persist conversation metadata (title, timestamp) locally in a JSON/SQLite store.
- **UI/Backend separation**: A thin `CopilotBackend` class wraps the SDK and exposes signals that GTK widgets connect to — the UI never touches `CopilotClient` directly.

---

## 1. Requirements & Constraints

- **REQ-001**: The application MUST be a native GNOME desktop app using GTK4 and Libadwaita.
- **REQ-002**: The application MUST use the official Python copilot-sdk (`github-copilot-sdk`) for all Copilot interactions.
- **REQ-003**: The application MUST support streaming responses displayed in real-time (token-by-token).
- **REQ-004**: The application MUST support multiple concurrent conversations with a sidebar/list view.
- **REQ-005**: The application MUST follow the GNOME Human Interface Guidelines (HIG).
- **REQ-006**: The application MUST support dark and light modes via Libadwaita.
- **REQ-007**: The application MUST render Markdown in assistant responses (headings, bold, italic, lists, code blocks).
- **REQ-008**: The application MUST support syntax-highlighted code blocks with a copy button.
- **REQ-009**: The application MUST allow model selection from available models (via `client.list_models()`).
- **REQ-010**: The application MUST support GitHub authentication (signed-in user, token env vars).
- **SEC-001**: API tokens and credentials MUST be stored securely using libsecret / GNOME Keyring.
- **SEC-002**: The application MUST NOT log or display raw API tokens in the UI.
- **CON-001**: Copilot CLI must be installed separately and available in `$PATH` (SDK prerequisite).
- **CON-002**: Python 3.11+ required (copilot-sdk minimum).
- **CON-003**: The copilot-sdk is in Technical Preview — API surface may change.
- **GUD-001**: Use GNOME Builder as the recommended IDE for development.
- **GUD-002**: Use Meson as the build system (standard for GNOME apps).
- **GUD-003**: Use Flatpak as the primary distribution format.
- **GUD-005**: Use `uv` as the Python package manager for dependency resolution, lockfile (`uv.lock`), and virtual environment management.
- **GUD-004**: Application ID should follow reverse-DNS: `io.github.ieshaan.CopilotGTK` (or similar).
- **PAT-001**: Follow GTK4 composite template pattern for all custom widgets.
- **PAT-002**: Use GObject properties and signals for data binding between backend and UI.
- **PAT-003**: Use `.ui` XML files for declarative UI layout where practical.

---

## 2. Implementation Steps

### Phase 1: Project Scaffolding & Build System

- GOAL-001: Set up the project structure, build system, and development environment so that a blank Libadwaita window can be built and launched.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Create project directory structure: `src/`, `data/`, `po/`, `build-aux/`, `tests/` | | |
| TASK-001a | Initialize `uv` project: `uv init`, configure `pyproject.toml` with project metadata, Python `>=3.11` requirement, and all runtime/dev dependencies. Generate `uv.lock` for deterministic builds | | |
| TASK-002 | Create `meson.build` (root) with project name `copilot-gtk`, Python dependency, i18n subdir | | |
| TASK-003 | Create `src/meson.build` to install Python sources and configure main entry point | | |
| TASK-004 | Create `src/main.py` — entry point that initializes `Adw.Application` and presents an empty `Adw.ApplicationWindow` | | |
| TASK-005 | Create `data/io.github.ieshaan.CopilotGTK.desktop.in` (desktop entry file) | | |
| TASK-006 | Create `data/io.github.ieshaan.CopilotGTK.metainfo.xml.in` (AppStream metadata) | | |
| TASK-007 | Create `data/io.github.ieshaan.CopilotGTK.gschema.xml` (GSettings schema for preferences) | | |
| TASK-008 | Create `data/icons/` with a placeholder SVG app icon | | |
| TASK-009 | Create `build-aux/io.github.ieshaan.CopilotGTK.Devel.json` (Flatpak manifest) with Python, PyGObject, Libadwaita, and `github-copilot-sdk` (use `uv export --format requirements-txt` for `flatpak-pip-generator` compatibility) | | |
| TASK-010 | Verify: `meson setup build && meson compile -C build && meson install -C build` produces a runnable app that shows an empty Adw window | | |

**Verification — Phase 1:**

| VER | Criterion | Command / Method | Pass Condition |
|-----|-----------|-----------------|----------------|
| VER-P1-001 | Directory structure exists | `ls src/ data/ po/ build-aux/ tests/` | All directories present, exit code 0 |
| VER-P1-002 | `uv` project initializes | `uv sync` | Virtual environment created, lockfile generated, zero errors |
| VER-P1-003 | Meson configures without errors | `meson setup build` | Exit code 0, no `ERROR` in output |
| VER-P1-004 | Meson compiles | `meson compile -C build` | Exit code 0 |
| VER-P1-005 | App launches and presents window | `meson install -C build && copilot-gtk` (or `python src/main.py`) | An empty `Adw.ApplicationWindow` renders on screen within 3 seconds, no Python traceback |
| VER-P1-006 | Desktop entry valid | `desktop-file-validate data/*.desktop.in` | Exit code 0 |
| VER-P1-007 | AppStream metadata valid | `appstreamcli validate data/*.metainfo.xml.in` | Exit code 0, no errors |
| VER-P1-008 | GSettings schema compiles | `glib-compile-schemas data/` | Exit code 0 |
| VER-P1-009 | Dependencies resolvable | `uv pip check` | No missing or conflicting dependencies |

### Phase 2: Copilot SDK Integration Layer

- GOAL-002: Build the backend wrapper that manages the CopilotClient lifecycle, sessions, and events, and bridge async to the GLib main loop.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-011 | Create `src/backend/async_bridge.py` — implement GLib↔asyncio event loop integration (use `gbulb` or custom `GLibEventLoopPolicy`) so `async` SDK calls run without blocking GTK | | |
| TASK-012 | Create `src/backend/copilot_service.py` — `CopilotService(GObject.Object)` class that wraps `CopilotClient`, exposes GObject signals: `response-chunk(str)`, `response-complete(str)`, `session-idle()`, `error(str)`, `models-loaded(list)` | | |
| TASK-013 | Implement `CopilotService.start()` — calls `await client.start()`, emits `ready` signal | | |
| TASK-014 | Implement `CopilotService.create_conversation(model: str)` — calls `client.create_session({"model": model, "streaming": True})`, stores session, connects event handlers | | |
| TASK-015 | Implement `CopilotService.send_message(conversation_id: str, prompt: str)` — calls `session.send({"prompt": prompt})`, bridges `assistant.message_delta` events to GObject signals | | |
| TASK-016 | Implement `CopilotService.list_models()` — calls `client.list_models()`, returns available model list | | |
| TASK-017 | Implement `CopilotService.stop()` — gracefully destroys all sessions and stops client | | |
| TASK-018 | Create `src/backend/conversation.py` — `Conversation` data class holding session_id, title, messages list, model, created_at | | |
| TASK-019 | Create `src/backend/message.py` — `Message` data class with role (user/assistant), content, timestamp, is_streaming flag | | |
| TASK-020 | Write unit tests for `CopilotService` with mocked `CopilotClient` | | |

**Verification — Phase 2:**

| VER | Criterion | Command / Method | Pass Condition |
|-----|-----------|-----------------|----------------|
| VER-P2-001 | Unit tests pass | `uv run pytest tests/test_copilot_service.py -v` | All tests pass, exit code 0 |
| VER-P2-002 | `CopilotService.start()` emits `ready` | Mock `CopilotClient.start()`, subscribe to `ready` signal, call `start()` | Signal received within 2 seconds |
| VER-P2-003 | Session creation succeeds | Call `create_conversation("gpt-5")` with mocked client | Returns valid `Conversation` object with `session_id`, `model == "gpt-5"` |
| VER-P2-004 | Streaming event bridge works | Mock `assistant.message_delta` events, verify `response-chunk` GObject signal fires on GTK main thread | Signal callback receives correct `delta_content` string, runs on main thread (`GLib.MainContext.default().is_owner()`) |
| VER-P2-005 | Session idle signal | Mock `session.idle` event | `session-idle` GObject signal emitted |
| VER-P2-006 | Error signal on SDK exception | Mock `CopilotClient` to raise an exception on `send()` | `error` GObject signal emitted with error message string |
| VER-P2-007 | Graceful stop | Call `stop()`, verify all sessions destroyed | `client.stop()` called, no `asyncio` warnings or leaked tasks |
| VER-P2-008 | Async bridge no-block | Schedule a 500ms async coroutine via bridge, verify GTK main loop remains responsive (process pending events during wait) | GTK widgets remain interactive; no freeze |

### Phase 3: Core UI — Main Window & Chat View

- GOAL-003: Build the main application window with a sidebar for conversations and a content area for the chat, following the GNOME HIG.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-021 | Create `src/window.py` + `src/window.ui` — `CopilotWindow(Adw.ApplicationWindow)` using `Adw.ToolbarView` with `Adw.HeaderBar` | | |
| TASK-022 | Add `Adw.NavigationSplitView` to window: sidebar (conversation list) + content (chat view) | | |
| TASK-023 | Create `src/widgets/conversation_row.py` + `.ui` — `ConversationRow(Adw.ActionRow)` for sidebar items showing title, model badge, timestamp | | |
| TASK-024 | Create `src/widgets/conversation_list.py` — `ConversationList(Gtk.ListBox)` managing the list of `ConversationRow` widgets, with "New Chat" button in header | | |
| TASK-025 | Create `src/widgets/chat_view.py` + `.ui` — `ChatView(Gtk.Box)` containing a `Gtk.ScrolledWindow` with message list + input area at bottom | | |
| TASK-026 | Create `src/widgets/message_bubble.py` + `.ui` — `MessageBubble(Gtk.Box)` widget that renders a single message with appropriate styling (user vs assistant), avatar icon, timestamp | | |
| TASK-027 | Create `src/widgets/chat_input.py` + `.ui` — `ChatInput(Gtk.Box)` with multi-line `Gtk.TextView`, send button (`Gtk.Button` with icon), Ctrl+Enter shortcut | | |
| TASK-028 | Implement message list population: when a conversation is selected, populate `ChatView` with `MessageBubble` widgets from conversation history | | |
| TASK-029 | Implement streaming display: connect `CopilotService.response-chunk` signal to update the last `MessageBubble` in real-time, auto-scroll to bottom | | |
| TASK-030 | Add `Adw.StatusPage` as empty state when no conversation is selected ("Start a new conversation") | | |
| TASK-031 | Implement "New Chat" action: prompt model selection via `Adw.ComboRow` in a dialog, then call `CopilotService.create_conversation()` | | |
| TASK-032 | Add app menu (hamburger) to `Adw.HeaderBar` with: Preferences, Keyboard Shortcuts, About | | |

**Verification — Phase 3:**

| VER | Criterion | Command / Method | Pass Condition |
|-----|-----------|-----------------|----------------|
| VER-P3-001 | Window renders with split layout | Launch app visually | `Adw.NavigationSplitView` visible with sidebar (left) and content (right) |
| VER-P3-002 | Empty state shown | Launch app with no conversations | `Adw.StatusPage` with "Start a new conversation" message visible in content area |
| VER-P3-003 | New Chat creates conversation | Click "New Chat" button → select model → confirm | New `ConversationRow` appears in sidebar, chat input area becomes active |
| VER-P3-004 | Message send displays user bubble | Type text in `ChatInput`, click send | `MessageBubble` with user styling and correct text appears in chat view |
| VER-P3-005 | Streaming response displays | Send message with mock backend enabled | Assistant `MessageBubble` updates incrementally; text grows token-by-token |
| VER-P3-006 | Auto-scroll on new content | Send long message that overflows viewport | `Gtk.ScrolledWindow` scrolls to bottom automatically |
| VER-P3-007 | Conversation switching | Create 2 conversations, click each in sidebar | Chat view swaps to show correct message history for selected conversation |
| VER-P3-008 | Hamburger menu items | Click hamburger button | Menu shows "Preferences", "Keyboard Shortcuts", "About" items |
| VER-P3-009 | No Python tracebacks | Run full interaction flow | `stderr` contains no `Traceback` strings |

### Phase 4: Markdown & Code Rendering

- GOAL-004: Render assistant responses as rich Markdown with syntax-highlighted code blocks and copy-to-clipboard functionality.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-033 | Evaluate Markdown rendering approach: (A) use `Pango` markup conversion from Markdown, (B) use `Gtk.TextView` with `Gtk.TextTag` styling, or (C) use `WebKitWebView` for HTML rendering. Recommended: **Option B** for native feel, with fallback to `GtkSourceView` for code blocks | | |
| TASK-034 | Create `src/widgets/markdown_renderer.py` — parser that converts Markdown AST (via `markdown-it-py` or `mistune` library) to `Gtk.TextBuffer` with `Gtk.TextTag` styles for headings, bold, italic, lists, inline code | | |
| TASK-035 | Create `src/widgets/code_block.py` + `.ui` — `CodeBlock(Gtk.Box)` widget using `GtkSourceView` with language-specific syntax highlighting, a copy button overlay, and language label | | |
| TASK-036 | Integrate `markdown_renderer` into `MessageBubble` — assistant messages flow through the renderer; user messages remain plain text | | |
| TASK-037 | Add CSS stylesheet `src/style.css` for message bubble styling: rounded corners, padding, distinct background colors for user/assistant, code block background, inline-code styling | | |
| TASK-038 | Test rendering with complex Markdown: nested lists, fenced code blocks with language hints, inline code, bold/italic, links, blockquotes | | |

**Verification — Phase 4:**

| VER | Criterion | Command / Method | Pass Condition |
|-----|-----------|-----------------|----------------|
| VER-P4-001 | Heading renders large | Feed `# Hello` to `MarkdownRenderer` | `Gtk.TextTag` with `scale > 1.0` applied to "Hello" in `TextBuffer` |
| VER-P4-002 | Bold renders bold | Feed `**bold**` | `Gtk.TextTag` with `weight = Pango.Weight.BOLD` applied |
| VER-P4-003 | Inline code uses monospace | Feed `` `code` `` | `Gtk.TextTag` with `family = "monospace"` applied |
| VER-P4-004 | Fenced code block renders | Feed `` ```python\nprint("hi")\n``` `` | `GtkSourceView` widget created with Python syntax highlighting |
| VER-P4-005 | Code copy button works | Click copy button on code block | Clipboard (`Gdk.Clipboard`) contains the code block text |
| VER-P4-006 | Nested list indentation | Feed `- A\n  - B\n    - C` | Three levels of indentation visible in `TextBuffer` |
| VER-P4-007 | Links are clickable | Feed `[link](https://example.com)` | Blue underlined text; clicking opens URL via `Gtk.UriLauncher` |
| VER-P4-008 | Markdown unit tests pass | `uv run pytest tests/test_markdown_renderer.py -v` | All tests pass, exit code 0 |
| VER-P4-009 | CSS loads without errors | Launch app, check `stderr` | No GTK CSS parsing warnings |

### Phase 5: Authentication & Settings

- GOAL-005: Implement authentication management and a preferences dialog for configuring the app.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-039 | Create `src/backend/auth_manager.py` — `AuthManager` class handling authentication methods: (1) GitHub signed-in user (copilot CLI login), (2) `GITHUB_TOKEN` / `GH_TOKEN` env var, (3) manually entered token stored in GNOME Keyring via `libsecret` | | |
| TASK-040 | Create `src/widgets/auth_dialog.py` + `.ui` — `AuthDialog(Adw.Dialog)` with status indicator (authenticated/not), GitHub login flow trigger (opens browser for `copilot auth`), manual token entry field | | |
| TASK-041 | Create `src/widgets/preferences_dialog.py` + `.ui` — `PreferencesDialog(Adw.PreferencesDialog)` with pages: General (default model `Adw.ComboRow`, streaming toggle `Adw.SwitchRow`, system message `Adw.EntryRow`), Authentication (auth status, token management), Advanced (CLI path override, log level) | | |
| TASK-042 | Wire GSettings schema to preferences: `default-model`, `streaming-enabled`, `system-message`, `cli-path`, `log-level` | | |
| TASK-043 | Show first-launch setup flow: if no auth is detected, present `AuthDialog` on first run before showing main window | | |
| TASK-044 | Implement BYOK (Bring Your Own Key) support in preferences: provider type selection, base URL, API key entry stored in Keyring | | |

**Verification — Phase 5:**

| VER | Criterion | Command / Method | Pass Condition |
|-----|-----------|-----------------|----------------|
| VER-P5-001 | Auth dialog renders on no-auth | Launch app with no tokens set, no CLI login | `AuthDialog` presented before main window |
| VER-P5-002 | Token stored in Keyring | Enter token in auth dialog, submit | `libsecret` stores token; `secret-tool lookup` retrieves it |
| VER-P5-003 | Token retrieved on next launch | Restart app after storing token | App skips auth dialog, loads main window directly |
| VER-P5-004 | Env var auth works | Set `GITHUB_TOKEN=test`, launch app | Auth detected, main window shown, no auth dialog |
| VER-P5-005 | Preferences dialog opens | Hamburger → Preferences | `PreferencesDialog` renders with General, Authentication, Advanced pages |
| VER-P5-006 | GSettings persistence | Toggle streaming switch off, close dialog, reopen | Switch value remains off; `gsettings get ... streaming-enabled` returns `false` |
| VER-P5-007 | BYOK provider configured | Enter Ollama URL + model in BYOK section, save | `CopilotService` creates session with `provider` config; no crash |
| VER-P5-008 | Token deletion works | Click "Remove Token" in auth settings | `libsecret` entry deleted; next launch shows auth dialog |
| VER-P5-009 | Auth unit tests pass | `uv run pytest tests/test_auth_manager.py -v` (mock libsecret) | All tests pass |

### Phase 6: Conversation Management & Persistence

- GOAL-006: Implement conversation lifecycle management, persistence, and search.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-045 | Create `src/backend/conversation_store.py` — `ConversationStore` class that persists conversation metadata (id, title, model, created_at, updated_at) to `~/.local/share/copilot-gtk/conversations.json` (or SQLite) | | |
| TASK-046 | Implement auto-title generation: after first assistant response, use the first ~50 chars of the response or prompt as conversation title | | |
| TASK-047 | Implement conversation deletion: right-click / long-press context menu on `ConversationRow` → Delete, with `Adw.AlertDialog` confirmation | | |
| TASK-048 | Implement conversation rename: editable title in `ConversationRow` or via context menu | | |
| TASK-049 | Implement message history retrieval: use `session.get_messages()` when re-opening a conversation | | |
| TASK-050 | Add search functionality: `Gtk.SearchBar` in sidebar header to filter conversations by title | | |

**Verification — Phase 6:**

| VER | Criterion | Command / Method | Pass Condition |
|-----|-----------|-----------------|----------------|
| VER-P6-001 | Conversations persist across restarts | Create 3 conversations, quit app, relaunch | All 3 conversations visible in sidebar with correct titles and models |
| VER-P6-002 | JSON store valid | `cat ~/.local/share/copilot-gtk/conversations.json \| python -m json.tool` | Valid JSON, contains 3 conversation entries |
| VER-P6-003 | Auto-title generated | Send first message, receive response | Conversation title in sidebar updates from "New Chat" to first ~50 chars of prompt/response |
| VER-P6-004 | Conversation deletion | Right-click conversation → Delete → Confirm | Conversation removed from sidebar; JSON store no longer contains its ID |
| VER-P6-005 | Delete confirmation dialog | Right-click → Delete | `Adw.AlertDialog` appears before deletion; clicking Cancel aborts |
| VER-P6-006 | Conversation rename | Right-click → Rename → type new title → confirm | Sidebar row updates; JSON store reflects new title |
| VER-P6-007 | Message history retrieval | Select existing conversation after restart | Previous messages displayed in chat view (from `session.get_messages()`) |
| VER-P6-008 | Search filters conversations | Type "weather" in search bar | Only conversations with "weather" in title visible; clear search restores all |
| VER-P6-009 | Persistence unit tests pass | `uv run pytest tests/test_conversation_store.py -v` | All tests pass |
| VER-P6-010 | Corrupt file recovery | Truncate `conversations.json` to invalid JSON, launch app | App starts without crash; sidebar empty; fresh store created |

### Phase 7: Polish, Keyboard Shortcuts & Accessibility

- GOAL-007: Add keyboard shortcuts, accessibility features, tooltips, and UI polish to meet GNOME HIG quality standards.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-051 | Define keyboard shortcuts: `Ctrl+N` (new chat), `Ctrl+W` (close conversation), `Ctrl+K` (search conversations), `Ctrl+Enter` (send message), `Escape` (cancel/close dialog), `F1` (shortcuts window) | | |
| TASK-052 | Create `src/shortcuts_window.ui` — `Gtk.ShortcutsWindow` listing all shortcuts organized by section | | |
| TASK-053 | Create `src/about_dialog.py` — `Adw.AboutDialog` with app name, version, icon, credits, license (GPL-3.0+), links | | |
| TASK-054 | Add accessibility labels to all interactive widgets: `Gtk.Accessible` roles, labels, descriptions | | |
| TASK-055 | Add loading indicators: `Adw.Spinner` in `MessageBubble` while assistant is responding; `Adw.Spinner` on app startup while SDK initializes | | |
| TASK-056 | Add error handling UX: `Adw.Toast` notifications via `Adw.ToastOverlay` for transient errors (network, auth), `Adw.StatusPage` for fatal errors (CLI not found) | | |
| TASK-057 | Implement stop-generation button: while assistant is streaming, show a "Stop" button in `ChatInput` area that cancels the current request | | |
| TASK-058 | Add adaptive layout: at narrow widths, `Adw.NavigationSplitView` collapses to single-pane navigation (mobile-friendly) | | |

**Verification — Phase 7:**

| VER | Criterion | Command / Method | Pass Condition |
|-----|-----------|-----------------|----------------|
| VER-P7-001 | `Ctrl+N` creates new chat | Press `Ctrl+N` in main window | Model selection dialog appears; new conversation created after selection |
| VER-P7-002 | `Ctrl+K` focuses search | Press `Ctrl+K` | Sidebar search bar appears and text cursor is inside it |
| VER-P7-003 | `Ctrl+Enter` sends message | Type text, press `Ctrl+Enter` | Message sent (equivalent to clicking send button) |
| VER-P7-004 | `Escape` closes dialog | Open any dialog, press `Escape` | Dialog dismissed |
| VER-P7-005 | `F1` shows shortcuts window | Press `F1` | `Gtk.ShortcutsWindow` appears with all shortcuts listed by section |
| VER-P7-006 | About dialog correct | Hamburger → About | `Adw.AboutDialog` shows app name, version, icon, license, credits |
| VER-P7-007 | Spinner during streaming | Send message | `Adw.Spinner` visible in assistant bubble during streaming, hidden after `session.idle` |
| VER-P7-008 | Spinner on startup | Launch app | `Adw.Spinner` shown while SDK initializes, replaced by main UI on `ready` signal |
| VER-P7-009 | Toast on transient error | Trigger network error via mock | `Adw.Toast` appears with error text, auto-dismisses after timeout |
| VER-P7-010 | Status page on fatal error | Remove `copilot` from `$PATH`, launch app | `Adw.StatusPage` with "Copilot CLI not found" and install instructions shown |
| VER-P7-011 | Stop button halts generation | Click "Stop" during streaming | Streaming stops, input re-enabled, no orphan spinner |
| VER-P7-012 | Adaptive collapse | Resize window to < 500px width | Sidebar hidden, content takes full width, back button in header |
| VER-P7-013 | Adaptive expand | Resize back to > 800px width | Split layout restored, sidebar and content side-by-side |
| VER-P7-014 | All widgets have a11y labels | Run `accerciser` or AT-SPI tree walk script | Zero interactive widgets with empty accessible name |

### Phase 8: Packaging & Distribution

- GOAL-008: Package the application as a Flatpak and prepare for distribution on Flathub.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-059 | Finalize `io.github.ieshaan.CopilotGTK.json` Flatpak manifest: runtime `org.gnome.Platform//47`, SDK `org.gnome.Sdk//47`, Python modules (copilot-sdk, markdown parser, gbulb), GtkSourceView | | |
| TASK-060 | Create proper app icon: design a recognizable SVG icon following GNOME icon guidelines (symbolic + full-color variants) | | |
| TASK-061 | Write `data/io.github.ieshaan.CopilotGTK.metainfo.xml.in` — full AppStream metadata with screenshots, description, release notes, content rating | | |
| TASK-062 | Test Flatpak build end-to-end: `flatpak-builder --install --user build-dir io.github.ieshaan.CopilotGTK.json` | | |
| TASK-063 | Set up CI/CD: GitHub Actions workflow for linting (`ruff`), type checking (`mypy`), unit tests (`pytest`), automated UI tests (`dogtail`/`pytest-gui`), and Flatpak build verification. Use `uv sync` for reproducible CI installs | | |
| TASK-064 | Write `README.md` with: project description, screenshots, installation instructions (Flatpak, from source), development setup, contributing guide | | |
| TASK-065 | Address Flatpak sandbox considerations: Copilot CLI binary access (may need `--filesystem` permission or bundle CLI), network access for API calls | | |

**Verification — Phase 8:**

| VER | Criterion | Command / Method | Pass Condition |
|-----|-----------|-----------------|----------------|
| VER-P8-001 | Flatpak builds successfully | `flatpak-builder --force-clean build-flatpak io.github.ieshaan.CopilotGTK.json` | Exit code 0, no build errors |
| VER-P8-002 | Flatpak installs & launches | `flatpak-builder --install --user ...` then `flatpak run io.github.ieshaan.CopilotGTK` | App window appears, no sandbox permission errors |
| VER-P8-003 | Network access inside Flatpak | Send a message inside Flatpak-installed app | SDK connects to Copilot CLI server, response received |
| VER-P8-004 | App icon visible | Check GNOME application menu / Activities | Correct SVG icon rendered at all sizes (symbolic in header, full-color in app grid) |
| VER-P8-005 | AppStream metadata valid | `appstreamcli validate --pedantic data/*.metainfo.xml.in` | Zero errors, zero warnings |
| VER-P8-006 | Desktop file valid | `desktop-file-validate` on installed `.desktop` file | Exit code 0 |
| VER-P8-007 | CI pipeline green | Push to GitHub, check Actions | All jobs pass: lint, type check, unit tests, Flatpak build |
| VER-P8-008 | README renders correctly | View on GitHub | Screenshots visible, install instructions accurate, dev setup works when followed |
| VER-P8-009 | `uv.lock` deterministic | `uv sync` on fresh clone | Identical environment to CI; `uv run pytest` passes |

### Phase 9: Automated UI Testing

- GOAL-009: Implement a fully automated UI test suite that exercises the GTK interface end-to-end in a headless compositor, covering all critical user workflows without manual intervention.

**Testing Framework Selection:**

| Framework | Approach | GTK4 Support | Verdict |
|-----------|----------|--------------|--------|
| **dogtail** | AT-SPI accessibility tree introspection | Excellent (AT-SPI is GTK-native) | **PRIMARY** |
| **pytest + GLib test helpers** | Programmatic widget instantiation + signal emission | Native | **UNIT-LEVEL UI** |
| **Selenium/Playwright** | Browser automation | N/A (not web) | Rejected |
| **LDTP** | AT-SPI based | Unmaintained | Rejected |
| **Appium + AT-SPI driver** | Cross-platform automation | Experimental | Backup option |

**Decision:** Use **dogtail** (AT-SPI-based) for end-to-end automated UI tests, complemented by **pytest with GTK widget unit tests** for component-level UI verification. Tests run in a headless Wayland compositor (`wlheadless` / `weston --headless` / `Xvfb` fallback) in CI.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-075 | Add UI test dependencies to `pyproject.toml`: `dogtail`, `python-xlib` (Xvfb support), `pytest-timeout`, `Pillow` (screenshot capture on failure) via `uv add --dev` | | |
| TASK-076 | Create `tests/ui/conftest.py` — pytest fixtures for: (1) launching headless compositor (`weston --headless` or `Xvfb`), (2) launching the app subprocess with mocked `CopilotService` backend via env var `COPILOT_GTK_MOCK_BACKEND=1`, (3) initializing dogtail `tree.root` and finding the app frame, (4) teardown: kill app + compositor, capture screenshot on failure | | |
| TASK-077 | Create `src/backend/mock_copilot_service.py` — `MockCopilotService` that implements the same GObject signal interface as `CopilotService` but returns canned responses (configurable via env vars or JSON fixture files). Used when `COPILOT_GTK_MOCK_BACKEND=1` is set | | |
| TASK-078 | Create `tests/ui/test_app_launch.py` — verify app starts, main window appears (role=`frame`), HeaderBar title is correct, sidebar and content panes are present | | |
| TASK-079 | Create `tests/ui/test_new_conversation.py` — click "New Chat" button via AT-SPI, verify model selection dialog appears, select a model, verify new conversation row appears in sidebar and chat view shows empty state is replaced with input area | | |
| TASK-080 | Create `tests/ui/test_send_message.py` — select a conversation, type into chat input (find `Gtk.TextView` via AT-SPI role), click send button, verify: (A) user message bubble appears, (B) assistant response streams in (from mock), (C) session idle restores input to editable state | | |
| TASK-081 | Create `tests/ui/test_streaming_display.py` — send a message that triggers a multi-chunk mock response, verify message content updates incrementally (poll AT-SPI text content), verify auto-scroll to bottom, verify spinner is visible during streaming and hidden after idle | | |
| TASK-082 | Create `tests/ui/test_conversation_sidebar.py` — create 3 conversations, verify sidebar lists all 3 with correct titles, click each row and verify chat view switches, delete a conversation via context menu and verify removal | | |
| TASK-083 | Create `tests/ui/test_markdown_rendering.py` — send a prompt that triggers a mock response containing headings, bold, code blocks; use AT-SPI text attributes to verify formatting is applied (bold tag, monospace for code), verify code block copy button is accessible | | |
| TASK-084 | Create `tests/ui/test_preferences_dialog.py` — open hamburger menu → Preferences, verify PreferencesDialog appears, toggle streaming switch, change default model combo, close dialog, verify GSettings values persisted | | |
| TASK-085 | Create `tests/ui/test_keyboard_shortcuts.py` — test `Ctrl+N` opens new chat, `Ctrl+K` focuses search bar, `Ctrl+Enter` sends message, `Escape` closes dialogs, `F1` opens shortcuts window | | |
| TASK-086 | Create `tests/ui/test_error_handling.py` — trigger mock error (network failure), verify `Adw.Toast` notification appears with error message, verify app does not crash, verify user can still interact | | |
| TASK-087 | Create `tests/ui/test_auth_dialog.py` — simulate no-auth state via mock, verify first-launch auth dialog appears, enter mock token, verify dialog dismisses and main window loads | | |
| TASK-088 | Create `tests/ui/test_adaptive_layout.py` — resize window to narrow width (< 600px), verify `NavigationSplitView` collapses to single pane, verify back button appears in content header, resize back and verify split layout restores | | |
| TASK-089 | Create `tests/ui/test_accessibility.py` — automated a11y audit: walk the entire AT-SPI tree, assert all interactive widgets (buttons, entries, switches, rows) have non-empty accessible names/labels, all images have descriptions, no orphan focus traps | | |
| TASK-090 | Create `tests/ui/test_dark_mode.py` — toggle color scheme via `Adw.StyleManager` (programmatic or dconf mock), verify app re-renders without crash, capture screenshots in both modes for visual diff (optional: `Pillow` perceptual comparison) | | |
| TASK-091 | Create `.github/workflows/ui-tests.yml` — dedicated CI workflow: install system deps (GTK4, Libadwaita, AT-SPI, Xvfb/weston), `uv sync`, run `pytest tests/ui/ -v --timeout=60` under `xvfb-run` or `weston --headless`, upload screenshot artifacts on failure | | |
| TASK-092 | Add `Makefile`/`justfile` targets: `test-unit` (`pytest tests/ --ignore=tests/ui`), `test-ui` (`xvfb-run pytest tests/ui/`), `test-all` (both), `test-ci` (all + lint + type check) | | |

**Verification — Phase 9:**

| VER | Criterion | Command / Method | Pass Condition |
|-----|-----------|-----------------|----------------|
| VER-P9-001 | UI tests run headless locally | `just test-ui` (or `xvfb-run pytest tests/ui/ -v`) | All 15 UI test files execute; no display-related crashes |
| VER-P9-002 | UI tests pass with mock backend | Set `COPILOT_GTK_MOCK_BACKEND=1`, run UI tests | All `TEST-UI-*` assertions pass; zero failures |
| VER-P9-003 | Screenshot capture on failure | Introduce intentional assertion failure in one test | PNG screenshot saved to `tests/ui/screenshots/` with test name and timestamp |
| VER-P9-004 | CI UI test workflow green | Push PR, observe `.github/workflows/ui-tests.yml` | Job completes successfully; screenshot artifacts uploaded if any fail |
| VER-P9-005 | Mock backend swaps cleanly | Launch app with `COPILOT_GTK_MOCK_BACKEND=1` manually | App behaves identically to real backend but with canned responses |
| VER-P9-006 | `just test-all` runs both suites | `just test-all` | Unit tests and UI tests both execute sequentially; combined exit code 0 |
| VER-P9-007 | AT-SPI tree accessible | Run `python -c "from dogtail.tree import root; print(root)"` under `xvfb-run` | AT-SPI root node printed; no D-Bus errors |
| VER-P9-008 | Test timeout enforcement | Add `@pytest.mark.timeout(60)` to a UI test, make it hang | Test fails after 60s with timeout error, not infinite hang |
| VER-P9-009 | No test pollution | Run UI tests twice in sequence | Second run passes identically; no leftover state from first run |

### Phase 10: Advanced Features (Post-MVP)

- GOAL-010: Implement advanced features that enhance the app beyond basic chat functionality.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-066 | Implement custom tools UI: allow users to see when the agent invokes tools, show tool call names and results in the chat view as collapsible detail rows | | |
| TASK-067 | Implement `on_user_input_request` handler: when the agent asks a question via `ask_user` tool, display an inline prompt in the chat view with choices or free-text input | | |
| TASK-068 | Implement file/image attachment support: drag-and-drop or file picker button in `ChatInput`, pass as `attachments` to `session.send()` | | |
| TASK-069 | Implement MCP server configuration: preferences page to add/remove MCP servers (GitHub MCP, custom MCPs) that get passed to `create_session()` | | |
| TASK-070 | Implement custom agents: UI for creating agent personas (name, description, system prompt) stored in GSettings, selectable when creating a new conversation | | |
| TASK-071 | Implement session hooks UI: optional toggle in preferences for pre-tool-use confirmation dialogs (maps to `on_pre_tool_use` hook with `permissionDecision: "ask"`) | | |
| TASK-072 | Implement export conversation: export chat as Markdown, PDF, or plain text file | | |
| TASK-073 | Add D-Bus activation support: allow opening the app from command line with a prompt, or from other GNOME apps | | |
| TASK-074 | Add GNOME search provider: register as a search provider so users can ask Copilot questions from GNOME shell search | | |

**Verification — Phase 10:**

| VER | Criterion | Command / Method | Pass Condition |
|-----|-----------|-----------------|----------------|
| VER-P10-001 | Tool calls visible in chat | Send prompt that triggers mock tool call | Collapsible tool-call row appears in chat view showing tool name, arguments, result |
| VER-P10-002 | `ask_user` inline prompt | Mock agent asks a question with choices | Inline choice buttons appear in chat; selecting one sends answer back |
| VER-P10-003 | File attachment sends | Drag image into chat input, send | `session.send()` called with `attachments` parameter; no crash |
| VER-P10-004 | MCP server configured | Add GitHub MCP in Preferences → MCP, create new conversation | `create_session()` includes `mcpServers` config |
| VER-P10-005 | Custom agent persona | Create "Code Reviewer" agent, start conversation with it | Session created with custom system prompt; agent behavior reflects persona |
| VER-P10-006 | Pre-tool confirmation dialog | Enable hook in preferences, trigger tool call | `Adw.AlertDialog` appears asking allow/deny; "Deny" blocks tool execution |
| VER-P10-007 | Export as Markdown | Export conversation → Markdown | `.md` file saved; content matches chat messages with correct formatting |
| VER-P10-008 | D-Bus activation | `gdbus call --session -d io.github.ieshaan.CopilotGTK ...` | App opens (or focuses if running) with the given prompt |
| VER-P10-009 | GNOME search provider | Type query in GNOME Activities search | Copilot results appear in search results; clicking opens app with the query |

---

## 3. Alternatives

- **ALT-001**: **Rust + gtk4-rs + community copilot-sdk-rust** — Rejected as primary choice because the Rust SDK is community-maintained and marked "use at your own risk." Performance benefits don't outweigh SDK stability risks for this app's I/O-bound workload. Remains a viable future migration target if the Rust SDK gains official status.

- **ALT-002**: **TypeScript + Electron/Tauri** — Would provide cross-platform support but violates the core requirement of being GTK-native. Electron apps are antithetical to GNOME integration. Tauri uses webkit2gtk but doesn't use Libadwaita/GTK widgets.

- **ALT-003**: **GJS (GNOME JavaScript) + shell to copilot CLI** — GJS is a legitimate GNOME technology, but the copilot-sdk npm packages are incompatible with GJS (different JS runtime). Would require raw CLI invocation and JSON-RPC parsing, losing all SDK benefits (auto-restart, session management, type safety).

- **ALT-004**: **Go + gotk4 + official Go SDK** — Go has an official SDK, but gotk4 bindings are less mature and less documented than PyGObject. The Go runtime also adds ~5MB overhead. The Go SDK is viable but the frontend bindings are the bottleneck.

- **ALT-005**: **WebKitWebView for Markdown rendering** — Instead of native `Gtk.TextView` + `GtkSourceView`, render all messages in embedded WebKit. Provides richer rendering (full HTML/CSS) but breaks native feel, increases memory usage, and creates a security surface. Rejected for MVP; could be revisited for complex content.

- **ALT-006**: **SQLite vs JSON for conversation persistence** — SQLite offers better querying and concurrent access but adds complexity. JSON files are simpler for MVP. Will start with JSON and migrate to SQLite if search/query needs grow.

- **ALT-007**: **Selenium/Playwright vs dogtail for UI testing** — Web automation tools are irrelevant for native GTK apps. Appium with an AT-SPI driver was considered but is experimental and adds Java dependency overhead. `dogtail` is purpose-built for GNOME/GTK AT-SPI testing, is Python-native (matching our stack), and has been used by Red Hat QE for years. Selected as the clear favorite.

---

## 4. Dependencies

- **DEP-001**: `Python >= 3.11` — Required by copilot-sdk
- **DEP-002**: `github-copilot-sdk` (PyPI: `uv add github-copilot-sdk`) — Official Python SDK for Copilot
- **DEP-003**: `PyGObject` (PyPI: `PyGObject`) — Python bindings for GTK4/GLib/GObject
- **DEP-004**: `GTK4 >= 4.12` — Core UI toolkit (system library)
- **DEP-005**: `Libadwaita >= 1.4` — GNOME HIG building blocks (system library)
- **DEP-006**: `GtkSourceView5` — Syntax-highlighted code blocks (system library, GIR: `GtkSource-5`)
- **DEP-007**: `libsecret` — Secure credential storage via GNOME Keyring (system library, GIR: `Secret-1`)
- **DEP-008**: `gbulb` (PyPI) — GLib ↔ asyncio event loop bridge, OR implement custom bridge
- **DEP-009**: `mistune >= 3.0` OR `markdown-it-py` (PyPI) — Markdown parsing for assistant responses
- **DEP-010**: `pycairo` (PyPI) — Cairo bindings, required by PyGObject for rendering
- **DEP-011**: `Copilot CLI` — Must be installed separately by the user and available in `$PATH` (SDK spawns it as a subprocess)
- **DEP-012**: `Meson >= 0.62` — Build system
- **DEP-013**: `flatpak-builder` — Flatpak packaging (development only)
- **DEP-014**: `PyGObject-stubs` (PyPI, dev only) — Type stubs for IDE autocomplete
- **DEP-015**: `uv >= 0.6` — Python package manager for dependency resolution, lockfile, and venv management
- **DEP-016**: `dogtail` (PyPI, dev only) — AT-SPI-based GUI test automation framework for GTK applications
- **DEP-017**: `pytest-timeout` (PyPI, dev only) — Timeout enforcement for UI tests to prevent hangs in CI
- **DEP-018**: `Pillow` (PyPI, dev only) — Screenshot capture on UI test failure for debugging
- **DEP-019**: `AT-SPI2` (system library: `at-spi2-core`, `at-spi2-atk`) — Accessibility bus required by dogtail for widget introspection
- **DEP-020**: `Xvfb` or `weston` (system, CI only) — Headless display server for running UI tests without a physical display

---

## 5. Files

The following file structure will be created:

- **FILE-001**: `meson.build` — Root Meson build file
- **FILE-002**: `src/meson.build` — Source sub-directory build file
- **FILE-003**: `src/main.py` — Application entry point, `Adw.Application` subclass
- **FILE-004**: `src/window.py` + `src/window.ui` — Main application window
- **FILE-005**: `src/backend/async_bridge.py` — GLib ↔ asyncio integration
- **FILE-006**: `src/backend/copilot_service.py` — CopilotClient wrapper with GObject signals
- **FILE-007**: `src/backend/conversation.py` — Conversation data model
- **FILE-008**: `src/backend/message.py` — Message data model
- **FILE-009**: `src/backend/auth_manager.py` — Authentication management
- **FILE-010**: `src/backend/conversation_store.py` — Conversation persistence
- **FILE-011**: `src/widgets/chat_view.py` + `.ui` — Chat message list + scroll container
- **FILE-012**: `src/widgets/chat_input.py` + `.ui` — Message input area
- **FILE-013**: `src/widgets/message_bubble.py` + `.ui` — Single message display widget
- **FILE-014**: `src/widgets/conversation_row.py` + `.ui` — Sidebar conversation item
- **FILE-015**: `src/widgets/conversation_list.py` — Sidebar conversation list
- **FILE-016**: `src/widgets/code_block.py` + `.ui` — Syntax-highlighted code block widget
- **FILE-017**: `src/widgets/markdown_renderer.py` — Markdown → Gtk.TextBuffer converter
- **FILE-018**: `src/widgets/preferences_dialog.py` + `.ui` — Preferences dialog
- **FILE-019**: `src/widgets/auth_dialog.py` + `.ui` — Authentication dialog
- **FILE-020**: `src/about_dialog.py` — About dialog
- **FILE-021**: `src/shortcuts_window.ui` — Keyboard shortcuts window
- **FILE-022**: `src/style.css` — Custom CSS for message bubbles, code blocks
- **FILE-023**: `data/io.github.ieshaan.CopilotGTK.desktop.in` — Desktop entry
- **FILE-024**: `data/io.github.ieshaan.CopilotGTK.metainfo.xml.in` — AppStream metadata
- **FILE-025**: `data/io.github.ieshaan.CopilotGTK.gschema.xml` — GSettings schema
- **FILE-026**: `data/icons/hicolor/scalable/apps/io.github.ieshaan.CopilotGTK.svg` — App icon
- **FILE-027**: `data/icons/hicolor/symbolic/apps/io.github.ieshaan.CopilotGTK-symbolic.svg` — Symbolic icon
- **FILE-028**: `build-aux/io.github.ieshaan.CopilotGTK.Devel.json` — Flatpak manifest
- **FILE-029**: `tests/test_copilot_service.py` — Backend unit tests
- **FILE-030**: `tests/test_markdown_renderer.py` — Markdown renderer tests
- **FILE-031**: `tests/test_conversation_store.py` — Persistence tests
- **FILE-032**: `tests/ui/conftest.py` — UI test fixtures: headless compositor launch, app subprocess, dogtail setup, screenshot-on-failure
- **FILE-033**: `tests/ui/test_app_launch.py` — UI test: app startup, window presence, layout verification
- **FILE-034**: `tests/ui/test_new_conversation.py` — UI test: new chat flow, model selection
- **FILE-035**: `tests/ui/test_send_message.py` — UI test: message send, response display, idle state
- **FILE-036**: `tests/ui/test_streaming_display.py` — UI test: incremental streaming, auto-scroll, spinner
- **FILE-037**: `tests/ui/test_conversation_sidebar.py` — UI test: multi-conversation management, deletion
- **FILE-038**: `tests/ui/test_markdown_rendering.py` — UI test: rich text formatting verification via AT-SPI
- **FILE-039**: `tests/ui/test_preferences_dialog.py` — UI test: preferences open/modify/persist
- **FILE-040**: `tests/ui/test_keyboard_shortcuts.py` — UI test: all keyboard shortcuts functional
- **FILE-041**: `tests/ui/test_error_handling.py` — UI test: error toast display, app resilience
- **FILE-042**: `tests/ui/test_auth_dialog.py` — UI test: first-launch auth flow
- **FILE-043**: `tests/ui/test_adaptive_layout.py` — UI test: responsive layout collapse/expand
- **FILE-044**: `tests/ui/test_accessibility.py` — UI test: automated a11y audit of AT-SPI tree
- **FILE-045**: `tests/ui/test_dark_mode.py` — UI test: color scheme toggle, screenshot comparison
- **FILE-046**: `src/backend/mock_copilot_service.py` — Mock backend for UI tests with canned responses
- **FILE-047**: `tests/ui/fixtures/` — Directory containing JSON fixture files for mock responses
- **FILE-048**: `README.md` — Project documentation
- **FILE-049**: `.github/workflows/ci.yml` — CI pipeline (lint, type check, unit tests)
- **FILE-050**: `.github/workflows/ui-tests.yml` — Dedicated UI test CI pipeline (headless compositor + dogtail)
- **FILE-051**: `pyproject.toml` — Project metadata, dependencies, and tool config (managed by `uv`)
- **FILE-052**: `uv.lock` — Deterministic dependency lockfile
- **FILE-053**: `justfile` — Task runner targets: `test-unit`, `test-ui`, `test-all`, `test-ci`, `lint`, `typecheck`

---

## 6. Testing

- **TEST-001**: Unit test `CopilotService` — mock `CopilotClient`, verify `start()`, `create_conversation()`, `send_message()`, `stop()` call correct SDK methods and emit correct GObject signals
- **TEST-002**: Unit test `CopilotService` event bridging — mock SDK events (`assistant.message_delta`, `session.idle`), verify they are re-emitted as GObject signals on the main thread
- **TEST-003**: Unit test `MarkdownRenderer` — feed various Markdown strings (headings, bold, code fences, lists, links) and verify correct `Gtk.TextTag` application on the `Gtk.TextBuffer`
- **TEST-004**: Unit test `ConversationStore` — verify save/load/delete of conversation metadata; test file corruption recovery
- **TEST-005**: Unit test `AuthManager` — mock `libsecret` calls, verify token storage/retrieval/deletion
- **TEST-006**: Integration test — launch full app in headless mode (Xvfb/weston), verify window creation, sidebar population, message send/receive flow with mocked SDK
- **TEST-007**: Flatpak build test — CI job that runs `flatpak-builder` to verify the manifest produces a valid bundle
- **TEST-008**: Lint & type check — `ruff check`, `mypy` with PyGObject stubs, verify zero errors
- **TEST-009**: Accessibility audit — verify all interactive widgets have proper `Gtk.Accessible` labels (automated via AT-SPI tree walk in `test_accessibility.py`)
- **TEST-010**: Manual test matrix — streaming with large responses, network disconnection during stream, multiple concurrent conversations, model switching mid-conversation

### Automated UI Tests (dogtail + AT-SPI)

All UI tests run in a headless compositor with a mocked Copilot backend. They are fully automated and execute in CI without any manual intervention.

- **TEST-UI-001**: **App Launch** — verify main window appears with correct title, HeaderBar, sidebar, and content area within 5 seconds
- **TEST-UI-002**: **New Conversation Flow** — click "New Chat" → model dialog appears → select model → conversation row added to sidebar → chat input area active
- **TEST-UI-003**: **Send Message** — type text in input → click send (or Ctrl+Enter) → user bubble appears → assistant response streams from mock → final message displayed → input re-enabled
- **TEST-UI-004**: **Streaming Display** — verify incremental text appearance (poll AT-SPI text content at intervals), auto-scroll behavior, spinner visibility during streaming
- **TEST-UI-005**: **Conversation Sidebar CRUD** — create 3 conversations → verify all listed → click each to switch → rename one → delete one → verify final count is 2
- **TEST-UI-006**: **Markdown Rendering** — trigger mock response with `# Heading`, `**bold**`, `` `code` ``, fenced code block → verify AT-SPI text attributes (bold, monospace) → verify code block copy button exists and is clickable
- **TEST-UI-007**: **Preferences Dialog** — hamburger → Preferences → dialog opens → toggle streaming switch → change model combo → close → reopen → verify changes persisted
- **TEST-UI-008**: **Keyboard Shortcuts** — `Ctrl+N` (new chat), `Ctrl+K` (search focus), `Ctrl+Enter` (send), `Escape` (close dialog), `F1` (shortcuts window) — each verified by AT-SPI state change
- **TEST-UI-009**: **Error Handling** — trigger mock network error → verify toast notification appears → verify app remains interactive → send another message successfully
- **TEST-UI-010**: **Auth Dialog (First Launch)** — start app with no auth → auth dialog shown → enter mock token → dialog dismisses → main window loads
- **TEST-UI-011**: **Adaptive Layout** — resize window to 400px width → verify single-pane mode (sidebar hidden, back button visible) → resize to 1200px → verify split-pane restored
- **TEST-UI-012**: **Accessibility Audit** — walk full AT-SPI tree → assert every `push button`, `text`, `toggle button`, `combo box`, `list item` has non-empty `name` or `description` → fail on any unlabeled interactive widget
- **TEST-UI-013**: **Dark Mode Toggle** — switch `Adw.StyleManager` to dark → verify no crash → capture screenshot → switch to light → capture screenshot → verify both screenshots differ (Pillow comparison)
- **TEST-UI-014**: **Stop Generation** — start streaming → click Stop button → verify streaming halts → verify input re-enabled → verify no orphan spinner
- **TEST-UI-015**: **Long Conversation Scroll** — send 20 messages in sequence → verify scroll position is at bottom → scroll up → send new message → verify auto-scroll back to bottom

---

## 7. Risks & Assumptions

- **RISK-001**: **Copilot SDK is in Technical Preview** — API may introduce breaking changes. *Mitigation*: Pin SDK version in requirements, wrap all SDK calls in `CopilotService` abstraction layer so changes are isolated.
- **RISK-002**: **GLib ↔ asyncio bridge complexity** — Integrating two event loops is non-trivial and can cause subtle threading bugs. *Mitigation*: Use well-tested `gbulb` library; if insufficient, implement a minimal bridge with `GLib.idle_add` for dispatching coroutine results to the main thread.
- **RISK-003**: **Copilot CLI distribution in Flatpak** — The SDK requires `copilot` CLI in `$PATH`, but Flatpak sandboxing may prevent access. *Mitigation*: (A) Use `--talk-name` to communicate with a host-side CLI, (B) bundle the CLI binary in the Flatpak, or (C) require users to install CLI on host and grant filesystem access.
- **RISK-004**: **Markdown rendering fidelity** — Native `Gtk.TextView` rendering may not handle all Markdown edge cases (tables, nested blockquotes, math). *Mitigation*: Start with core Markdown (headings, bold/italic, code, lists) and iteratively add support.
- **RISK-005**: **Memory usage with long conversations** — Streaming many messages into `Gtk.TextBuffer` widgets may consume significant memory. *Mitigation*: Use `Gtk.ListView` with recycled widgets instead of creating a `MessageBubble` per message; rely on SDK's infinite session compaction for context management.
- **RISK-006**: **AT-SPI availability in CI for UI tests** — Headless CI environments may not have a running D-Bus session or AT-SPI registry, causing dogtail tests to fail. *Mitigation*: CI workflow explicitly starts `dbus-daemon --session`, sets `DBUS_SESSION_BUS_ADDRESS`, and launches `at-spi-bus-launcher`. Use `xvfb-run` to provide a display. All documented in `.github/workflows/ui-tests.yml`.
- **ASSUMPTION-001**: Users have a GitHub Copilot subscription (free tier or paid) or BYOK credentials.
- **ASSUMPTION-002**: Users are running a GNOME desktop environment (or at least have GTK4 + Libadwaita libraries installed).
- **ASSUMPTION-003**: Users can install the Copilot CLI separately (it is not bundled with this app in the initial version).
- **ASSUMPTION-004**: Network connectivity is available for Copilot API calls (no offline mode).

---

## 8. Related Specifications / Further Reading

- [GitHub Copilot SDK — Main Repository](https://github.com/github/copilot-sdk)
- [Copilot SDK — Python README](https://github.com/github/copilot-sdk/tree/main/python)
- [Copilot SDK — Getting Started Guide](https://github.com/github/copilot-sdk/blob/main/docs/getting-started.md)
- [Copilot SDK — Authentication Docs](https://github.com/github/copilot-sdk/blob/main/docs/auth/index.md)
- [Copilot SDK — BYOK (Bring Your Own Key)](https://github.com/github/copilot-sdk/blob/main/docs/auth/byok.md)
- [Copilot SDK — MCP Server Integration](https://github.com/github/copilot-sdk/blob/main/docs/mcp/overview.md)
- [PyGObject — Getting Started](https://pygobject.gnome.org/getting_started.html)
- [PyGObject — Tutorials](https://pygobject.gnome.org/tutorials/index.html)
- [Libadwaita 1.x API Reference](https://gnome.pages.gitlab.gnome.org/libadwaita/doc/1-latest/)
- [Libadwaita Widget Gallery](https://gnome.pages.gitlab.gnome.org/libadwaita/doc/1-latest/widget-gallery.html)
- [GNOME Developer Documentation — Beginners Tutorials](https://developer.gnome.org/documentation/tutorials/beginners.html)
- [GNOME Human Interface Guidelines](https://developer.gnome.org/hig/)
- [GtkSourceView API Reference](https://gnome.pages.gitlab.gnome.org/gtksourceview/gtksourceview5/)
- [Flatpak Developer Documentation](https://docs.flatpak.org/)
- [gbulb — GLib event loop for asyncio](https://github.com/beeware/gbulb)
- [GNOME apps built with Python (reference)](https://wiki.gnome.org/Apps) — Dialect, Apostrophe, Bottles
- [uv — Python package manager](https://docs.astral.sh/uv/) — Dependency management, lockfile, venv
- [dogtail — GUI test automation](https://gitlab.com/dogtail/dogtail) — AT-SPI-based testing for GTK apps
- [AT-SPI2 — Accessibility Service Provider Interface](https://wiki.gnome.org/Accessibility) — Foundation for automated UI testing
- [Xvfb — Virtual framebuffer](https://www.x.org/releases/X11R7.6/doc/man/man1/Xvfb.1.xhtml) — Headless display for CI GUI tests
- [weston — Wayland compositor (headless mode)](https://wayland.freedesktop.org/weston.html) — Native Wayland headless testing
