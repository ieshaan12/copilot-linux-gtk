# SPDX-License-Identifier: GPL-3.0-or-later
"""CodeBlock — Syntax-highlighted code block widget with copy button."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GtkSource", "5")

from gi.repository import Adw, Gdk, GLib, GObject, Gtk, GtkSource, Pango  # noqa: E402


class CodeBlock(Gtk.Box):
    """A code block widget using GtkSourceView with syntax highlighting.

    Displays a header bar with the language name and a copy-to-clipboard
    button, followed by a non-editable GtkSourceView.
    """

    __gtype_name__ = "CodeBlock"

    def __init__(
        self,
        code: str = "",
        language: str = "",
    ) -> None:
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=0,
        )
        self.add_css_class("code-block")

        self._code = code
        self._language = language

        # --- Header bar ---
        header = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=6,
            margin_start=10,
            margin_end=6,
            margin_top=4,
            margin_bottom=4,
        )
        header.add_css_class("code-block-header")

        lang_label = Gtk.Label(
            label=language or "text",
            xalign=0,
            hexpand=True,
        )
        lang_label.add_css_class("caption")
        lang_label.add_css_class("dim-label")
        header.append(lang_label)

        copy_btn = Gtk.Button(icon_name="edit-copy-symbolic")
        copy_btn.set_tooltip_text("Copy code")
        copy_btn.add_css_class("flat")
        copy_btn.add_css_class("circular")
        copy_btn.add_css_class("code-copy-btn")
        copy_btn.connect("clicked", self._on_copy_clicked)
        copy_btn.update_property(
            [Gtk.AccessibleProperty.LABEL],
            [f"Copy {language or 'code'} to clipboard"],
        )
        header.append(copy_btn)
        self._copy_btn = copy_btn

        self.append(header)

        # --- Source view ---
        self._source_buffer = GtkSource.Buffer()
        self._source_view = GtkSource.View(
            buffer=self._source_buffer,
            editable=False,
            cursor_visible=False,
            monospace=True,
            show_line_numbers=False,
            top_margin=4,
            bottom_margin=8,
            left_margin=10,
            right_margin=10,
        )
        self._source_view.add_css_class("code-block-source")

        # Apply language highlighting
        if language:
            lang_manager = GtkSource.LanguageManager.get_default()
            src_lang = lang_manager.get_language(language)
            if src_lang is None:
                # Try common aliases
                aliases = {
                    "js": "javascript",
                    "ts": "typescript",
                    "py": "python",
                    "rb": "ruby",
                    "sh": "bash",
                    "shell": "bash",
                    "yml": "yaml",
                    "dockerfile": "docker",
                    "rs": "rust",
                    "cs": "c-sharp",
                    "cpp": "cpp",
                    "c++": "cpp",
                    "objc": "objc",
                    "jsx": "javascript",
                    "tsx": "typescript",
                }
                alias = aliases.get(language.lower())
                if alias:
                    src_lang = lang_manager.get_language(alias)
            if src_lang is not None:
                self._source_buffer.set_language(src_lang)

        # Apply a colour scheme that follows the system theme
        style_manager = Adw.StyleManager.get_default()
        self._apply_scheme(style_manager)
        style_manager.connect("notify::dark", lambda sm, _: self._apply_scheme(sm))

        self._source_buffer.set_text(code)

        # Wrap in a frame-like container
        self.append(self._source_view)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _apply_scheme(self, style_manager: Adw.StyleManager) -> None:
        """Set GtkSourceView colour scheme matching dark/light mode."""
        scheme_manager = GtkSource.StyleSchemeManager.get_default()
        if style_manager.get_dark():
            scheme = scheme_manager.get_scheme("Adwaita-dark")
        else:
            scheme = scheme_manager.get_scheme("Adwaita")
        if scheme is not None:
            self._source_buffer.set_style_scheme(scheme)

    def _on_copy_clicked(self, _btn: Gtk.Button) -> None:
        """Copy the code block text to clipboard."""
        clipboard = Gdk.Display.get_default().get_clipboard()
        clipboard.set(self._code)

        # Visual feedback
        self._copy_btn.set_icon_name("object-select-symbolic")
        self._copy_btn.set_tooltip_text("Copied!")
        GLib.timeout_add(
            2000,
            self._reset_copy_btn,
        )

    def _reset_copy_btn(self) -> bool:
        self._copy_btn.set_icon_name("edit-copy-symbolic")
        self._copy_btn.set_tooltip_text("Copy code")
        return GLib.SOURCE_REMOVE

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def code(self) -> str:
        return self._code

    @property
    def language(self) -> str:
        return self._language

    def set_code(self, code: str) -> None:
        """Update the displayed code."""
        self._code = code
        self._source_buffer.set_text(code)
