# SPDX-License-Identifier: GPL-3.0-or-later
"""MarkdownRenderer — Converts Markdown text into a styled Gtk.TextView.

Uses ``mistune`` 3.x to parse Markdown into an AST, then walks the AST
to populate a ``Gtk.TextBuffer`` with ``Gtk.TextTag`` styles. Fenced code
blocks are rendered as embedded :class:`CodeBlock` child widgets via
``Gtk.TextChildAnchor``.
"""

from __future__ import annotations

import logging
from typing import Any

import gi
import mistune

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gdk, Gtk, Pango  # noqa: E402

from .code_block import CodeBlock  # noqa: E402

log = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────
# Tag names (constants)
# ──────────────────────────────────────────────────────────────────────

_HEADING_SCALES = {
    1: 1.6,
    2: 1.4,
    3: 1.2,
    4: 1.1,
    5: 1.05,
    6: 1.0,
}


class MarkdownTextView(Gtk.TextView):
    """A non-editable TextView that renders Markdown content.

    Call :meth:`set_markdown` to replace the entire content, or
    :meth:`append_markdown_delta` for streaming incremental tokens
    (though incremental rendering re-parses the full accumulated text
    for correctness).
    """

    __gtype_name__ = "MarkdownTextView"

    # Maximum natural width (px) for content-adaptive sizing.
    _MAX_CONTENT_WIDTH = 600

    def __init__(self) -> None:
        super().__init__(
            editable=False,
            cursor_visible=False,
            wrap_mode=Gtk.WrapMode.WORD_CHAR,
            top_margin=0,
            bottom_margin=0,
            left_margin=0,
            right_margin=0,
        )
        self._raw_markdown = ""
        self._code_blocks: list[CodeBlock] = []
        self._setup_tags()

    # ------------------------------------------------------------------
    # Size negotiation
    # ------------------------------------------------------------------

    def do_measure(self, orientation: Gtk.Orientation, for_size: int) -> tuple[int, int, int, int]:
        """Content-aware natural width.

        ``Gtk.TextView`` with ``wrap_mode=WORD_CHAR`` reports a natural
        width equal to the longest single word, which collapses the
        message bubble.  We override this to return a width derived from
        the actual content length (capped at :pyattr:`_MAX_CONTENT_WIDTH`).
        """
        min_w, nat_w, min_bl, nat_bl = Gtk.TextView.do_measure(self, orientation, for_size)
        if orientation == Gtk.Orientation.HORIZONTAL:
            if self._raw_markdown:
                lines = self._raw_markdown.split("\n")
                max_line_len = max(len(line) for line in lines)
                # Use Pango font metrics for accurate char width
                ctx = self.get_pango_context()
                metrics = ctx.get_metrics(None, None)
                char_w = metrics.get_approximate_char_width() / Pango.SCALE
                content_w = min(
                    int(max_line_len * char_w) + 30,
                    self._MAX_CONTENT_WIDTH,
                )
                nat_w = max(min_w, content_w)
            else:
                nat_w = max(min_w, 100)
            # No horizontal baselines
            return min_w, nat_w, -1, -1
        return min_w, nat_w, min_bl, nat_bl

    # ------------------------------------------------------------------
    # Tag setup
    # ------------------------------------------------------------------

    def _setup_tags(self) -> None:
        """Create reusable TextTags in the buffer's tag table."""
        buf = self.get_buffer()
        table = buf.get_tag_table()

        def _add(name: str, **props: Any) -> Gtk.TextTag:
            tag = Gtk.TextTag(name=name)
            for k, v in props.items():
                tag.set_property(k, v)
            table.add(tag)
            return tag

        # Headings
        for level, scale in _HEADING_SCALES.items():
            _add(
                f"h{level}",
                scale=scale,
                weight=Pango.Weight.BOLD,
                pixels_above_lines=int(8 * scale),
                pixels_below_lines=4,
            )

        # Inline styles
        _add("bold", weight=Pango.Weight.BOLD)
        _add("italic", style=Pango.Style.ITALIC)
        _add("strikethrough", strikethrough=True)
        _add("inline-code", family="monospace", background_rgba=_rgba("#80808033"))

        # Links
        _add(
            "link",
            foreground_rgba=_rgba("#3584e4"),
            underline=Pango.Underline.SINGLE,
        )

        # Blockquote
        _add(
            "blockquote",
            left_margin=16,
            style=Pango.Style.ITALIC,
            foreground_rgba=_rgba("#888888"),
            pixels_above_lines=4,
            pixels_below_lines=4,
        )

        # List items
        _add("list-item", left_margin=20, pixels_above_lines=2)
        _add("list-item-2", left_margin=40, pixels_above_lines=2)
        _add("list-item-3", left_margin=60, pixels_above_lines=2)

        # Thematic break
        _add("thematic-break", foreground_rgba=_rgba("#888888"))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_markdown(self, text: str) -> None:
        """Parse *text* as Markdown and render into the buffer."""
        self._raw_markdown = text
        self._render()

    def get_markdown(self) -> str:
        """Return the raw Markdown source."""
        return self._raw_markdown

    def append_markdown_delta(self, delta: str) -> None:
        """Append *delta* to accumulated Markdown and re-render."""
        self._raw_markdown += delta
        self._render()

    @property
    def code_blocks(self) -> list[CodeBlock]:
        """Embedded CodeBlock widgets (for testing access)."""
        return list(self._code_blocks)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render(self) -> None:
        """Parse ``_raw_markdown`` via mistune and populate the buffer."""
        buf = self.get_buffer()

        # Clear
        buf.set_text("")
        self._code_blocks.clear()

        if not self._raw_markdown.strip():
            return

        # Parse via mistune AST renderer (returns list of tokens)
        md = mistune.create_markdown(renderer=None)
        tokens = md(self._raw_markdown)

        self._walk_tokens(buf, tokens)  # type: ignore[arg-type]

    def _walk_tokens(self, buf: Gtk.TextBuffer, tokens: list[dict[str, Any]]) -> None:
        """Recursively walk the mistune AST token list."""
        for token in tokens:
            ttype = token.get("type", "")
            children = token.get("children")

            if ttype == "paragraph":
                self._render_paragraph(buf, children)
            elif ttype == "heading":
                self._render_heading(buf, token, children)
            elif ttype == "code_block" or ttype == "block_code":
                self._render_code_block(buf, token)
            elif ttype == "list":
                self._render_list(buf, token, depth=0)
            elif ttype in ("blockquote", "block_quote"):
                self._render_blockquote(buf, children)
            elif ttype == "thematic_break":
                self._insert_thematic_break(buf)
            elif ttype == "blank_line":
                pass  # skip extra blank lines
            else:
                # Fallback: if it has children, walk them
                if children:
                    self._walk_tokens(buf, children)

    # ------------------------------------------------------------------
    # Block-level renderers
    # ------------------------------------------------------------------

    def _render_paragraph(self, buf: Gtk.TextBuffer, children: list[dict] | None) -> None:
        """Render a paragraph — just its inline children + trailing newline."""
        if not children:
            return
        self._render_inline(buf, children)
        self._insert_text(buf, "\n")

    def _render_heading(
        self, buf: Gtk.TextBuffer, token: dict, children: list[dict] | None
    ) -> None:
        attrs = token.get("attrs", {}) or {}
        level = attrs.get("level", 1)
        tag_name = f"h{level}"

        start_mark = self._create_mark(buf)
        if children:
            self._render_inline(buf, children, extra_tags=[])
        end = buf.get_end_iter()
        start_iter = buf.get_iter_at_mark(start_mark)
        buf.apply_tag_by_name(tag_name, start_iter, end)
        buf.delete_mark(start_mark)
        self._insert_text(buf, "\n")

    def _render_code_block(self, buf: Gtk.TextBuffer, token: dict) -> None:
        """Embed a CodeBlock widget via TextChildAnchor."""
        attrs = token.get("attrs", {}) or {}
        raw = token.get("raw", "") or token.get("text", "")
        info = attrs.get("info", "") or ""
        language = info.split()[0] if info else ""

        # Strip trailing newline from code
        code = raw.rstrip("\n")

        # Ensure we're on a new line
        end = buf.get_end_iter()
        if end.get_offset() > 0:
            prev = end.copy()
            prev.backward_char()
            if buf.get_text(prev, end, False) != "\n":
                buf.insert(end, "\n")
                end = buf.get_end_iter()

        anchor = buf.create_child_anchor(end)

        code_block = CodeBlock(code=code, language=language)
        self.add_child_at_anchor(code_block, anchor)
        self._code_blocks.append(code_block)

        end = buf.get_end_iter()
        buf.insert(end, "\n")

    def _render_list(self, buf: Gtk.TextBuffer, token: dict, depth: int = 0) -> None:
        """Render an ordered or unordered list."""
        attrs = token.get("attrs", {}) or {}
        ordered = attrs.get("ordered", False)
        children = token.get("children") or []

        for i, item in enumerate(children, start=1):
            if item.get("type") != "list_item":
                continue
            self._render_list_item(buf, item, i, ordered, depth)

    def _render_list_item(
        self,
        buf: Gtk.TextBuffer,
        item: dict,
        index: int,
        ordered: bool,
        depth: int,
    ) -> None:
        """Render a single list item, possibly with nested content."""
        # Clamp depth for CSS tags
        if depth >= 2:
            tag_name = "list-item-3"
        elif depth == 1:
            tag_name = "list-item-2"
        else:
            tag_name = "list-item"

        # Bullet / number prefix
        if ordered:
            prefix = f"{index}. "
        else:
            bullets = ["• ", "◦ ", "▪ "]
            prefix = bullets[min(depth, len(bullets) - 1)]

        start_mark = self._create_mark(buf)
        self._insert_text(buf, prefix)

        children = item.get("children") or []
        nested_list = None
        for child in children:
            ctype = child.get("type", "")
            if ctype in ("paragraph", "block_text"):
                self._render_inline(buf, child.get("children") or [])
            elif ctype == "list":
                nested_list = child
            elif child.get("children"):
                self._render_inline(buf, child.get("children") or [])

        # Apply tag to the current item's text (prefix + inline content)
        end = buf.get_end_iter()
        start_iter = buf.get_iter_at_mark(start_mark)
        tag = buf.get_tag_table().lookup(tag_name)
        if tag:
            buf.apply_tag(tag, start_iter, end)
        buf.delete_mark(start_mark)
        self._insert_text(buf, "\n")

        # Now render nested list, if any
        if nested_list is not None:
            self._render_list(buf, nested_list, depth=depth + 1)

    def _render_blockquote(self, buf: Gtk.TextBuffer, children: list[dict] | None) -> None:
        if not children:
            return
        start_mark = self._create_mark(buf)
        self._walk_tokens(buf, children)
        end = buf.get_end_iter()
        start_iter = buf.get_iter_at_mark(start_mark)
        buf.apply_tag_by_name("blockquote", start_iter, end)
        buf.delete_mark(start_mark)

    def _insert_thematic_break(self, buf: Gtk.TextBuffer) -> None:
        start_mark = self._create_mark(buf)
        self._insert_text(buf, "─" * 40 + "\n")
        end = buf.get_end_iter()
        start_iter = buf.get_iter_at_mark(start_mark)
        buf.apply_tag_by_name("thematic-break", start_iter, end)
        buf.delete_mark(start_mark)

    # ------------------------------------------------------------------
    # Inline renderers
    # ------------------------------------------------------------------

    def _render_inline(
        self,
        buf: Gtk.TextBuffer,
        tokens: list[dict],
        extra_tags: list[str] | None = None,
    ) -> None:
        """Render a list of inline tokens (text, strong, emphasis, etc.)."""
        tags = extra_tags or []
        for token in tokens:
            ttype = token.get("type", "")
            children = token.get("children")

            if ttype == "text":
                raw = token.get("raw", "") or token.get("text", "")
                self._insert_text(buf, raw, tags)

            elif ttype == "strong":
                self._render_inline(buf, children or [], tags + ["bold"])

            elif ttype == "emphasis":
                self._render_inline(buf, children or [], tags + ["italic"])

            elif ttype == "strikethrough":
                self._render_inline(buf, children or [], tags + ["strikethrough"])

            elif ttype == "codespan":
                raw = token.get("raw", "") or token.get("text", "")
                # Strip surrounding backticks if present
                code_text = raw.strip("`") if raw else ""
                self._insert_text(buf, code_text, tags + ["inline-code"])

            elif ttype == "link":
                # We store the URL as invisible data—click handling done elsewhere
                self._render_inline(buf, children or [], tags + ["link"])

            elif ttype == "image":
                attrs = token.get("attrs", {}) or {}
                alt = attrs.get("alt", "")
                self._insert_text(buf, f"[Image: {alt}]", tags)

            elif ttype == "softbreak":
                self._insert_text(buf, " ", tags)

            elif ttype == "linebreak":
                self._insert_text(buf, "\n", tags)

            elif ttype == "raw_html" or ttype == "html":
                raw = token.get("raw", "") or ""
                self._insert_text(buf, raw, tags)

            else:
                # Fallback: render raw text or walk children
                raw = token.get("raw", "") or token.get("text", "")
                if raw:
                    self._insert_text(buf, raw, tags)
                elif children:
                    self._render_inline(buf, children, tags)

    # ------------------------------------------------------------------
    # Buffer helpers
    # ------------------------------------------------------------------

    def _insert_text(
        self,
        buf: Gtk.TextBuffer,
        text: str,
        tag_names: list[str] | None = None,
    ) -> None:
        """Insert *text* at end of buffer, optionally applying tags."""
        if not text:
            return

        start_mark = self._create_mark(buf)
        end = buf.get_end_iter()
        buf.insert(end, text)

        if tag_names:
            end = buf.get_end_iter()
            start_iter = buf.get_iter_at_mark(start_mark)
            for tag_name in tag_names:
                tag = buf.get_tag_table().lookup(tag_name)
                if tag:
                    buf.apply_tag(tag, start_iter, end)
        buf.delete_mark(start_mark)

    def _create_mark(self, buf: Gtk.TextBuffer) -> Gtk.TextMark:
        """Create a left-gravity mark at the current end of buffer."""
        end = buf.get_end_iter()
        return buf.create_mark(None, end, True)


# ──────────────────────────────────────────────────────────────────────
# Utility
# ──────────────────────────────────────────────────────────────────────


def _rgba(hex_color: str) -> Gdk.RGBA:
    """Parse a hex colour string (with optional alpha) into Gdk.RGBA."""
    rgba = Gdk.RGBA()
    rgba.parse(hex_color)
    return rgba
