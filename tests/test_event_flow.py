# SPDX-License-Identifier: GPL-3.0-or-later
"""Integration tests for the complete event flow from service signals to UI.

These tests simulate the exact SDK event sequences observed in production
(e.g. multi-turn tool-call flows, reasoning-only turns) and verify that
the UI ends up in the correct state — without a live Copilot backend.
"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw  # noqa: E402

Adw.init()

from copilot_gtk.backend.conversation import Conversation  # noqa: E402
from copilot_gtk.backend.message import Message, MessageRole  # noqa: E402
from copilot_gtk.window import CopilotWindow  # noqa: E402

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _make_mock_service():
    """Create a bare CopilotService (no SDK) with GObject signals."""
    from copilot_gtk.backend.copilot_service import CopilotService

    service = CopilotService.__new__(CopilotService)
    CopilotService.__init__(service)
    return service


def _setup_active_session(service, win, session_id="s1", model="gpt-4"):
    """Create a conversation and select it so the window is in chat mode."""
    conv = Conversation(session_id=session_id, title="New Chat", model=model)
    service._conversations[session_id] = conv
    win._on_session_idle(service, session_id)
    assert win._current_session_id == session_id
    assert win._content_stack.get_visible_child_name() == "chat"
    return conv


def _simulate_user_sends(win, service, session_id, text):
    """Simulate the user pressing Send (adds bubbles + starts loading)."""
    win._chat_view.add_user_message(text)
    win._chat_view.add_assistant_placeholder()
    # The real window also calls service.send_message(), but we're
    # driving signals manually, so skip that.

    # Simulate the conversation model side (normally done by send_message)
    conv = service._conversations[session_id]
    conv.add_message(Message(role=MessageRole.USER, content=text))
    conv.add_message(Message(role=MessageRole.ASSISTANT, content="", is_streaming=True))


def _get_last_bubble(win):
    """Return the last MessageBubble in the chat view."""
    child = win._chat_view._message_box.get_first_child()
    last = None
    while child is not None:
        last = child
        child = child.get_next_sibling()
    return last


def _count_bubbles(win):
    """Count the number of bubbles in the chat view."""
    count = 0
    child = win._chat_view._message_box.get_first_child()
    while child is not None:
        count += 1
        child = child.get_next_sibling()
    return count


# ------------------------------------------------------------------
# Test: Simple single-turn response
# ------------------------------------------------------------------


class TestSingleTurnFlow:
    """Standard flow: user message → streaming deltas → response-complete → idle."""

    def test_deltas_appear_in_bubble(self):
        service = _make_mock_service()
        win = CopilotWindow(service=service)
        _setup_active_session(service, win)

        _simulate_user_sends(win, service, "s1", "Hello")

        # Turn start → loading
        win._on_turn_start(service, "s1")

        # Stream content
        win._on_response_chunk(service, "s1", "Hi ")
        win._on_response_chunk(service, "s1", "there!")

        bubble = _get_last_bubble(win)
        assert bubble.content == "Hi there!"
        assert bubble.is_streaming is True

    def test_response_complete_finalises_bubble(self):
        service = _make_mock_service()
        win = CopilotWindow(service=service)
        _setup_active_session(service, win)

        _simulate_user_sends(win, service, "s1", "Hello")
        win._on_turn_start(service, "s1")
        win._on_response_chunk(service, "s1", "Hi there!")
        win._on_response_complete(service, "s1", "Hi there!")

        bubble = _get_last_bubble(win)
        assert bubble.content == "Hi there!"
        assert bubble.is_streaming is False

    def test_session_idle_stops_loading(self):
        service = _make_mock_service()
        win = CopilotWindow(service=service)
        _setup_active_session(service, win)

        _simulate_user_sends(win, service, "s1", "Hello")
        win._on_turn_start(service, "s1")
        win._chat_input.set_loading(True)

        win._on_response_chunk(service, "s1", "Hi!")
        win._on_response_complete(service, "s1", "Hi!")
        win._on_turn_end(service, "s1")
        win._on_session_idle(service, "s1")

        assert win._chat_input._is_loading is False


# ------------------------------------------------------------------
# Test: Multi-turn tool-call flow
# ------------------------------------------------------------------


class TestMultiTurnToolCallFlow:
    """Flow with tool calls: Turn 1 sends empty ASSISTANT_MESSAGE (tool call),
    Turn 2 streams the actual answer.

    This is the flow that was broken:
      TURN_START → REASONING_DELTA… → empty ASSISTANT_MESSAGE → TOOL_…
      → TURN_END → TURN_START → MESSAGE_DELTA… → ASSISTANT_MESSAGE
      → TURN_END → SESSION_IDLE
    """

    def test_empty_response_complete_does_not_kill_bubble(self):
        """An empty response-complete (tool-call turn) must NOT finalize the bubble."""
        service = _make_mock_service()
        win = CopilotWindow(service=service)
        _setup_active_session(service, win)

        _simulate_user_sends(win, service, "s1", "What time is it?")

        # Turn 1: reasoning → empty ASSISTANT_MESSAGE (tool call)
        win._on_turn_start(service, "s1")
        # No response-chunk arrives (only reasoning deltas, handled by service)
        # response-complete is NOT emitted for empty ASSISTANT_MESSAGE
        # (service skips it), so turn-end fires directly
        win._on_turn_end(service, "s1")

        # Bubble should still be streaming (waiting for the real answer)
        bubble = _get_last_bubble(win)
        assert bubble.is_streaming is True
        assert win._chat_view._streaming_bubble is not None

    def test_full_multi_turn_produces_correct_result(self):
        """Complete multi-turn flow ends with content in the bubble."""
        service = _make_mock_service()
        win = CopilotWindow(service=service)
        _setup_active_session(service, win)

        _simulate_user_sends(win, service, "s1", "What time is it?")

        # Turn 1: tool call (no visible content)
        win._on_turn_start(service, "s1")
        win._on_turn_end(service, "s1")

        # Turn 2: the real answer streams in
        win._on_turn_start(service, "s1")
        win._on_response_chunk(service, "s1", "It's ")
        win._on_response_chunk(service, "s1", "3:00 PM.")
        win._on_response_complete(service, "s1", "It's 3:00 PM.")
        win._on_turn_end(service, "s1")

        # Session completes
        win._on_session_idle(service, "s1")

        bubble = _get_last_bubble(win)
        assert bubble.content == "It's 3:00 PM."
        assert bubble.is_streaming is False
        assert win._chat_view._streaming_bubble is None
        assert win._chat_input._is_loading is False

    def test_three_turn_tool_chain(self):
        """Three turns: tool call → tool call → answer."""
        service = _make_mock_service()
        win = CopilotWindow(service=service)
        _setup_active_session(service, win)

        _simulate_user_sends(win, service, "s1", "Complex query")

        # Turn 1: tool call
        win._on_turn_start(service, "s1")
        win._on_turn_end(service, "s1")

        # Turn 2: another tool call
        win._on_turn_start(service, "s1")
        win._on_turn_end(service, "s1")

        # Bubble still alive
        assert win._chat_view._streaming_bubble is not None

        # Turn 3: actual answer
        win._on_turn_start(service, "s1")
        win._on_response_chunk(service, "s1", "Here is the answer.")
        win._on_response_complete(service, "s1", "Here is the answer.")
        win._on_turn_end(service, "s1")
        win._on_session_idle(service, "s1")

        bubble = _get_last_bubble(win)
        assert bubble.content == "Here is the answer."
        assert bubble.is_streaming is False

    def test_loading_stays_on_between_turns(self):
        """Loading indicator should not flicker off between turns."""
        service = _make_mock_service()
        win = CopilotWindow(service=service)
        _setup_active_session(service, win)

        _simulate_user_sends(win, service, "s1", "Query")
        win._on_turn_start(service, "s1")
        win._chat_input.set_loading(True)

        # Turn 1 ends — loading should NOT stop
        win._on_turn_end(service, "s1")
        # turn_end no longer calls set_loading(False)
        # turn_start re-sets it:
        win._on_turn_start(service, "s1")

        # Turn 2 streams content
        win._on_response_chunk(service, "s1", "Done.")
        win._on_response_complete(service, "s1", "Done.")
        win._on_turn_end(service, "s1")

        # Only session_idle stops loading
        win._on_session_idle(service, "s1")
        assert win._chat_input._is_loading is False


# ------------------------------------------------------------------
# Test: Reasoning-only turn (no ASSISTANT_MESSAGE content)
# ------------------------------------------------------------------


class TestReasoningOnlyFlow:
    """Models that emit only reasoning deltas and no ASSISTANT_MESSAGE.

    The safety net in SESSION_IDLE should finalize the streaming message
    at the conversation model level, and the window's _on_session_idle
    should finalize the UI bubble.
    """

    def test_session_idle_finalises_orphan_bubble(self):
        """SESSION_IDLE finalises a bubble that never got response-complete."""
        service = _make_mock_service()
        win = CopilotWindow(service=service)
        _setup_active_session(service, win)

        _simulate_user_sends(win, service, "s1", "Think hard")

        win._on_turn_start(service, "s1")
        # Only reasoning deltas arrive (handled internally by service)
        # No response-chunk or response-complete ever fires
        win._on_turn_end(service, "s1")
        win._on_session_idle(service, "s1")

        # The bubble should show the "no response" error
        bubble = _get_last_bubble(win)
        assert bubble.is_streaming is False
        assert "⚠" in bubble.content
        assert win._chat_view._streaming_bubble is None

    def test_reasoning_then_content_in_same_turn(self):
        """Reasoning deltas followed by content deltas in the same turn."""
        service = _make_mock_service()
        win = CopilotWindow(service=service)
        _setup_active_session(service, win)

        _simulate_user_sends(win, service, "s1", "Hello")

        win._on_turn_start(service, "s1")
        # Reasoning happens (service handles internally, no UI emission)
        # Then content arrives
        win._on_response_chunk(service, "s1", "Hello! ")
        win._on_response_chunk(service, "s1", "How can I help?")
        win._on_response_complete(service, "s1", "Hello! How can I help?")
        win._on_turn_end(service, "s1")
        win._on_session_idle(service, "s1")

        bubble = _get_last_bubble(win)
        assert bubble.content == "Hello! How can I help?"
        assert bubble.is_streaming is False


# ------------------------------------------------------------------
# Test: Error during streaming
# ------------------------------------------------------------------


class TestErrorDuringStreaming:
    """Errors that arrive while a streaming bubble is active."""

    def test_error_replaces_empty_bubble(self):
        """A service error on an empty bubble shows the error inline."""
        service = _make_mock_service()
        win = CopilotWindow(service=service)
        _setup_active_session(service, win)

        _simulate_user_sends(win, service, "s1", "Hello")
        win._on_turn_start(service, "s1")

        # Error before any content
        win._on_service_error(service, "Rate limit exceeded")

        bubble = _get_last_bubble(win)
        assert "Rate limit exceeded" in bubble.content
        assert bubble.has_css_class("error-bubble")
        assert win._chat_input._is_loading is False

    def test_error_after_partial_content(self):
        """A service error after some content still shows the error."""
        service = _make_mock_service()
        win = CopilotWindow(service=service)
        _setup_active_session(service, win)

        _simulate_user_sends(win, service, "s1", "Hello")
        win._on_turn_start(service, "s1")
        win._on_response_chunk(service, "s1", "Starting to answer...")

        win._on_service_error(service, "Connection lost")

        bubble = _get_last_bubble(win)
        assert "Connection lost" in bubble.content
        assert win._chat_input._is_loading is False

    def test_error_with_no_streaming_bubble(self):
        """A service error when there's no active bubble creates one."""
        service = _make_mock_service()
        win = CopilotWindow(service=service)
        _setup_active_session(service, win)

        # Error fires without a preceding user message
        win._on_service_error(service, "Authentication expired")

        # Should show error in a new bubble
        bubble = _get_last_bubble(win)
        assert bubble is not None
        assert "Authentication expired" in bubble.content


# ------------------------------------------------------------------
# Test: Cross-session isolation
# ------------------------------------------------------------------


class TestCrossSessionIsolation:
    """Events for non-active sessions must not affect the current view."""

    def test_chunk_for_other_session_ignored(self):
        service = _make_mock_service()
        win = CopilotWindow(service=service)
        _setup_active_session(service, win, session_id="s1")

        _simulate_user_sends(win, service, "s1", "Hello")
        win._on_turn_start(service, "s1")

        # Chunk arrives for a different session
        win._on_response_chunk(service, "s2", "Wrong session content")

        bubble = _get_last_bubble(win)
        assert bubble.content == ""  # still empty, only s1's content matters

    def test_session_idle_for_other_session_no_effect(self):
        service = _make_mock_service()
        win = CopilotWindow(service=service)
        _setup_active_session(service, win, session_id="s1")

        # Pre-register s2 in sidebar so _on_session_idle won't auto-select it
        conv2 = Conversation(session_id="s2")
        service._conversations["s2"] = conv2
        win._conversation_list.add_conversation(conv2)

        _simulate_user_sends(win, service, "s1", "Hello")
        win._on_turn_start(service, "s1")
        win._chat_input.set_loading(True)

        # session-idle for s2 — should NOT touch s1's loading state
        win._on_session_idle(service, "s2")

        assert win._current_session_id == "s1"
        assert win._chat_input._is_loading is True


# ------------------------------------------------------------------
# Test: Double finish_streaming is safe
# ------------------------------------------------------------------


class TestIdempotentFinish:
    """Calling finish_streaming multiple times should be harmless."""

    def test_double_finish_streaming(self):
        service = _make_mock_service()
        win = CopilotWindow(service=service)
        _setup_active_session(service, win)

        _simulate_user_sends(win, service, "s1", "Hello")
        win._on_turn_start(service, "s1")
        win._on_response_chunk(service, "s1", "Content")
        win._on_response_complete(service, "s1", "Content")

        # session_idle calls finish_streaming again — should be a no-op
        win._on_session_idle(service, "s1")

        bubble = _get_last_bubble(win)
        assert bubble.content == "Content"
        assert bubble.is_streaming is False

    def test_finish_then_idle_no_duplicate_bubble(self):
        """session_idle after response_complete should not create extra bubbles."""
        service = _make_mock_service()
        win = CopilotWindow(service=service)
        _setup_active_session(service, win)

        _simulate_user_sends(win, service, "s1", "Hello")
        win._on_response_chunk(service, "s1", "Done")
        win._on_response_complete(service, "s1", "Done")
        win._on_session_idle(service, "s1")

        # Should have exactly 2 bubbles: user + assistant
        assert _count_bubbles(win) == 2
