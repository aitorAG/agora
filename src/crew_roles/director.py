"""Director: orquestador central. Gestiona el flujo de turnos, llama a Guionista, Character y Observer."""

import os
import time
from typing import Literal, Any

from ..state import ConversationState
from ..manager import ConversationManager
from ..io_adapters import InputProvider, OutputHandler
from ..logging_config import get_logger

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


def run_one_step(
    manager: ConversationManager,
    character_agents: dict[str, Any],
    observer_agent: Any,
    max_turns: int,
    *,
    current_next_action: Literal["character", "user_input"] = "character",
    pending_user_text: str | None = None,
    user_exit: bool = False,
    max_messages_before_user: int = 3,
    stream_character: bool = False,
    character_stream_sink: Any = None,
) -> dict[str, Any]:
    """Ejecuta una sola iteración del bucle: fase character o user_input. Sin I/O; devuelve eventos.

    Args:
        manager: ConversationManager de la partida.
        character_agents: Dict nombre -> CharacterAgent.
        observer_agent: ObserverAgent.
        max_turns: Máximo de turnos de usuario.
        current_next_action: Fase actual ("character" o "user_input").
        pending_user_text: Si current_next_action es "user_input", texto del jugador (o None).
        user_exit: Si el jugador pidió salir.
        max_messages_before_user: Tras N mensajes no-usuario se fuerza user_input.
        stream_character: Si True, el personaje hace streaming (solo tiene efecto si character_stream_sink está dado).
        character_stream_sink: Callable[[str], None] para enviar chunks de respuesta del personaje (para API/SSE).

    Returns:
        dict con next_action ("character" | "user_input" | "ended"), game_ended: bool, events: list.
    """
    events: list[dict] = []
    agent_names_ordered = list(character_agents.keys())
    next_action: Literal["character", "user_input", "ended"] = current_next_action

    if current_next_action == "character":
        state = manager.state
        continuation_decision = state.get("metadata", {}).get("continuation_decision", {})
        who = continuation_decision.get("who_should_respond", "")
        if who and who in character_agents:
            agent = character_agents[who]
        else:
            agent = character_agents[agent_names_ordered[0]]
        result = run_character_response(
            agent,
            state,
            stream=stream_character and character_stream_sink is not None,
            stream_sink=character_stream_sink,
        )
        if "error" in result:
            events.append({"type": "error", "message": result["error"]})
            return {"next_action": "ended", "game_ended": True, "events": events}
        manager.add_message(
            result["author"],
            result["message"],
            displayed=result.get("displayed", False),
        )
        last_msg = manager.state["messages"][-1]
        events.append({"type": "message", "message": dict(last_msg)})
    else:
        assert current_next_action == "user_input"
        if user_exit:
            manager.update_metadata("user_exit", True)
            events.append({"type": "game_ended", "reason": "user_exit", "mission_evaluation": None})
            return {"next_action": "ended", "game_ended": True, "events": events}
        if pending_user_text and pending_user_text.strip():
            manager.add_message("Usuario", pending_user_text.strip())
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
        events.append({"type": "game_ended", "reason": reason, "mission_evaluation": evaluation})
        return {"next_action": "ended", "game_ended": True, "events": events}

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
            return {"next_action": "ended", "game_ended": False, "events": events}
        next_action = "character"

    return {"next_action": next_action, "game_ended": False, "events": events}


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
    logger = get_logger("Director")
    agent_names_ordered = list(character_agents.keys())
    next_action: Literal["character", "user_input"] = "character"
    stream_character = os.environ.get("AGORA_STREAM_CHARACTER", "").strip().lower() in ("1", "true", "yes")

    while True:
        t0_turn = time.perf_counter()
        logger.info("Turn started (next=%s)", next_action)

        if next_action == "character":
            logger.info("Phase: character")
            state = manager.state
            continuation_decision = state.get("metadata", {}).get("continuation_decision", {})
            who = continuation_decision.get("who_should_respond", "")
            if who and who in character_agents:
                agent = character_agents[who]
            else:
                agent = character_agents[agent_names_ordered[0]]
            result = run_character_response(agent, state, stream=stream_character)
            if "error" in result:
                output_handler.on_error(f"Error en {agent.name}: {result['error']}")
                return manager.state
            logger.info("Character response received")
            manager.add_message(
                result["author"],
                result["message"],
                displayed=result.get("displayed", False),
            )
            output_handler.on_message(manager.state["messages"][-1])

        else:
            assert next_action == "user_input"
            logger.info("Phase: user_input")
            user_result = input_provider.get_user_input()
            logger.info("User input received")
            if user_result.user_exit:
                manager.update_metadata("user_exit", True)
                return manager.state
            if user_result.text and user_result.text.strip():
                manager.add_message("Usuario", user_result.text.strip())
                manager.increment_turn()

        state = manager.state
        obs_result = run_observer_tasks(observer_agent, state)
        logger.info("Observer finished")
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
            logger.info("Game ended")
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

        elapsed_turn = time.perf_counter() - t0_turn
        logger.info("Turn finished (next=%s) in %.2f s", next_action, elapsed_turn)
