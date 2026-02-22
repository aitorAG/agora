"""Rol CrewAI: Observer. Evalúa quién debe hablar y si el jugador cumplió su misión (game_ended)."""

from typing import Dict, Any, List

from ..agents.observer import ObserverAgent, parse_mission_evaluation_response, normalize_who_should_respond
from ..state import ConversationState


def create_observer_agent(
    actor_names: List[str] | None = None,
    player_mission: str | None = None,
    model: str = "deepseek-chat",
) -> ObserverAgent:
    """Crea el agente Observer (rol CrewAI)."""
    return ObserverAgent(
        name="Observer",
        model=model,
        actor_names=actor_names or [],
        player_mission=player_mission or "",
    )


def run_observer_tasks(agent: ObserverAgent, state: ConversationState) -> Dict[str, Any]:
    """Ejecuta las tareas del Observer: continuación (quién habla) y evaluación de misiones.
    Salida: continuation_decision, mission_evaluation, game_ended, game_ended_reason, analysis, update_metadata.
    """
    return agent.process(state)


__all__ = [
    "create_observer_agent",
    "run_observer_tasks",
    "parse_mission_evaluation_response",
    "normalize_who_should_respond",
]
