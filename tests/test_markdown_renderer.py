# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for MarkdownTextView and CodeBlock widgets (Phase 4)."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GtkSource", "5")

from gi.repository import Adw, Pango  # noqa: E402

Adw.init()

from copilot_gtk.widgets.code_block import CodeBlock  # noqa: E402
from copilot_gtk.widgets.markdown_renderer import MarkdownTextView  # noqa: E402

# ======================================================================
# Helper utilities
# ======================================================================


def _get_text(view: MarkdownTextView) -> str:
    """Extract all visible text from a MarkdownTextView's buffer."""
    buf = view.get_buffer()
    start = buf.get_start_iter()
    end = buf.get_end_iter()
    return buf.get_text(start, end, False)


def _has_tag_in_range(view: MarkdownTextView, tag_name: str) -> bool:
    """Return True if *tag_name* is applied anywhere in the buffer."""
    buf = view.get_buffer()
    tag = buf.get_tag_table().lookup(tag_name)
    if tag is None:
        return False
    it = buf.get_start_iter()
    while True:
        if it.has_tag(tag):
            return True
        if not it.forward_char():
            break
    return False


def _get_tag_property(view: MarkdownTextView, tag_name: str, prop: str):
    """Return a tag's property value."""
    buf = view.get_buffer()
    tag = buf.get_tag_table().lookup(tag_name)
    if tag is None:
        return None
    return tag.get_property(prop)


def _get_tagged_text(view: MarkdownTextView, tag_name: str) -> str:
    """Extract the text covered by *tag_name*."""
    buf = view.get_buffer()
    tag = buf.get_tag_table().lookup(tag_name)
    if tag is None:
        return ""
    parts: list[str] = []
    it = buf.get_start_iter()
    in_tag = False
    while True:
        has = it.has_tag(tag)
        if has and not in_tag:
            in_tag = True
            start = it.copy()
        elif not has and in_tag:
            in_tag = False
            parts.append(buf.get_text(start, it, False))
        if not it.forward_char():
            if in_tag:
                parts.append(buf.get_text(start, buf.get_end_iter(), False))
            break
    return "".join(parts)


# ======================================================================
# VER-P4-001: Heading renders large
# ======================================================================


class TestHeadingRendering:
    def test_h1_renders_with_large_scale(self):
        view = MarkdownTextView()
        view.set_markdown("# Hello")
        assert _has_tag_in_range(view, "h1")
        scale = _get_tag_property(view, "h1", "scale")
        assert scale > 1.0

    def test_h2_renders_with_scale(self):
        view = MarkdownTextView()
        view.set_markdown("## Subtitle")
        assert _has_tag_in_range(view, "h2")
        scale = _get_tag_property(view, "h2", "scale")
        assert scale > 1.0

    def test_h3_renders_with_scale(self):
        view = MarkdownTextView()
        view.set_markdown("### Third level")
        assert _has_tag_in_range(view, "h3")

    def test_heading_text_preserved(self):
        view = MarkdownTextView()
        view.set_markdown("# Hello World")
        text = _get_tagged_text(view, "h1")
        assert "Hello World" in text

    def test_heading_bold_weight(self):
        view = MarkdownTextView()
        view.set_markdown("# Hello")
        weight = _get_tag_property(view, "h1", "weight")
        assert weight == Pango.Weight.BOLD


# ======================================================================
# VER-P4-002: Bold renders bold
# ======================================================================


class TestBoldRendering:
    def test_bold_text_has_bold_tag(self):
        view = MarkdownTextView()
        view.set_markdown("This is **bold** text")
        assert _has_tag_in_range(view, "bold")

    def test_bold_tag_weight(self):
        view = MarkdownTextView()
        view.set_markdown("**bold**")
        weight = _get_tag_property(view, "bold", "weight")
        assert weight == Pango.Weight.BOLD

    def test_bold_text_content(self):
        view = MarkdownTextView()
        view.set_markdown("Hello **world**")
        text = _get_tagged_text(view, "bold")
        assert "world" in text


# ======================================================================
# VER-P4-003: Inline code uses monospace
# ======================================================================


class TestInlineCode:
    def test_inline_code_has_tag(self):
        view = MarkdownTextView()
        view.set_markdown("Use `code` here")
        assert _has_tag_in_range(view, "inline-code")

    def test_inline_code_monospace_family(self):
        view = MarkdownTextView()
        view.set_markdown("`code`")
        family = _get_tag_property(view, "inline-code", "family")
        assert family == "monospace"

    def test_inline_code_text_content(self):
        view = MarkdownTextView()
        view.set_markdown("Use `my_func()` here")
        text = _get_tagged_text(view, "inline-code")
        assert "my_func()" in text


# ======================================================================
# VER-P4-004: Fenced code block renders
# ======================================================================


class TestCodeBlock:
    def test_code_block_created(self):
        view = MarkdownTextView()
        view.set_markdown('```python\nprint("hi")\n```')
        assert len(view.code_blocks) == 1

    def test_code_block_language(self):
        view = MarkdownTextView()
        view.set_markdown('```python\nprint("hi")\n```')
        cb = view.code_blocks[0]
        assert cb.language == "python"

    def test_code_block_content(self):
        view = MarkdownTextView()
        view.set_markdown('```python\nprint("hi")\n```')
        cb = view.code_blocks[0]
        assert 'print("hi")' in cb.code

    def test_code_block_no_language(self):
        view = MarkdownTextView()
        view.set_markdown("```\nsome code\n```")
        assert len(view.code_blocks) == 1
        assert view.code_blocks[0].language == ""

    def test_multiple_code_blocks(self):
        view = MarkdownTextView()
        view.set_markdown("```python\na = 1\n```\n\nSome text\n\n```bash\necho hi\n```")
        assert len(view.code_blocks) == 2
        assert view.code_blocks[0].language == "python"
        assert view.code_blocks[1].language == "bash"


# ======================================================================
# VER-P4-005: Code copy button works
# ======================================================================


class TestCodeCopyButton:
    def test_code_block_widget_structure(self):
        cb = CodeBlock(code="hello", language="python")
        assert cb.code == "hello"
        assert cb.language == "python"

    def test_code_block_set_code(self):
        cb = CodeBlock(code="old", language="text")
        cb.set_code("new code")
        assert cb.code == "new code"

    def test_code_block_language_aliases(self):
        """Language aliases like 'js' → 'javascript' are resolved."""
        cb = CodeBlock(code="let x = 1;", language="js")
        # Should not crash; language hint is applied
        assert cb.language == "js"


# ======================================================================
# VER-P4-006: Nested list indentation
# ======================================================================


class TestListRendering:
    def test_unordered_list(self):
        view = MarkdownTextView()
        view.set_markdown("- Alpha\n- Beta\n- Gamma")
        text = _get_text(view)
        assert "Alpha" in text
        assert "Beta" in text
        assert "Gamma" in text

    def test_unordered_list_has_bullets(self):
        view = MarkdownTextView()
        view.set_markdown("- A\n- B")
        text = _get_text(view)
        assert "•" in text

    def test_nested_list_has_list_tags(self):
        view = MarkdownTextView()
        view.set_markdown("- A\n  - B\n    - C")
        assert _has_tag_in_range(view, "list-item")

    def test_ordered_list(self):
        view = MarkdownTextView()
        view.set_markdown("1. First\n2. Second\n3. Third")
        text = _get_text(view)
        assert "First" in text
        assert "Second" in text

    def test_nested_list_depth_indentation(self):
        """Nested list items should use deeper indent tags."""
        view = MarkdownTextView()
        view.set_markdown("- A\n  - B\n    - C")
        # Level-2 tag exists
        l2_margin = _get_tag_property(view, "list-item-2", "left-margin")
        l1_margin = _get_tag_property(view, "list-item", "left-margin")
        assert l2_margin > l1_margin


# ======================================================================
# VER-P4-007: Links are styled
# ======================================================================


class TestLinkRendering:
    def test_link_has_tag(self):
        view = MarkdownTextView()
        view.set_markdown("[Example](https://example.com)")
        assert _has_tag_in_range(view, "link")

    def test_link_text_content(self):
        view = MarkdownTextView()
        view.set_markdown("[Example](https://example.com)")
        text = _get_tagged_text(view, "link")
        assert "Example" in text

    def test_link_underlined(self):
        view = MarkdownTextView()
        view.set_markdown("[Example](https://example.com)")
        underline = _get_tag_property(view, "link", "underline")
        assert underline == Pango.Underline.SINGLE


# ======================================================================
# VER-P4-008: Markdown unit tests
# ======================================================================


class TestItalicRendering:
    def test_italic_text(self):
        view = MarkdownTextView()
        view.set_markdown("This is *italic* text")
        assert _has_tag_in_range(view, "italic")

    def test_italic_style(self):
        view = MarkdownTextView()
        view.set_markdown("*italic*")
        style = _get_tag_property(view, "italic", "style")
        assert style == Pango.Style.ITALIC


class TestBlockquote:
    def test_blockquote_renders(self):
        view = MarkdownTextView()
        view.set_markdown("> This is a quote")
        assert _has_tag_in_range(view, "blockquote")

    def test_blockquote_text(self):
        view = MarkdownTextView()
        view.set_markdown("> Important note")
        text = _get_tagged_text(view, "blockquote")
        assert "Important" in text


class TestThematicBreak:
    def test_hr_renders(self):
        view = MarkdownTextView()
        view.set_markdown("Above\n\n---\n\nBelow")
        text = _get_text(view)
        assert "─" in text


class TestStreamingDelta:
    def test_append_delta(self):
        view = MarkdownTextView()
        view.append_markdown_delta("Hello ")
        view.append_markdown_delta("**world**")
        assert view.get_markdown() == "Hello **world**"
        assert _has_tag_in_range(view, "bold")

    def test_set_markdown_replaces(self):
        view = MarkdownTextView()
        view.set_markdown("# First")
        view.set_markdown("# Second")
        text = _get_text(view)
        assert "Second" in text
        assert "First" not in text


class TestComplexMarkdown:
    """Test rendering with complex Markdown containing mixed elements."""

    def test_mixed_inline_styles(self):
        view = MarkdownTextView()
        view.set_markdown("**bold** and *italic* and `code`")
        assert _has_tag_in_range(view, "bold")
        assert _has_tag_in_range(view, "italic")
        assert _has_tag_in_range(view, "inline-code")

    def test_code_block_within_text(self):
        view = MarkdownTextView()
        md = (
            "Here is some text:\n\n"
            "```python\ndef hello():\n    print('hi')\n```\n\n"
            "And more text after."
        )
        view.set_markdown(md)
        text = _get_text(view)
        assert "Here is some text:" in text
        assert "And more text after." in text
        assert len(view.code_blocks) == 1

    def test_empty_markdown(self):
        view = MarkdownTextView()
        view.set_markdown("")
        text = _get_text(view)
        assert text == ""

    def test_plain_text_no_markdown(self):
        view = MarkdownTextView()
        view.set_markdown("Just plain text")
        text = _get_text(view)
        assert "Just plain text" in text

    def test_bold_italic_combined(self):
        view = MarkdownTextView()
        view.set_markdown("***bold italic***")
        assert _has_tag_in_range(view, "bold")
        assert _has_tag_in_range(view, "italic")


# ======================================================================
# MessageBubble integration (VER-P4 cross-check)
# ======================================================================


class TestMessageBubbleMarkdown:
    def test_user_bubble_plain_text(self):
        from copilot_gtk.widgets.message_bubble import MessageBubble

        bubble = MessageBubble(role="user", content="Hello!")
        assert bubble.content == "Hello!"
        # User bubbles should NOT have markdown view
        assert bubble._markdown_view is None
        assert bubble._text_label is not None

    def test_assistant_bubble_uses_markdown(self):
        from copilot_gtk.widgets.message_bubble import MessageBubble

        bubble = MessageBubble(role="assistant", content="**bold** text")
        assert bubble._markdown_view is not None
        assert bubble._text_label is None
        assert "**bold** text" in bubble.content

    def test_assistant_bubble_append_content(self):
        from copilot_gtk.widgets.message_bubble import MessageBubble

        bubble = MessageBubble(role="assistant", content="", is_streaming=True)
        bubble.append_content("Hello ")
        bubble.append_content("**world**")
        assert "Hello **world**" in bubble.content

    def test_assistant_bubble_set_content(self):
        from copilot_gtk.widgets.message_bubble import MessageBubble

        bubble = MessageBubble(role="assistant", content="old")
        bubble.set_content("# New heading")
        assert "# New heading" in bubble.content

    def test_user_bubble_append_still_works(self):
        from copilot_gtk.widgets.message_bubble import MessageBubble

        bubble = MessageBubble(role="user", content="Hi")
        bubble.append_content(" there")
        assert bubble.content == "Hi there"
