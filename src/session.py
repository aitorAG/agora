"""Bootstrap de sesión de partida: crea motor (manager, agentes) con I/O inyectados.
Sin LangGraph: el Director orquesta el bucle vía crew_roles.
"""

import os
from typing import Any, Callable
from .state import ConversationState
from .manager import ConversationManager
from .io_adapters import InputProvider, OutputHandler
from .logging_config import get_logger
from .crew_roles import (
    create_guionista_agent,
    run_setup_task,
    create_character_agent,
    create_observer_agent,
    run_game_loop,
)


def create_session(
    *,
    theme: str | None = None,
    num_actors: int = 3,
    max_turns: int = 10,
    input_provider: InputProvider,
    output_handler: OutputHandler,
) -> tuple[Callable[[], ConversationState], ConversationState, dict[str, Any]]:
    """Crea una sesión de partida: Guionista genera setup, se crean Manager y agentes (crew_roles).
    El Director orquesta el bucle al ejecutar el runner.

    Args:
        theme: Tema opcional para el Guionista.
        num_actors: Número de actores (por defecto 3).
        max_turns: Máximo de intervenciones del jugador.
        input_provider: Abstracción para obtener input del jugador.
        output_handler: Abstracción para emitir mensajes y errores.

    Returns:
        (runner, initial_state, setup)
        - runner: llamable sin argumentos que ejecuta el bucle hasta el fin; devuelve estado final.
        - initial_state: estado inicial (messages=[], turn=0, metadata={}).
        - setup: dict con narrativa_inicial, player_mission, actors, etc.
    """
    log = get_logger("Session")
    log.debug("Setup phase: Guionista")
    stream_guionista = os.environ.get("AGORA_STREAM_GUIONISTA", "").strip().lower() in ("1", "true", "yes")
    guionista = create_guionista_agent()
    game_setup = run_setup_task(guionista, theme=theme, num_actors=num_actors, stream=stream_guionista)

    log.debug("Setup phase: creating agents")
    manager = ConversationManager()
    initial_state: ConversationState = manager.state

    actors_list = game_setup["actors"]
    character_agents: dict[str, Any] = {}
    for a in actors_list:
        character_agents[a["name"]] = create_character_agent(
            name=a["name"],
            personality=a["personality"],
            mission=a.get("mission"),
            background=a.get("background"),
        )

    observer = create_observer_agent(
        actor_names=[a["name"] for a in actors_list],
        player_mission=game_setup.get("player_mission") or "",
    )

    def runner() -> ConversationState:
        return run_game_loop(
            manager,
            character_agents,
            observer,
            max_turns,
            input_provider=input_provider,
            output_handler=output_handler,
            max_messages_before_user=3,
        )

    log.debug("Runner configured")
    setup = dict(game_setup)
    return runner, initial_state, setup
