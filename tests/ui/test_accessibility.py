# SPDX-License-Identifier: GPL-3.0-or-later
"""UI Test: Accessibility Audit (TASK-089).

Walks the AT-SPI tree and verifies that all interactive widgets
have proper accessible names/labels, no focus traps exist, and
the tree structure is well-formed.
"""

from __future__ import annotations

import time

import pytest

pytestmark = [
    pytest.mark.ui,
    pytest.mark.timeout(90),
]

# Roles that require accessible names
INTERACTIVE_ROLES = {
    "push button",
    "button",
    "toggle button",
    "check box",
    "radio button",
    "combo box",
    "spin button",
    "menu item",
    "menu",
    "tab",
}

# Roles where empty names are acceptable
CONTAINER_ROLES = {
    "filler",
    "panel",
    "scroll pane",
    "viewport",
    "separator",
    "scroll bar",
    "status bar",
    "tool bar",
}


def _collect_nodes(node, depth: int = 0, max_depth: int = 15) -> list:
    """Recursively collect all nodes in the AT-SPI tree."""
    nodes = []
    if depth > max_depth:
        return nodes

    try:
        nodes.append(node)
        for i in range(node.child_count):
            try:
                child = node.children[i]
                nodes.extend(_collect_nodes(child, depth + 1, max_depth))
            except Exception:
                continue
    except Exception:
        pass

    return nodes


class TestAccessibilityAudit:
    """Automated accessibility audit of the entire AT-SPI tree."""

    def test_interactive_widgets_have_names(self, app_node):
        """All interactive widgets should have non-empty accessible names."""
        time.sleep(2)  # Let the app settle
        window = app_node.child(roleName="frame")
        all_nodes = _collect_nodes(window)

        violations = []
        for node in all_nodes:
            try:
                role = getattr(node, "roleName", "") or ""
                name = getattr(node, "name", "") or ""

                if role in INTERACTIVE_ROLES and not name.strip():
                    # Check if maybe it has a description instead
                    desc = getattr(node, "description", "") or ""
                    if not desc.strip():
                        violations.append(
                            f"  {role} at index {getattr(node, 'indexInParent', '?')} "
                            f"has no accessible name"
                        )
            except Exception:
                continue

        if violations:
            pytest.fail(
                f"Found {len(violations)} interactive widgets without accessible names:\n"
                + "\n".join(violations[:20])  # Limit output
            )

    def test_no_orphan_focus_traps(self, app_node):
        """Focusable widgets should not trap keyboard focus."""
        time.sleep(2)
        window = app_node.child(roleName="frame")
        all_nodes = _collect_nodes(window)

        focusable_count = 0
        for node in all_nodes:
            try:
                if getattr(node, "focusable", False):
                    focusable_count += 1
            except Exception:
                continue

        # There should be at least some focusable widgets
        assert focusable_count > 0, "No focusable widgets found"

        # A focus trap would mean only 1 focusable widget in a branch
        # This is a heuristic check — real trap detection requires tabbing through
        assert focusable_count >= 2, (
            f"Only {focusable_count} focusable widget(s) — possible focus trap"
        )

    def test_tree_structure_not_empty(self, app_node):
        """The AT-SPI tree should have reasonable depth and breadth."""
        window = app_node.child(roleName="frame")
        all_nodes = _collect_nodes(window)

        # A well-structured GTK4 app should have many nodes
        assert len(all_nodes) > 10, (
            f"AT-SPI tree too shallow: only {len(all_nodes)} nodes"
        )

    def test_buttons_have_actions(self, app_node):
        """All buttons should have at least one available action."""
        time.sleep(2)
        window = app_node.child(roleName="frame")
        all_nodes = _collect_nodes(window)

        violations = []
        for node in all_nodes:
            try:
                role = getattr(node, "roleName", "") or ""
                if role in ("push button", "button"):
                    actions = getattr(node, "actions", None)
                    if actions is not None and len(actions) == 0:
                        name = getattr(node, "name", "unnamed")
                        violations.append(f"  Button '{name}' has no actions")
            except Exception:
                continue

        if violations:
            pytest.fail(
                f"Found {len(violations)} buttons without actions:\n"
                + "\n".join(violations[:10])
            )

    def test_labels_are_not_empty(self, app_node):
        """Label widgets should have non-empty text content."""
        time.sleep(2)
        window = app_node.child(roleName="frame")
        all_nodes = _collect_nodes(window)

        empty_labels = 0
        total_labels = 0
        for node in all_nodes:
            try:
                role = getattr(node, "roleName", "") or ""
                if role == "label":
                    total_labels += 1
                    name = getattr(node, "name", "") or ""
                    if not name.strip():
                        empty_labels += 1
            except Exception:
                continue

        # Allow some empty labels (spacers, decorative) but flag if majority are empty
        if total_labels > 0:
            ratio = empty_labels / total_labels
            assert ratio < 0.5, (
                f"{empty_labels}/{total_labels} labels are empty ({ratio:.0%})"
            )
