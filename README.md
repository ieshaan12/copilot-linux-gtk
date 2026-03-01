# Copilot for GNOME

A GNOME-native Linux desktop application for conversational AI, powered by the
[GitHub Copilot SDK](https://github.com/nicolo-ribaudo/copilot-sdk-js).

Built with **GTK4**, **Libadwaita**, and **Python** — following the
[GNOME Human Interface Guidelines](https://developer.gnome.org/hig/).

> **Status:** Technical Preview (v0.1.0)

## Features

- **Streaming AI responses** — real-time token-by-token display
- **Multiple conversations** — create, rename, delete, and search
- **Conversation persistence** — chats survive app restarts
- **Markdown rendering** — headings, bold, italic, lists, inline code
- **Syntax-highlighted code blocks** — powered by GtkSourceView 5 with
  one-click copy
- **Model selection** — choose from available Copilot models per conversation
- **Authentication** — GitHub token, CLI auto-detect, or Bring Your Own Key
- **Keyboard shortcuts** — Ctrl+N, Ctrl+W, Ctrl+K, Ctrl+Enter, F1, Escape
- **Accessibility** — labels on all interactive widgets, screen-reader friendly
- **Adaptive layout** — responsive split view for narrow windows
- **Dark & light mode** — follows system color scheme

## Screenshots

<!-- TODO: Add screenshots after first release -->
<!-- ![Chat View](data/screenshots/chat-view.png) -->
<!-- ![Sidebar Search](data/screenshots/sidebar.png) -->

## Requirements

- **Python** ≥ 3.11
- **GTK4** ≥ 4.12
- **Libadwaita** ≥ 1.4
- **GtkSourceView 5**
- **libsecret** (for GNOME Keyring token storage)
- **GitHub Copilot** subscription (for the AI backend)

## Installation

### From Source (recommended for development)

1. **Install system dependencies** (Fedora):

   ```bash
   sudo dnf install gtk4-devel libadwaita-devel gtksourceview5-devel \
       libsecret-devel gobject-introspection-devel python3-gobject
   ```

   Ubuntu/Debian:

   ```bash
   sudo apt install libgtk-4-dev libadwaita-1-dev libgtksourceview-5-dev \
       libsecret-1-dev libgirepository1.0-dev gir1.2-gtk-4.0 gir1.2-adw-1 \
       gir1.2-gtksource-5 gir1.2-secret-1
   ```

2. **Install [uv](https://docs.astral.sh/uv/)** (Python package manager):

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

3. **Clone and install**:

   ```bash
   git clone https://github.com/ieshaan12/copilot-linux-gtk.git
   cd copilot-linux-gtk
   uv sync
   ```

4. **Run**:

   ```bash
   uv run copilot-gtk
   ```

### Flatpak (coming soon)

```bash
flatpak install io.github.ieshaan.CopilotGTK
flatpak run io.github.ieshaan.CopilotGTK
```

## Development

### Setup

```bash
git clone https://github.com/ieshaan12/copilot-linux-gtk.git
cd copilot-linux-gtk
uv sync                    # Install all dependencies (including dev)
```

### Common Commands

```bash
uv run copilot-gtk         # Run the app
uv run pytest tests/ -v    # Run unit tests
uv run ruff check src/     # Lint
uv run ruff format src/    # Format
uv run mypy src/copilot_gtk/ --ignore-missing-imports  # Type check
```

Or use the Justfile (requires [just](https://github.com/casey/just)):

```bash
just run                   # Run the app
just test                  # Run all unit tests
just lint                  # Lint + format check
just typecheck             # Mypy type checking
just check                 # All checks (lint + typecheck + test)
```

### Project Structure

```
src/copilot_gtk/
├── main.py                 # Application entry point
├── window.py               # Main window (split view)
├── style.css               # Custom GTK stylesheet
├── backend/
│   ├── copilot_service.py  # GObject wrapper around Copilot SDK
│   ├── auth_manager.py     # Authentication management
│   ├── conversation.py     # Conversation model
│   ├── conversation_store.py # JSON persistence
│   └── message.py          # Message model
└── widgets/
    ├── chat_view.py        # Scrollable chat message list
    ├── chat_input.py       # Multi-line text input with send/stop
    ├── message_bubble.py   # Individual message display
    ├── markdown_renderer.py # Markdown → GTK text tags
    ├── code_block.py       # Syntax-highlighted code blocks
    ├── conversation_list.py # Sidebar conversation list
    ├── conversation_row.py # Individual sidebar row
    ├── shortcuts_window.py # Keyboard shortcuts overlay
    ├── auth_dialog.py      # First-launch authentication
    └── preferences_dialog.py # Settings dialog

data/
├── io.github.ieshaan.CopilotGTK.desktop.in
├── io.github.ieshaan.CopilotGTK.metainfo.xml.in
├── io.github.ieshaan.CopilotGTK.gschema.xml
└── icons/                  # App icons (scalable + symbolic SVG)

tests/                      # 238 unit tests
```

### Architecture

The app uses **gbulb** to bridge the GLib main loop with Python's asyncio,
allowing the Copilot SDK (which is asyncio-based) to run alongside GTK's
event-driven UI. The `CopilotService` class wraps the SDK client and exposes
all events as GObject signals that the UI widgets connect to.

## Keyboard Shortcuts

| Shortcut       | Action                |
| -------------- | --------------------- |
| `Ctrl+N`       | New conversation      |
| `Ctrl+W`       | Close conversation    |
| `Ctrl+K`       | Search conversations  |
| `Ctrl+Enter`   | Send message          |
| `Escape`       | Close search / Stop   |
| `F1`           | Keyboard shortcuts    |
| `Ctrl+Q`       | Quit                  |

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes with tests
4. Run `just check` (or the individual commands above)
5. Open a Pull Request

## License

[GPL-3.0-or-later](https://www.gnu.org/licenses/gpl-3.0.html)

Copyright © 2026 ieshaan
