"""Rol CrewAI: Guionista. Genera el setup inicial de la partida (ambientación, actores, misión del jugador)."""

from typing import Dict, Any

from ..agents.guionista import GuionistaAgent
from ..state import ConversationState


def create_guionista_agent(model: str = "deepseek-chat") -> GuionistaAgent:
    """Crea el agente Guionista (rol CrewAI)."""
    return GuionistaAgent(name="Guionista", model=model)


def run_setup_task(
    agent: GuionistaAgent,
    theme: str | None = None,
    num_actors: int = 3,
) -> Dict[str, Any]:
    """Ejecuta la tarea de generar setup. Entrada: theme, num_actors. Salida: game_setup dict."""
    return agent.generate_setup(theme=theme, num_actors=num_actors)


def default_setup(num_actors: int) -> Dict[str, Any]:
    """Setup por defecto si el LLM falla. Expuesto para tests."""
    from ..agents.guionista import _default_setup
    return _default_setup(num_actors)
