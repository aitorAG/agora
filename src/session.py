"""Bootstrap de sesión de partida: crea motor (manager, agentes, grafo) con I/O inyectados.

El motor no conoce terminal ni HTTP; solo recibe InputProvider y OutputHandler.
"""

from typing import Any
from .state import ConversationState
from .manager import ConversationManager
from .agents.character import CharacterAgent
from .agents.observer import ObserverAgent
from .agents.guionista import GuionistaAgent
from .graph import create_conversation_graph
from .io_adapters import InputProvider, OutputHandler


def create_session(
    *,
    theme: str | None = None,
    num_actors: int = 3,
    max_turns: int = 10,
    input_provider: InputProvider,
    output_handler: OutputHandler,
) -> tuple[Any, ConversationState, dict[str, Any]]:
    """Crea una sesión de partida: Guionista genera setup, se crean Manager, agentes y grafo.

    Args:
        theme: Tema opcional para el Guionista (ej. desde GAME_THEME).
        num_actors: Número de actores (por defecto 3).
        max_turns: Máximo de intervenciones del jugador.
        input_provider: Abstracción para obtener input del jugador.
        output_handler: Abstracción para emitir mensajes y errores.

    Returns:
        (graph, initial_state, setup)
        - graph: grafo LangGraph compilado listo para invoke(initial_state).
        - initial_state: estado inicial (messages=[], turn=0, metadata={}).
        - setup: dict con narrativa_inicial, player_mission, actors, etc. para que el cliente muestre la pantalla inicial.
    """
    guionista = GuionistaAgent()
    game_setup = guionista.generate_setup(theme=theme, num_actors=num_actors)

    manager = ConversationManager()
    initial_state: ConversationState = manager.state

    actors_list = game_setup["actors"]
    character_agents: dict[str, CharacterAgent] = {}
    for a in actors_list:
        character_agents[a["name"]] = CharacterAgent(
            name=a["name"],
            personality=a["personality"],
            mission=a.get("mission"),
            background=a.get("background"),
        )

    actor_names = [a["name"] for a in game_setup["actors"]]
    observer = ObserverAgent(
        actor_names=actor_names,
        player_mission=game_setup.get("player_mission") or "",
        actor_missions={a["name"]: a.get("mission", "") for a in game_setup["actors"]},
    )

    graph = create_conversation_graph(
        character_agents=character_agents,
        observer_agent=observer,
        manager=manager,
        max_turns=max_turns,
        input_provider=input_provider,
        output_handler=output_handler,
    )

    # setup es el game_setup completo: para mostrar (on_setup_ready) y para persistir (game_setup.json)
    setup = dict(game_setup)
    return graph, initial_state, setup
