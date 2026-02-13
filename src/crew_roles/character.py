"""Rol CrewAI: Character. Genera la respuesta de un personaje dado el historial y su identidad."""

from typing import Dict, Any

from ..agents.character import CharacterAgent
from ..state import ConversationState


def create_character_agent(
    name: str,
    personality: str,
    mission: str | None = None,
    background: str | None = None,
    model: str = "deepseek-chat",
) -> CharacterAgent:
    """Crea un agente Character (rol CrewAI) para un personaje."""
    return CharacterAgent(
        name=name,
        personality=personality,
        mission=mission,
        background=background,
        model=model,
    )


def run_character_response(
    agent: CharacterAgent,
    state: ConversationState,
    stream: bool = False,
    stream_sink: Any = None,
) -> Dict[str, Any]:
    """Ejecuta la tarea de generar respuesta. Entrada: state. Salida: dict con message, author o error (y opcionalmente displayed)."""
    return agent.process(state, stream=stream, stream_sink=stream_sink)
