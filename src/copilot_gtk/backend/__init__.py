# SPDX-License-Identifier: GPL-3.0-or-later
"""Backend package — Copilot SDK integration layer."""

from .async_bridge import install_async_bridge, run_async  # noqa: F401
from .auth_manager import AuthManager  # noqa: F401
from .conversation import Conversation  # noqa: F401
from .conversation_store import ConversationStore  # noqa: F401
from .copilot_service import CopilotService  # noqa: F401
from .message import Message, MessageRole  # noqa: F401
from .mock_copilot_service import MockCopilotService, create_service  # noqa: F401
