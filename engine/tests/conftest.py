"""Fixtures compartidos para tests."""

import pytest
from src.manager import ConversationManager
from src.state import ConversationState


@pytest.fixture
def manager():
    """ConversationManager vacío."""
    return ConversationManager()


@pytest.fixture
def sample_state() -> ConversationState:
    """Estado de conversación de ejemplo con mensajes y metadata."""
    return {
        "messages": [
            {"author": "Alice", "content": "Hola.", "timestamp": None, "turn": 0},
            {"author": "Usuario", "content": "Hola Alice.", "timestamp": None, "turn": 0},
        ],
        "turn": 1,
        "metadata": {"continuation_decision": {"needs_response": False, "who_should_respond": "none"}},
    }
