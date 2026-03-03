# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for MockCopilotService."""

import os
from unittest.mock import MagicMock

import gi
import pytest

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Adw, GLib  # noqa: E402

Adw.init()

from copilot_gtk.backend.mock_copilot_service import (  # noqa: E402
    MockCopilotService,
    _MockModelInfo,
    create_service,
    is_mock_backend_enabled,
)


class TestMockModelInfo:
    """Tests for _MockModelInfo."""

    def test_creation(self):
        m = _MockModelInfo("gpt-4o", "GPT-4o")
        assert m.id == "gpt-4o"
        assert m.name == "GPT-4o"

    def test_repr(self):
        m = _MockModelInfo("gpt-4o", "GPT-4o")
        assert "gpt-4o" in repr(m)
        assert "GPT-4o" in repr(m)


class TestIsMockBackendEnabled:
    """Tests for environment variable detection."""

    def test_enabled_with_1(self):
        os.environ["COPILOT_GTK_MOCK_BACKEND"] = "1"
        assert is_mock_backend_enabled() is True
        del os.environ["COPILOT_GTK_MOCK_BACKEND"]

    def test_enabled_with_true(self):
        os.environ["COPILOT_GTK_MOCK_BACKEND"] = "true"
        assert is_mock_backend_enabled() is True
        del os.environ["COPILOT_GTK_MOCK_BACKEND"]

    def test_enabled_with_yes(self):
        os.environ["COPILOT_GTK_MOCK_BACKEND"] = "yes"
        assert is_mock_backend_enabled() is True
        del os.environ["COPILOT_GTK_MOCK_BACKEND"]

    def test_disabled_with_0(self):
        os.environ["COPILOT_GTK_MOCK_BACKEND"] = "0"
        assert is_mock_backend_enabled() is False
        del os.environ["COPILOT_GTK_MOCK_BACKEND"]

    def test_disabled_when_unset(self):
        os.environ.pop("COPILOT_GTK_MOCK_BACKEND", None)
        assert is_mock_backend_enabled() is False


class TestCreateService:
    """Tests for the create_service factory."""

    def test_returns_mock_when_enabled(self):
        os.environ["COPILOT_GTK_MOCK_BACKEND"] = "1"
        svc = create_service()
        assert isinstance(svc, MockCopilotService)
        del os.environ["COPILOT_GTK_MOCK_BACKEND"]

    def test_returns_real_when_disabled(self):
        os.environ.pop("COPILOT_GTK_MOCK_BACKEND", None)
        svc = create_service()
        from copilot_gtk.backend.copilot_service import CopilotService
        assert isinstance(svc, CopilotService)


class TestMockCopilotService:
    """Tests for MockCopilotService."""

    def test_initial_state(self):
        svc = MockCopilotService()
        assert svc.conversations == {}
        assert svc.models == []

    def test_stop_clears_conversations(self):
        svc = MockCopilotService()
        svc._conversations["test"] = MagicMock()
        svc.stop()
        assert svc.conversations == {}
        assert svc._started is False

    def test_list_models_populates(self):
        svc = MockCopilotService()
        handler = MagicMock()
        svc.connect("models-loaded", handler)
        svc.list_models()

        # Models are loaded synchronously into _models
        assert len(svc._models) == 3
        assert svc._models[0].id == "gpt-4o"

    def test_create_conversation_adds_to_dict(self):
        svc = MockCopilotService()
        idle_handler = MagicMock()
        svc.connect("session-idle", idle_handler)

        svc.create_conversation("gpt-4o")

        # Conversation should be created immediately (before GLib.idle fires)
        convs = svc.conversations
        assert len(convs) == 1
        sid = list(convs.keys())[0]
        assert sid.startswith("mock-")
        assert convs[sid].model == "gpt-4o"

    def test_create_conversation_default_model(self):
        svc = MockCopilotService()
        svc.create_conversation()

        convs = svc.conversations
        assert len(convs) == 1
        sid = list(convs.keys())[0]
        assert convs[sid].model == "gpt-4o"

    def test_send_message_adds_messages(self):
        svc = MockCopilotService()
        svc.create_conversation("gpt-4o")

        sid = list(svc.conversations.keys())[0]
        svc.send_message(sid, "Hello!")

        conv = svc._conversations[sid]
        assert len(conv.messages) == 2  # user + assistant placeholder
        assert conv.messages[0].role.value == "user"
        assert conv.messages[0].content == "Hello!"
        assert conv.messages[1].role.value == "assistant"

    def test_send_message_unknown_session_emits_error(self):
        svc = MockCopilotService()
        handler = MagicMock()
        svc.connect("error", handler)

        svc.send_message("nonexistent", "Hello!")

        handler.assert_called_once()

    def test_send_message_with_mock_error(self):
        os.environ["COPILOT_GTK_MOCK_ERROR"] = "Test error"
        svc = MockCopilotService()
        svc.create_conversation()

        sid = list(svc.conversations.keys())[0]
        # This should schedule an error emission, not a response
        svc.send_message(sid, "trigger error")

        # Messages still get added to the model
        conv = svc._conversations[sid]
        assert len(conv.messages) == 2

        del os.environ["COPILOT_GTK_MOCK_ERROR"]

    def test_abort_session(self):
        svc = MockCopilotService()
        idle_handler = MagicMock()
        svc.connect("session-idle", idle_handler)

        svc.create_conversation()
        sid = list(svc.conversations.keys())[0]

        # abort should not crash
        svc.abort_session(sid)

    def test_destroy_conversation(self):
        svc = MockCopilotService()
        svc.create_conversation()

        sid = list(svc.conversations.keys())[0]
        svc.destroy_conversation(sid)

        assert sid not in svc._conversations

    def test_check_auth_status(self):
        svc = MockCopilotService()
        handler = MagicMock()
        svc.connect("auth-status", handler)
        svc.check_auth_status()
        # Signal is emitted via GLib.idle_add, so can't verify sync

    def test_split_into_chunks(self):
        chunks = MockCopilotService._split_into_chunks("Hello World!", 3)
        assert len(chunks) == 3
        assert "".join(chunks) == "Hello World!"

    def test_split_into_one_chunk(self):
        chunks = MockCopilotService._split_into_chunks("Hello", 1)
        assert chunks == ["Hello"]

    def test_get_response_text_default(self):
        svc = MockCopilotService()
        text = svc._get_response_text("anything")
        assert "mock" in text.lower()

    def test_get_response_text_from_env(self):
        os.environ["COPILOT_GTK_MOCK_RESPONSE"] = "Custom response"
        svc = MockCopilotService()
        text = svc._get_response_text("anything")
        assert text == "Custom response"
        del os.environ["COPILOT_GTK_MOCK_RESPONSE"]

    def test_signals_match_copilot_service(self):
        """MockCopilotService should have the same signal set as CopilotService."""
        from copilot_gtk.backend.copilot_service import CopilotService

        mock_signals = set(MockCopilotService.__gsignals__.keys())
        real_signals = set(CopilotService.__gsignals__.keys())
        assert mock_signals == real_signals, (
            f"Signal mismatch! "
            f"Mock-only: {mock_signals - real_signals}, "
            f"Real-only: {real_signals - mock_signals}"
        )
