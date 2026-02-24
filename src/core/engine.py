"""Motor headless de partida: registro de sesiones y ejecución por pasos. Sin I/O ni FastAPI."""

from __future__ import annotations

import logging
import time
from datetime import datetime
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
from ..persistence import PersistenceProvider, create_persistence_provider


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
    persisted_messages: int = 0


class GameEngine:
    """Motor de partidas: registro en memoria y ejecución por pasos."""

    def __init__(self, persistence_provider: PersistenceProvider | None = None) -> None:
        self._registry: dict[str, GameSession] = {}
        self._logger = logging.getLogger(__name__)
        self._persistence = persistence_provider or create_persistence_provider()

    def create_game(
        self,
        theme: str | None = None,
        num_actors: int = 3,
        max_turns: int = 10,
        stream_sink: Any = None,
        username: str | None = None,
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

        title = str(game_setup.get("titulo") or theme or "Partida").strip() or "Partida"
        game_id = self._persistence.create_game(
            title=title,
            config_json=dict(game_setup),
            username=username,
            game_mode="custom",
        )
        session = self._build_session_from_setup(
            setup=game_setup,
            max_turns=max_turns,
            max_messages_before_user=3,
        )
        self._registry[game_id] = session
        self._warmup_session(game_id, session)
        return game_id, session.setup

    def create_game_from_setup(
        self,
        setup: dict[str, Any],
        max_turns: int = 10,
        username: str | None = None,
        standard_template_id: str | None = None,
        template_version: str | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Crea una partida desde un setup predefinido (modo standard)."""
        if not isinstance(setup, dict):
            raise ValueError("Invalid setup")
        actors = setup.get("actors")
        if not isinstance(actors, list) or not actors:
            raise ValueError("Invalid setup actors")

        title = str(setup.get("titulo") or "Partida estándar").strip() or "Partida estándar"
        game_id = self._persistence.create_game(
            title=title,
            config_json=dict(setup),
            username=username,
            game_mode="standard",
            standard_template_id=standard_template_id,
            template_version=template_version,
        )
        session = self._build_session_from_setup(
            setup=setup,
            max_turns=max_turns,
            max_messages_before_user=3,
        )
        self._registry[game_id] = session
        self._warmup_session(game_id, session)
        return game_id, session.setup

    def _build_session_from_setup(
        self,
        setup: dict[str, Any],
        max_turns: int,
        max_messages_before_user: int = 3,
    ) -> GameSession:
        actors_list = setup.get("actors", [])
        if not isinstance(actors_list, list) or not actors_list:
            raise ValueError("Invalid setup actors")
        manager = ConversationManager()
        character_agents: dict[str, Any] = {}
        actor_names: list[str] = []
        for actor in actors_list:
            if not isinstance(actor, dict):
                continue
            name = str(actor.get("name", "")).strip()
            if not name:
                continue
            actor_names.append(name)
            character_agents[name] = create_character_agent(
                name=name,
                personality=actor.get("personality"),
                mission=actor.get("mission"),
                background=actor.get("background"),
            )
        if not actor_names:
            raise ValueError("Invalid setup actors")
        observer = create_observer_agent(
            actor_names=actor_names,
            player_mission=setup.get("player_mission") or "",
        )
        return GameSession(
            manager=manager,
            character_agents=character_agents,
            observer_agent=observer,
            setup=dict(setup),
            max_turns=max_turns,
            max_messages_before_user=max_messages_before_user,
            next_action="character",
            persisted_messages=0,
        )

    def _warmup_session(self, game_id: str, session: GameSession) -> None:
        """Avanza al primer punto de input del usuario y persiste snapshot inicial."""
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
        self._persist_session_state(game_id, session)

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

    def list_games(self, username: str) -> list[dict[str, Any]]:
        """Lista partidas para el usuario indicado."""
        return self._persistence.list_games_for_user(username)

    def game_belongs_to_user(self, game_id: str, username: str) -> bool:
        game = self._persistence.get_game(game_id)
        return str(game.get("user", "")) == username

    def resume_game(self, game_id: str) -> dict[str, Any]:
        """Reanuda sesión existente desde memoria o persistencia."""
        if game_id in self._registry:
            return {"session_id": game_id, "loaded_from_memory": True}
        self._rehydrate_session(game_id)
        return {"session_id": game_id, "loaded_from_memory": False}

    @staticmethod
    def _parse_timestamp(value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str) and value:
            normalized = value.replace("Z", "+00:00")
            try:
                return datetime.fromisoformat(normalized)
            except ValueError:
                pass
        return datetime.now()

    @staticmethod
    def _valid_next_action(value: Any) -> Literal["character", "user_input", "ended"]:
        if value in ("character", "user_input", "ended"):
            return value
        return "user_input"

    def _rehydrate_session(self, game_id: str) -> GameSession:
        """Reconstruye una sesión desde persistencia y la registra en memoria."""
        if game_id in self._registry:
            return self._registry[game_id]

        game = self._persistence.get_game(game_id)
        config_json = game.get("config_json", {})
        if not isinstance(config_json, dict):
            raise ValueError("Session cannot be resumed: invalid config")

        state_json = game.get("state_json", {})
        if not isinstance(state_json, dict):
            state_json = {}

        actors = config_json.get("actors", [])
        if not isinstance(actors, list):
            raise ValueError("Session cannot be resumed: invalid actors")

        character_agents: dict[str, Any] = {}
        actor_names: list[str] = []
        for actor in actors:
            if not isinstance(actor, dict):
                continue
            name = str(actor.get("name", "")).strip()
            if not name:
                continue
            actor_names.append(name)
            character_agents[name] = create_character_agent(
                name=name,
                personality=actor.get("personality"),
                mission=actor.get("mission"),
                background=actor.get("background"),
            )

        if not actor_names:
            raise ValueError("Session cannot be resumed: no valid actors")

        observer = create_observer_agent(
            actor_names=actor_names,
            player_mission=str(config_json.get("player_mission") or ""),
        )

        persisted_records = self._persistence.get_game_messages(game_id)
        restored_messages: list[dict[str, Any]] = []
        raw_messages = state_json.get("messages", [])
        if isinstance(raw_messages, list):
            for msg in raw_messages:
                if not isinstance(msg, dict):
                    continue
                try:
                    msg_turn = int(msg.get("turn", 0))
                except (TypeError, ValueError):
                    msg_turn = 0
                restored_messages.append(
                    {
                        "author": str(msg.get("author", "")),
                        "content": str(msg.get("content", "")),
                        "timestamp": self._parse_timestamp(msg.get("timestamp")),
                        "turn": msg_turn,
                        "displayed": bool(msg.get("displayed", False)),
                    }
                )

        # Compatibilidad con snapshots antiguos sin messages en state_json.
        if not restored_messages and isinstance(persisted_records, list):
            for rec in persisted_records:
                if not isinstance(rec, dict):
                    continue
                metadata = rec.get("metadata_json", {})
                if not isinstance(metadata, dict):
                    metadata = {}
                try:
                    rec_turn = int(rec.get("turn_number", 0))
                except (TypeError, ValueError):
                    rec_turn = 0
                restored_messages.append(
                    {
                        "author": str(metadata.get("author") or rec.get("role") or ""),
                        "content": str(rec.get("content", "")),
                        "timestamp": self._parse_timestamp(metadata.get("timestamp") or rec.get("created_at")),
                        "turn": rec_turn,
                        "displayed": False,
                    }
                )

        raw_metadata = state_json.get("metadata", {})
        metadata = raw_metadata if isinstance(raw_metadata, dict) else {}

        try:
            restored_turn = int(state_json.get("turn", 0))
        except (TypeError, ValueError):
            restored_turn = 0

        manager = ConversationManager()
        manager.restore_state(
            {
                "messages": restored_messages,
                "turn": restored_turn,
                "metadata": metadata,
            }
        )

        try:
            max_turns = int(state_json.get("max_turns", 10))
        except (TypeError, ValueError):
            max_turns = 10
        try:
            max_messages_before_user = int(state_json.get("max_messages_before_user", 3))
        except (TypeError, ValueError):
            max_messages_before_user = 3

        session = GameSession(
            manager=manager,
            character_agents=character_agents,
            observer_agent=observer,
            setup=dict(config_json),
            max_turns=max_turns,
            max_messages_before_user=max_messages_before_user,
            next_action=self._valid_next_action(state_json.get("next_action")),
            persisted_messages=len(restored_messages),
        )
        self._registry[game_id] = session
        return session

    def _get_session(self, game_id: str) -> GameSession:
        if game_id not in self._registry:
            self._rehydrate_session(game_id)
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
        self._persist_session_state(game_id, session)
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
        self._persist_session_state(game_id, session)
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
            try:
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
                self._persist_session_state(game_id, session)
                queue.put(("done", all_events))
            except Exception as e:
                queue.put(("error", str(e)))

        thread = Thread(target=run)
        thread.start()
        while True:
            try:
                item = queue.get(timeout=300.0)
            except Empty:
                break
            if item[0] == "delta":
                yield {"type": "message_delta", "delta": item[1]}
            elif item[0] == "error":
                yield {"type": "error", "message": item[1]}
                break
            else:
                for ev in item[1]:
                    yield ev
                break
        thread.join()

    @staticmethod
    def _map_role(author: str) -> str:
        if author == "Usuario":
            return "player"
        if author in ("Sistema", "system"):
            return "director"
        safe = (author or "actor").strip().replace(" ", "_").lower()
        return f"actor_{safe}"

    @staticmethod
    def _jsonable(value: Any) -> Any:
        if isinstance(value, dict):
            return {k: GameEngine._jsonable(v) for k, v in value.items()}
        if isinstance(value, list):
            return [GameEngine._jsonable(v) for v in value]
        if hasattr(value, "isoformat"):
            try:
                return value.isoformat()
            except Exception:
                return str(value)
        return value

    def _persist_session_state(self, game_id: str, session: GameSession) -> None:
        state = session.manager.state
        messages = state.get("messages", [])
        if not isinstance(messages, list):
            messages = []
        for msg in messages[session.persisted_messages :]:
            author = str(msg.get("author", ""))
            self._persistence.append_message(
                game_id=game_id,
                turn_number=int(msg.get("turn", 0)),
                role=self._map_role(author),
                content=str(msg.get("content", "")),
                metadata_json={
                    "author": author,
                    "timestamp": msg.get("timestamp").isoformat() if hasattr(msg.get("timestamp"), "isoformat") else str(msg.get("timestamp")) if msg.get("timestamp") is not None else None,
                },
            )
        session.persisted_messages = len(messages)
        state_json = {
            "turn": state.get("turn", 0),
            "messages": messages,
            "metadata": state.get("metadata", {}),
            "next_action": session.next_action,
            "max_turns": session.max_turns,
            "max_messages_before_user": session.max_messages_before_user,
        }
        self._persistence.save_game_state(game_id, self._jsonable(state_json))


def create_engine(persistence_provider: PersistenceProvider | None = None) -> GameEngine:
    """Factory: una instancia del motor (para API o tests)."""
    return GameEngine(persistence_provider=persistence_provider)
