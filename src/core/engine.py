"""Motor headless de partida: registro de sesiones y ejecución por pasos. Sin I/O ni FastAPI."""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any, Literal

from ..state import ConversationState
from ..manager import ConversationManager
from ..crew_roles.guionista import create_guionista_agent, run_setup_task
from ..crew_roles.character import create_character_agent
from ..crew_roles.observer import create_observer_agent
from ..crew_roles.director import run_one_step


@dataclass
class GameSession:
    """Sesión de una partida en memoria."""
    manager: ConversationManager
    character_agents: dict[str, Any]
    observer_agent: Any
    setup: dict[str, Any]
    max_turns: int
    max_messages_before_user: int = 3
    next_action: Literal["character", "user_input", "ended"] = "character"


class GameEngine:
    """Motor de partidas: registro en memoria y ejecución por pasos."""

    def __init__(self) -> None:
        self._registry: dict[str, GameSession] = {}
        self._logger = logging.getLogger(__name__)

    def create_game(
        self,
        theme: str | None = None,
        num_actors: int = 3,
        max_turns: int = 10,
    ) -> tuple[str, dict[str, Any]]:
        """Crea una partida: Guionista genera setup, Manager y agentes. Devuelve (game_id, setup)."""
        guionista = create_guionista_agent()
        game_setup = run_setup_task(guionista, theme=theme, num_actors=num_actors)

        manager = ConversationManager()
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
            actor_missions={a["name"]: a.get("mission", "") for a in actors_list},
        )

        game_id = str(uuid.uuid4())
        session = GameSession(
            manager=manager,
            character_agents=character_agents,
            observer_agent=observer,
            setup=dict(game_setup),
            max_turns=max_turns,
            max_messages_before_user=3,
            next_action="character",
        )
        self._registry[game_id] = session
        return game_id, session.setup

    def get_state(self, game_id: str) -> ConversationState:
        """Devuelve el estado actual de la partida. Lanza KeyError si no existe."""
        session = self._registry[game_id]
        state = session.manager.state
        return state

    def _get_session(self, game_id: str) -> GameSession:
        if game_id not in self._registry:
            raise KeyError(f"Game not found: {game_id}")
        return self._registry[game_id]

    def player_input(
        self,
        game_id: str,
        text: str,
        user_exit: bool = False,
    ) -> tuple[list, ConversationState, bool]:
        """
        Aplica el input del jugador y avanza pasos hasta user_input o game_ended.
        Devuelve (events, state, game_ended).
        """
        session = self._get_session(game_id)
        all_events: list = []
        t0 = time.perf_counter()
        result = run_one_step(
            session.manager,
            session.character_agents,
            session.observer_agent,
            session.max_turns,
            pending_user_text=text or "",
            user_exit=user_exit,
            max_messages_before_user=session.max_messages_before_user,
        )
        session.next_action = result["next_action"]
        all_events.extend(result.get("events", []))

        while result["next_action"] == "character" and not result.get("game_ended"):
            result = run_one_step(
                session.manager,
                session.character_agents,
                session.observer_agent,
                session.max_turns,
                pending_user_text=None,
                user_exit=False,
                max_messages_before_user=session.max_messages_before_user,
            )
            session.next_action = result["next_action"]
            all_events.extend(result.get("events", []))

        state = session.manager.state
        game_ended = bool(result.get("game_ended", False))
        elapsed = time.perf_counter() - t0
        self._logger.debug(
            "player_input game_id=%s, events=%d, game_ended=%s, elapsed=%.2fs",
            game_id,
            len(all_events),
            game_ended,
            elapsed,
        )
        return all_events, state, game_ended

    def tick(
        self,
        game_id: str,
    ) -> tuple[list, ConversationState, bool, bool]:
        """
        Un paso de personaje si toca; si no, devuelve waiting_for_player.
        Devuelve (events, state, game_ended, waiting_for_player).
        """
        session = self._get_session(game_id)
        if session.next_action != "character":
            return [], session.manager.state, False, True

        t0 = time.perf_counter()
        result = run_one_step(
            session.manager,
            session.character_agents,
            session.observer_agent,
            session.max_turns,
            pending_user_text=None,
            user_exit=False,
            max_messages_before_user=session.max_messages_before_user,
        )
        session.next_action = result["next_action"]
        events = result.get("events", [])
        state = session.manager.state
        game_ended = bool(result.get("game_ended", False))
        elapsed = time.perf_counter() - t0
        self._logger.debug(
            "tick game_id=%s, events=%d, game_ended=%s, elapsed=%.2fs",
            game_id,
            len(events),
            game_ended,
            elapsed,
        )
        return events, state, game_ended, False


def create_engine() -> GameEngine:
    """Factory: una instancia del motor (para API o tests)."""
    return GameEngine()
