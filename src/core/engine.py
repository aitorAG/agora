"""Motor headless de partida: registro de sesiones y ejecución por pasos. Sin I/O ni FastAPI."""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from queue import Empty, Queue
from threading import Thread
from typing import Any, Iterator, Literal

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
        stream_sink: Any = None,
    ) -> tuple[str, dict[str, Any]]:
        """Crea una partida: Guionista genera setup, Manager y agentes. Devuelve (game_id, setup).
        Si stream_sink es un Callable[[str], None], se invoca con cada chunk de la narrativa (JSON) durante la generación."""
        guionista = create_guionista_agent()
        stream = stream_sink is not None
        game_setup = run_setup_task(
            guionista,
            theme=theme,
            num_actors=num_actors,
            stream=stream,
            stream_sink=stream_sink,
        )

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
        # Avanzar hasta que toque user_input (o partida termine) para que player_can_write sea true al devolver
        result = run_one_step(
            session.manager,
            session.character_agents,
            session.observer_agent,
            session.max_turns,
            current_next_action=session.next_action,
            pending_user_text=None,
            user_exit=False,
            max_messages_before_user=session.max_messages_before_user,
        )
        session.next_action = result["next_action"]
        while result["next_action"] == "character" and not result.get("game_ended"):
            result = run_one_step(
                session.manager,
                session.character_agents,
                session.observer_agent,
                session.max_turns,
                current_next_action=session.next_action,
                pending_user_text=None,
                user_exit=False,
                max_messages_before_user=session.max_messages_before_user,
            )
            session.next_action = result["next_action"]
        return game_id, session.setup

    def get_state(self, game_id: str) -> ConversationState:
        """Devuelve el estado actual de la partida. Lanza KeyError si no existe."""
        session = self._registry[game_id]
        state = session.manager.state
        return state

    def get_status(self, game_id: str) -> dict[str, Any]:
        """Devuelve el contrato de estado para la API: turn_current, turn_max, current_speaker, player_can_write, game_finished, result, messages. Lanza KeyError si no existe."""
        session = self._get_session(game_id)
        state = session.manager.state
        metadata = state.get("metadata", {})
        continuation = metadata.get("continuation_decision", {})
        current_speaker = continuation.get("who_should_respond") or ""
        if current_speaker == "user":
            current_speaker = ""
        player_can_write = session.next_action == "user_input"
        game_finished = bool(metadata.get("game_ended", False))
        result = None
        if game_finished:
            result = {
                "reason": metadata.get("game_ended_reason", ""),
                "mission_evaluation": metadata.get("last_mission_evaluation"),
            }
        messages = state.get("messages", [])
        return {
            "turn_current": state.get("turn", 0),
            "turn_max": session.max_turns,
            "current_speaker": current_speaker,
            "player_can_write": player_can_write,
            "game_finished": game_finished,
            "result": result,
            "messages": messages,
        }

    def get_context(self, game_id: str) -> dict[str, Any]:
        """Devuelve contexto estable para panel lateral: player_mission, personajes, metadata inicial. Lanza KeyError si no existe."""
        session = self._get_session(game_id)
        setup = session.setup
        actors = setup.get("actors", [])
        characters = [
            {
                "name": a.get("name", ""),
                "personality": a.get("personality", ""),
                "mission": a.get("mission", ""),
                "background": a.get("background", ""),
                "presencia_escena": a.get("presencia_escena", ""),
            }
            for a in actors
        ]
        return {
            "player_mission": setup.get("player_mission", ""),
            "characters": characters,
            "ambientacion": setup.get("ambientacion", ""),
            "contexto_problema": setup.get("contexto_problema", ""),
            "relevancia_jugador": setup.get("relevancia_jugador", ""),
            "narrativa_inicial": setup.get("narrativa_inicial", ""),
        }

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
            current_next_action=session.next_action,
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
                current_next_action=session.next_action,
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
            current_next_action=session.next_action,
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

    def execute_turn_stream(
        self,
        game_id: str,
        text: str,
        user_exit: bool = False,
    ) -> Iterator[dict[str, Any]]:
        """Ejecuta el turno (input del jugador + respuestas de personajes hasta user_input o game_ended).
        Genera eventos en streaming: message_delta (chunks), luego message, turn_end, game_ended si aplica.
        """
        session = self._get_session(game_id)
        queue: Queue = Queue()

        def chunk_sink(chunk: str) -> None:
            queue.put(("delta", chunk))

        def run() -> None:
            all_events: list = []
            result = run_one_step(
                session.manager,
                session.character_agents,
                session.observer_agent,
                session.max_turns,
                current_next_action=session.next_action,
                pending_user_text=text or "",
                user_exit=user_exit,
                max_messages_before_user=session.max_messages_before_user,
                stream_character=True,
                character_stream_sink=chunk_sink,
            )
            session.next_action = result["next_action"]
            all_events.extend(result.get("events", []))
            while result["next_action"] == "character" and not result.get("game_ended"):
                result = run_one_step(
                    session.manager,
                    session.character_agents,
                    session.observer_agent,
                    session.max_turns,
                    current_next_action=session.next_action,
                    pending_user_text=None,
                    user_exit=False,
                    max_messages_before_user=session.max_messages_before_user,
                    stream_character=True,
                    character_stream_sink=chunk_sink,
                )
                session.next_action = result["next_action"]
                all_events.extend(result.get("events", []))
            queue.put(("done", all_events))

        thread = Thread(target=run)
        thread.start()
        while True:
            try:
                item = queue.get(timeout=300.0)
            except Empty:
                break
            if item[0] == "delta":
                yield {"type": "message_delta", "delta": item[1]}
            else:
                for ev in item[1]:
                    yield ev
                break
        thread.join()


def create_engine() -> GameEngine:
    """Factory: una instancia del motor (para API o tests)."""
    return GameEngine()
