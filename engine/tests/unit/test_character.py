"""Tests unitarios del CharacterAgent (stream=False y stream=True)."""

import pytest
from unittest.mock import patch, MagicMock

from src.agents.character import CharacterAgent
from src.state import ConversationState


@pytest.fixture
def sample_state() -> ConversationState:
    """Estado mínimo para que el agente construya mensajes."""
    return {
        "messages": [
            {"author": "Usuario", "content": "Hola.", "timestamp": None, "turn": 0},
        ],
        "turn": 1,
        "metadata": {},
    }


@pytest.fixture
def agent() -> CharacterAgent:
    """CharacterAgent de prueba."""
    return CharacterAgent(
        name="Test",
        personality="Amable.",
        model="deepseek-chat",
    )


def test_character_process_stream_false_returns_message_and_author(
    agent: CharacterAgent, sample_state: ConversationState
):
    """Con stream=False, process devuelve message y author sin displayed."""
    with patch("src.agents.character.send_message", return_value="Respuesta completa."):
        result = agent.process(sample_state, stream=False)
    assert result["message"] == "Respuesta completa."
    assert result["author"] == "Test"
    assert "displayed" not in result or result.get("displayed") is not True


def test_character_process_stream_true_returns_concatenated_and_displayed(
    agent: CharacterAgent, sample_state: ConversationState
):
    """Con stream=True, process devuelve texto concatenado y displayed=True."""
    chunks = ["Hi ", "there."]

    with patch("src.agents.character.send_message", return_value=iter(chunks)):
        with patch("src.agents.character.sys.stdout") as mock_stdout:
            mock_stdout.write = MagicMock()
            mock_stdout.flush = MagicMock()
            result = agent.process(sample_state, stream=True)

    assert result["message"] == "Hi there."
    assert result["author"] == "Test"
    assert result.get("displayed") is True
    # Debe haber escrito el prefijo y los chunks en stdout
    assert mock_stdout.write.called
    assert mock_stdout.flush.called
