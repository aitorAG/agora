"""Director: orquestador central. Gestiona el flujo de turnos, llama a Guionista, Character y Observer."""

from typing import Literal, Any

from ..state import ConversationState
from ..manager import ConversationManager
from ..io_adapters import InputProvider, OutputHandler

from .guionista import run_setup_task
from .character import run_character_response
from .observer import run_observer_tasks


def route_continuation(
    continuation_decision: dict,
    character_agent_names: list[str],
) -> Literal["character", "user_input", "continue"]:
    """Decide el siguiente paso tras el observer. Si no hay respuesta necesaria o who=none, se da palabra al usuario."""
    if not continuation_decision.get("needs_response", False):
        return "user_input"
    who_should_respond = continuation_decision.get("who_should_respond", "none")
    if who_should_respond == "user":
        return "user_input"
    if who_should_respond == "character" or who_should_respond in character_agent_names:
        return "character"
    return "user_input"


def route_should_continue(state: ConversationState, max_turns: int) -> Literal["continue", "end"]:
    """Decide si continuar al siguiente turno o terminar."""
    if state.get("metadata", {}).get("user_exit", False):
        return "end"
    if state["turn"] >= max_turns:
        return "end"
    return "continue"


def _messages_since_user(messages: list) -> int:
    """Cuenta cuántos mensajes consecutivos al final del historial no son del Usuario."""
    count = 0
    for msg in reversed(messages):
        if msg.get("author") == "Usuario":
            break
        count += 1
    return count


def run_game_loop(
    manager: ConversationManager,
    character_agents: dict[str, Any],
    observer_agent: Any,
    max_turns: int,
    *,
    input_provider: InputProvider,
    output_handler: OutputHandler,
    max_messages_before_user: int = 3,
) -> ConversationState:
    """Ejecuta el bucle de partida hasta fin (game_ended, max_turns o user_exit).
    Si no se sabe quién debe hablar se da palabra al usuario. Cada max_messages_before_user
    intervenciones no-usuario se fuerza user_input (0 = desactivado).
    """
    agent_names_ordered = list(character_agents.keys())
    next_action: Literal["character", "user_input"] = "character"

    while True:
        if next_action == "character":
            state = manager.state
            continuation_decision = state.get("metadata", {}).get("continuation_decision", {})
            who = continuation_decision.get("who_should_respond", "")
            if who and who in character_agents:
                agent = character_agents[who]
            else:
                agent = character_agents[agent_names_ordered[0]]
            result = run_character_response(agent, state)
            if "error" in result:
                output_handler.on_error(f"Error en {agent.name}: {result['error']}")
                return manager.state
            manager.add_message(result["author"], result["message"])
            output_handler.on_message(manager.state["messages"][-1])

        else:
            assert next_action == "user_input"
            user_result = input_provider.get_user_input()
            if user_result.user_exit:
                manager.update_metadata("user_exit", True)
                return manager.state
            if user_result.text and user_result.text.strip():
                manager.add_message("Usuario", user_result.text.strip())
                manager.increment_turn()

        state = manager.state
        obs_result = run_observer_tasks(observer_agent, state)
        if obs_result.get("update_metadata"):
            if obs_result.get("analysis") is not None:
                manager.update_metadata(f"turn_{state['turn']}_analysis", obs_result["analysis"])
        if obs_result.get("continuation_decision"):
            manager.update_metadata("continuation_decision", obs_result["continuation_decision"])
        if obs_result.get("mission_evaluation") is not None:
            manager.update_metadata("last_mission_evaluation", obs_result["mission_evaluation"])
            manager.update_metadata(f"turn_{state['turn']}_mission_evaluation", obs_result["mission_evaluation"])
        if "game_ended" in obs_result:
            manager.update_metadata("game_ended", obs_result["game_ended"])
        if "game_ended_reason" in obs_result:
            manager.update_metadata("game_ended_reason", obs_result["game_ended_reason"])
        state = manager.state

        if state.get("metadata", {}).get("game_ended", False):
            reason = state.get("metadata", {}).get("game_ended_reason", "")
            evaluation = state.get("metadata", {}).get("last_mission_evaluation", {})
            output_handler.on_game_ended(reason, evaluation)
            return manager.state

        next_step = route_continuation(
            state.get("metadata", {}).get("continuation_decision", {}),
            agent_names_ordered,
        )
        if max_messages_before_user > 0:
            since_user = _messages_since_user(state.get("messages", []))
            if since_user >= max_messages_before_user:
                next_step = "user_input"
        if next_step == "user_input":
            next_action = "user_input"
        else:
            if route_should_continue(state, max_turns) == "end":
                return manager.state
            next_action = "character"
