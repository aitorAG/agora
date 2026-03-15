"""Motor headless de partida: registro de sesiones y ejecución por pasos. Sin I/O ni FastAPI."""

from __future__ import annotations

import logging
import random
import time
from datetime import datetime
from dataclasses import dataclass
from queue import Empty, Queue
from threading import Thread
from typing import Any, Iterator, Literal
from uuid import uuid4

from ..state import ConversationState
from ..manager import ConversationManager
from ..agents.actor_prompt_template import default_actor_prompt_template
from ..crew_roles.guionista import create_guionista_agent, run_setup_task
from ..crew_roles.character import create_character_agent, run_character_response
from ..crew_roles.observer import create_observer_agent
from ..crew_roles.director import run_one_step
from ..persistence import PersistenceProvider, create_persistence_provider
from ..observability import emit_event, trace_interaction, trace_setup
from ..player_identity import INTERNAL_PLAYER_AUTHOR
from ..public_missions import (
    fallback_actor_public_mission,
    fallback_player_public_mission,
)
from ..text_limits import validate_custom_seed, validate_user_message
from .game_setup_contract import validate_game_setup


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
    actor_prompt_template: str = ""


class GameEngine:
    """Motor de partidas: registro en memoria y ejecución por pasos."""

    def __init__(self, persistence_provider: PersistenceProvider | None = None) -> None:
        self._registry: dict[str, GameSession] = {}
        self._logger = logging.getLogger(__name__)
        self._persistence = persistence_provider or create_persistence_provider()

    def create_game(
        self,
        theme: str | None = None,
        era: str | None = None,
        topic: str | None = None,
        style: str | None = None,
        num_actors: int = 3,
        max_turns: int = 10,
        stream_sink: Any = None,
        username: str | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Crea una partida: Guionista genera setup, Manager y agentes. Devuelve (game_id, setup).
        Si stream_sink es un Callable[[str], None], se invoca con cada chunk de la narrativa (JSON) durante la generación."""
        validated_seed = validate_custom_seed(
            theme=theme,
            era=era,
            topic=topic,
            style=style,
        )
        effective_theme = validated_seed["theme"] or None
        guionista = create_guionista_agent()
        stream = stream_sink is not None
        setup_interaction_id = f"setup:{uuid4()}"
        with trace_setup(user_id=username or "", interaction_id=setup_interaction_id, name="setup"):
            game_setup = run_setup_task(
                guionista,
                theme=effective_theme,
                num_actors=num_actors,
                stream=stream,
                stream_sink=stream_sink,
            )

        title = str(game_setup.get("titulo") or effective_theme or "Partida").strip() or "Partida"
        game_id = self._persistence.create_game(
            title=title,
            config_json=dict(game_setup),
            username=username,
            game_mode="custom",
        )
        emit_event(
            "link_interaction",
            {
                "interaction_id": setup_interaction_id,
                "game_id": game_id,
                "user_id": username or "",
                "status": "ok",
            },
        )
        session = self._build_session_from_setup(
            setup=game_setup,
            max_turns=max_turns,
            actor_prompt_template=self._current_actor_prompt_template(),
            player_name=username,
        )
        self._registry[game_id] = session
        self._warmup_session(game_id, session, game_mode="custom")
        return game_id, session.setup

    def create_game_from_setup(
        self,
        setup: dict[str, Any],
        max_turns: int = 10,
        username: str | None = None,
        game_mode: Literal["custom", "standard"] = "standard",
        standard_template_id: str | None = None,
        template_version: str | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Crea una partida desde un setup predefinido."""
        if game_mode not in ("custom", "standard"):
            raise ValueError("Invalid game mode")

        validated_setup = validate_game_setup(setup)
        default_title = "Plantilla" if game_mode == "standard" else "Partida"
        title = str(validated_setup.get("titulo") or default_title).strip() or default_title
        game_id = self._persistence.create_game(
            title=title,
            config_json=dict(validated_setup),
            username=username,
            game_mode=game_mode,
            standard_template_id=standard_template_id,
            template_version=template_version,
        )
        session = self._build_session_from_setup(
            setup=validated_setup,
            max_turns=max_turns,
            actor_prompt_template=self._current_actor_prompt_template(),
            player_name=username,
        )
        self._registry[game_id] = session
        self._warmup_session(game_id, session, game_mode=game_mode)
        return game_id, session.setup

    def _build_session_from_setup(
        self,
        setup: dict[str, Any],
        max_turns: int,
        actor_prompt_template: str | None = None,
        player_name: str | None = None,
    ) -> GameSession:
        actors_list = setup.get("actors", [])
        if not isinstance(actors_list, list) or not actors_list:
            raise ValueError("Invalid setup actors")
        manager = ConversationManager()
        resolved_player_name = str(player_name or "").strip() or INTERNAL_PLAYER_AUTHOR
        manager.update_metadata("player_name", resolved_player_name)
        character_agents: dict[str, Any] = {}
        actor_names: list[str] = []
        player_public_mission = str(
            setup.get("player_public_mission")
            or fallback_player_public_mission(
                relevancia_jugador=setup.get("relevancia_jugador"),
                contexto_problema=setup.get("contexto_problema"),
            )
        ).strip()
        scene_participants = self._build_scene_participants(setup)
        resolved_actor_prompt_template = str(
            actor_prompt_template or default_actor_prompt_template()
        )
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
                player_public_mission=player_public_mission,
                scene_participants=scene_participants,
                prompt_template=resolved_actor_prompt_template,
            )
        if not actor_names:
            raise ValueError("Invalid setup actors")
        max_messages_before_user = len(actor_names)
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
            actor_prompt_template=resolved_actor_prompt_template,
        )

    @staticmethod
    def _build_scene_participants(setup: dict[str, Any]) -> list[dict[str, str]]:
        actors = setup.get("actors", [])
        if not isinstance(actors, list):
            return []
        scene_participants: list[dict[str, str]] = []
        for actor in actors:
            if not isinstance(actor, dict):
                continue
            name = str(actor.get("name", "")).strip()
            if not name:
                continue
            scene_participants.append(
                {
                    "name": name,
                    "personality": str(actor.get("personality", "")).strip(),
                    "public_mission": str(
                        actor.get("public_mission")
                        or fallback_actor_public_mission(
                            personality=actor.get("personality"),
                            presencia_escena=actor.get("presencia_escena"),
                        )
                    ).strip(),
                    "presencia_escena": str(actor.get("presencia_escena", "")).strip(),
                }
            )
        return scene_participants

    def _current_actor_prompt_template(self) -> str:
        persisted = self._persistence.get_actor_prompt_template()
        return str(persisted or default_actor_prompt_template())

    def _build_standard_opening_instruction(self, session: GameSession) -> str:
        setup = session.setup
        context_parts = [
            str(setup.get("ambientacion") or "").strip(),
            str(setup.get("contexto_problema") or "").strip(),
            str(setup.get("relevancia_jugador") or "").strip(),
        ]
        context_block = "\n".join(part for part in context_parts if part)
        instruction = (
            "Dado el contexto, tu background y tu misión, da tu posición inicial "
            "sobre el conflicto en 1 o 2 frases, dirigiéndote al jugador, sin "
            "revelar tu objetivo explícitamente."
        )
        if context_block:
            return f"Contexto de la escena:\n{context_block}\n\n{instruction}"
        return instruction

    def _warmup_standard_session(self, game_id: str, session: GameSession) -> None:
        actor_names = list(session.character_agents.keys())
        if not actor_names:
            raise ValueError("Invalid setup actors")

        random.shuffle(actor_names)
        opening_count = max(1, (len(actor_names) + 1) // 2)
        opening_instruction = self._build_standard_opening_instruction(session)

        for idx, actor_name in enumerate(actor_names[:opening_count]):
            agent = session.character_agents.get(actor_name)
            if agent is None:
                continue
            result = run_character_response(
                agent,
                session.manager.state,
                extra_system_instruction=opening_instruction if idx == 0 else None,
            )
            if "error" in result:
                raise RuntimeError(str(result["error"]))
            session.manager.add_message(
                result["author"],
                result["message"],
                displayed=result.get("displayed", False),
            )

        session.manager.update_metadata(
            "continuation_decision",
            {
                "needs_response": False,
                "who_should_respond": "user",
                "reason": "Warmup de plantilla completado.",
            },
        )
        session.next_action = "user_input"
        self._persist_session_state(game_id, session)

    def _warmup_session(
        self,
        game_id: str,
        session: GameSession,
        game_mode: Literal["custom", "standard"] = "custom",
    ) -> None:
        """Avanza al primer punto de input del usuario y persiste snapshot inicial."""
        if game_mode == "standard":
            self._warmup_standard_session(game_id, session)
            return
        game = self._persistence.get_game(game_id)
        user_id = str(game.get("user_id") or game.get("user") or "") if game else ""
        interaction_id = f"{game_id}:warmup"
        with trace_interaction(game_id, user_id, interaction_id, name="warmup"):
            result = run_one_step(
                session.manager,
                session.character_agents,
                session.observer_agent,
                session.max_turns,
                current_next_action=session.next_action,
                pending_user_text=None,
                user_exit=False,
                max_messages_before_user=session.max_messages_before_user,
                game_id=game_id,
                turn=session.manager.state.get("turn", 0),
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
                    game_id=game_id,
                    turn=session.manager.state.get("turn", 0),
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
                "public_mission": a.get("public_mission", "")
                or fallback_actor_public_mission(
                    personality=a.get("personality"),
                    presencia_escena=a.get("presencia_escena"),
                ),
                "background": a.get("background", ""),
                "presencia_escena": a.get("presencia_escena", ""),
            }
            for a in actors
        ]
        return {
            "player_mission": setup.get("player_mission", ""),
            "player_public_mission": setup.get("player_public_mission", "")
            or fallback_player_public_mission(
                relevancia_jugador=setup.get("relevancia_jugador", ""),
                contexto_problema=setup.get("contexto_problema", ""),
            ),
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

    def submit_feedback(self, game_id: str, user_id: str, feedback_text: str) -> str:
        return self._persistence.create_feedback(
            game_id=game_id,
            user_id=user_id,
            feedback_text=feedback_text,
        )

    def list_feedback(self, limit: int = 500) -> list[dict[str, Any]]:
        return self._persistence.list_feedback(limit=limit)

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
        player_public_mission = str(
            config_json.get("player_public_mission")
            or fallback_player_public_mission(
                relevancia_jugador=config_json.get("relevancia_jugador"),
                contexto_problema=config_json.get("contexto_problema"),
            )
        ).strip()
        scene_participants = self._build_scene_participants(config_json)
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
                player_public_mission=player_public_mission,
                scene_participants=scene_participants,
                prompt_template=str(
                    state_json.get("actor_prompt_template")
                    or default_actor_prompt_template()
                ),
            )

        if not actor_names:
            raise ValueError("Session cannot be resumed: no valid actors")

        observer = create_observer_agent(
            actor_names=actor_names,
            player_mission=str(config_json.get("player_mission") or ""),
        )

        persisted_records = self._persistence.get_game_messages(game_id)
        restored_messages: list[dict[str, Any]] = []
        if isinstance(persisted_records, list):
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
                        "author": str(rec.get("author") or metadata.get("author") or rec.get("role") or ""),
                        "content": str(rec.get("content", "")),
                        "timestamp": self._parse_timestamp(metadata.get("timestamp") or rec.get("created_at")),
                        "turn": rec_turn,
                        "displayed": bool(metadata.get("displayed", False)),
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
        restored_player_name = str(metadata.get("player_name") or game.get("user") or "").strip()
        manager.update_metadata(
            "player_name",
            restored_player_name or INTERNAL_PLAYER_AUTHOR,
        )

        try:
            max_turns = int(state_json.get("max_turns", 10))
        except (TypeError, ValueError):
            max_turns = 10
        max_messages_before_user = len(actor_names)

        session = GameSession(
            manager=manager,
            character_agents=character_agents,
            observer_agent=observer,
            setup=dict(config_json),
            max_turns=max_turns,
            max_messages_before_user=max_messages_before_user,
            next_action=self._valid_next_action(state_json.get("next_action")),
            persisted_messages=len(restored_messages),
            actor_prompt_template=str(
                state_json.get("actor_prompt_template")
                or default_actor_prompt_template()
            ),
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
        if text and text.strip():
            validate_user_message(text)
        game = self._persistence.get_game(game_id)
        user_id = str(game.get("user_id") or game.get("user") or "") if game else ""
        state = session.manager.state
        interaction_id = f"{game_id}:turn:{state.get('turn', 0)}"
        all_events: list = []
        t0 = time.perf_counter()
        with trace_interaction(game_id, user_id, interaction_id):
            result = run_one_step(
                session.manager,
                session.character_agents,
                session.observer_agent,
                session.max_turns,
                current_next_action=session.next_action,
                pending_user_text=text or "",
                user_exit=user_exit,
                max_messages_before_user=session.max_messages_before_user,
                game_id=game_id,
                turn=session.manager.state.get("turn", 0),
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
                    game_id=game_id,
                    turn=session.manager.state.get("turn", 0),
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

        game = self._persistence.get_game(game_id)
        user_id = str(game.get("user_id") or game.get("user") or "") if game else ""
        interaction_id = f"{game_id}:tick:{session.manager.state.get('turn', 0)}"
        t0 = time.perf_counter()
        with trace_interaction(game_id, user_id, interaction_id, name="tick"):
            result = run_one_step(
                session.manager,
                session.character_agents,
                session.observer_agent,
                session.max_turns,
                current_next_action=session.next_action,
                pending_user_text=None,
                user_exit=False,
                max_messages_before_user=session.max_messages_before_user,
                game_id=game_id,
                turn=session.manager.state.get("turn", 0),
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
        Genera eventos en streaming: observer_thinking, message_start, message_delta,
        message y game_ended a medida que cada actor termina.
        """
        session = self._get_session(game_id)
        if text and text.strip():
            validate_user_message(text)
        game = self._persistence.get_game(game_id)
        user_id = str(game.get("user_id") or game.get("user") or "") if game else ""
        interaction_id = f"{game_id}:turn:{session.manager.state.get('turn', 0)}"
        queue: Queue = Queue()

        def chunk_sink(chunk: str) -> None:
            queue.put(("delta", chunk))

        def event_sink(event: dict[str, Any]) -> None:
            queue.put(("event", dict(event)))

        def run() -> None:
            try:
                with trace_interaction(game_id, user_id, interaction_id, name="turn_stream"):
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
                        event_sink=event_sink,
                        game_id=game_id,
                        turn=session.manager.state.get("turn", 0),
                    )
                    session.next_action = result["next_action"]
                    for ev in result.get("events", []):
                        event_sink(ev)
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
                            event_sink=event_sink,
                            game_id=game_id,
                            turn=session.manager.state.get("turn", 0),
                        )
                        session.next_action = result["next_action"]
                        for ev in result.get("events", []):
                            event_sink(ev)
                    self._persist_session_state(game_id, session)
                    queue.put(("done", None))
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
            elif item[0] == "event":
                yield item[1]
            elif item[0] == "error":
                yield {"type": "error", "message": item[1]}
                break
            else:
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

    def _build_state_snapshot(self, session: GameSession) -> dict[str, Any]:
        state = session.manager.state
        return {
            "turn": state.get("turn", 0),
            "metadata": state.get("metadata", {}),
            "next_action": session.next_action,
            "max_turns": session.max_turns,
            "max_messages_before_user": session.max_messages_before_user,
            "actor_prompt_template": session.actor_prompt_template,
        }

    def _build_domain_events(self, game_id: str, session: GameSession, new_messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if session.next_action != "user_input" or not new_messages:
            return []
        actor_count = max(1, len(session.character_agents))
        messages = session.manager.state.get("messages", [])
        total_messages = len(messages) if isinstance(messages, list) else len(new_messages)
        window_size = (actor_count + 1) * 2
        return [
            {
                "event_type": "turn_reached_user_input",
                "aggregate_type": "game",
                "aggregate_id": game_id,
                "payload_json": {
                    "game_id": game_id,
                    "turn": int(session.manager.state.get("turn", 0)),
                    "actor_count": actor_count,
                    "window_size": window_size,
                    "message_count": total_messages,
                    "next_action": session.next_action,
                },
            }
        ]

    def _persist_session_state(self, game_id: str, session: GameSession) -> None:
        state = session.manager.state
        messages = state.get("messages", [])
        if not isinstance(messages, list):
            messages = []
        new_messages = []
        for msg in messages[session.persisted_messages :]:
            author = str(msg.get("author", ""))
            new_messages.append(
                {
                    "author": author,
                    "turn": int(msg.get("turn", 0)),
                    "role": self._map_role(author),
                    "content": str(msg.get("content", "")),
                    "timestamp": msg.get("timestamp"),
                    "displayed": bool(msg.get("displayed", False)),
                }
            )
        state_snapshot = self._jsonable(self._build_state_snapshot(session))
        domain_events = self._build_domain_events(game_id, session, new_messages)
        self._persistence.persist_game_progress(
            game_id=game_id,
            new_messages=new_messages,
            state_json=state_snapshot,
            domain_events=domain_events,
        )
        session.persisted_messages = len(messages)


def create_engine(persistence_provider: PersistenceProvider | None = None) -> GameEngine:
    """Factory: una instancia del motor (para API o tests)."""
    return GameEngine(persistence_provider=persistence_provider)
