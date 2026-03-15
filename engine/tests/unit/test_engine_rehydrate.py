"""Tests de rehidratación de sesiones en GameEngine."""

import uuid
from datetime import datetime, timezone

import src.core.engine as engine_module
from src.core.engine import GameEngine
from src.persistence.provider import PersistenceProvider


def _utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


class _InMemoryProvider(PersistenceProvider):
    def __init__(self):
        self.games: dict[str, dict] = {}
        self.messages: dict[str, list[dict]] = {}
        self.outbox_events: list[dict] = []
        self.runtime_settings: dict[str, dict] = {}

    def create_game(
        self,
        title,
        config_json,
        username=None,
        game_mode="custom",
        standard_template_id=None,
        template_version=None,
    ) -> str:
        game_id = str(uuid.uuid4())
        now = _utc_now_iso()
        self.games[game_id] = {
            "id": game_id,
            "title": title,
            "status": "active",
            "user": username or "usuario",
            "game_mode": game_mode,
            "standard_template_id": standard_template_id,
            "template_version": template_version,
            "created_at": now,
            "updated_at": now,
            "config_json": dict(config_json),
            "state_json": {"turn": 0, "metadata": {}, "next_action": "character"},
        }
        self.messages[game_id] = []
        return game_id

    def save_game_state(self, game_id, state_json):
        self.games[game_id]["state_json"] = dict(state_json)

    def append_message(self, game_id, turn_number, role, content, metadata_json=None):
        self.messages[game_id].append(
            {
                "id": str(uuid.uuid4()),
                "game_id": game_id,
                "turn_number": int(turn_number),
                "author": (metadata_json or {}).get("author") or role,
                "role": role,
                "content": content,
                "metadata_json": metadata_json or {},
                "created_at": _utc_now_iso(),
            }
        )

    def get_game(self, game_id):
        if game_id not in self.games:
            raise KeyError(game_id)
        return dict(self.games[game_id])

    def get_game_messages(self, game_id):
        if game_id not in self.messages:
            raise KeyError(game_id)
        return list(self.messages[game_id])

    def list_games_for_user(self, username):
        return [g for g in self.games.values() if g.get("user") == username]

    def create_feedback(self, game_id, user_id, feedback_text):
        _ = (game_id, user_id, feedback_text)
        return str(uuid.uuid4())

    def list_feedback(self, limit=500):
        _ = limit
        return []

    def enqueue_domain_event(self, event_type, aggregate_type, aggregate_id, payload_json):
        event = {
            "id": str(uuid.uuid4()),
            "event_type": event_type,
            "aggregate_type": aggregate_type,
            "aggregate_id": aggregate_id,
            "payload_json": dict(payload_json),
        }
        self.outbox_events.append(event)
        return event["id"]

    def get_runtime_setting(self, key: str):
        return self.runtime_settings.get(key)

    def set_runtime_setting(self, key: str, value_json: dict):
        self.runtime_settings[key] = dict(value_json)


def _build_config():
    return {
        "ambientacion": "Roma",
        "contexto_problema": "Intriga política",
        "relevancia_jugador": "Eres clave",
        "player_mission": "Descubrir al culpable",
        "narrativa_inicial": "Comienza la historia",
        "actors": [
            {
                "name": "Livia",
                "personality": "Calculadora",
                "mission": "Ocultar secretos",
                "background": "Senadora",
            }
        ],
    }


def test_engine_rehydrate_restores_state_and_avoids_duplicates(monkeypatch):
    monkeypatch.setattr(engine_module, "create_character_agent", lambda **_: object())
    monkeypatch.setattr(engine_module, "create_observer_agent", lambda **_: object())

    provider = _InMemoryProvider()
    game_id = provider.create_game("Partida", _build_config())
    provider.append_message(
        game_id,
        turn_number=1,
        role="player",
        content="hola",
        metadata_json={"author": "Usuario", "timestamp": "2026-02-18T10:00:00+00:00"},
    )
    provider.save_game_state(
        game_id,
        {
            "turn": 1,
            "metadata": {"continuation_decision": {"who_should_respond": "user"}},
            "next_action": "user_input",
            "max_turns": 12,
            "max_messages_before_user": 4,
        },
    )

    engine = GameEngine(persistence_provider=provider)
    resumed = engine.resume_game(game_id)
    assert resumed["loaded_from_memory"] is False

    status = engine.get_status(game_id)
    assert status["turn_current"] == 1
    assert status["turn_max"] == 12
    assert status["player_can_write"] is True
    assert len(status["messages"]) == 1
    assert status["messages"][0]["author"] == "Usuario"
    assert engine._registry[game_id].manager.state["metadata"]["player_name"] == "usuario"

    resumed_again = engine.resume_game(game_id)
    assert resumed_again["loaded_from_memory"] is True

    # Verifica que no se duplica al persistir de nuevo sin mensajes nuevos.
    session = engine._registry[game_id]
    engine._persist_session_state(game_id, session)
    persisted = provider.get_game_messages(game_id)
    assert len(persisted) == 1


def test_engine_resume_invalid_game_state_raises_value_error(monkeypatch):
    monkeypatch.setattr(engine_module, "create_character_agent", lambda **_: object())
    monkeypatch.setattr(engine_module, "create_observer_agent", lambda **_: object())

    provider = _InMemoryProvider()
    game_id = provider.create_game("Partida inválida", {"actors": []})
    engine = GameEngine(persistence_provider=provider)

    try:
        engine.resume_game(game_id)
        assert False, "Debe lanzar ValueError cuando no hay actores válidos"
    except ValueError:
        pass


def test_engine_rehydrate_preserves_actor_prompt_template_from_snapshot(monkeypatch):
    captured_templates: list[str | None] = []

    def _capture_character_agent(**kwargs):
        captured_templates.append(kwargs.get("prompt_template"))
        return object()

    monkeypatch.setattr(engine_module, "create_character_agent", _capture_character_agent)
    monkeypatch.setattr(engine_module, "create_observer_agent", lambda **_: object())

    provider = _InMemoryProvider()
    prompt_a = (
        "Eres {name}. {personality}. {player_name}. {scene_participants_block}"
        "{background_block}{mission_block}{extra_system_instruction_block}"
    )
    prompt_b = (
        "CAMBIO {name} / {personality} / {player_name} / {scene_participants_block}"
        "{background_block}{mission_block}{extra_system_instruction_block}"
    )
    provider.set_actor_prompt_template(prompt_a)
    game_id = provider.create_game("Partida", _build_config())

    engine = GameEngine(persistence_provider=provider)
    session = engine._build_session_from_setup(
        setup=_build_config(),
        max_turns=10,
        actor_prompt_template=provider.get_actor_prompt_template(),
        player_name="alice",
    )
    engine._registry[game_id] = session
    engine._persist_session_state(game_id, session)
    assert provider.get_game(game_id)["state_json"]["actor_prompt_template"] == prompt_a
    assert provider.get_game(game_id)["state_json"]["metadata"]["player_name"] == "alice"

    del engine._registry[game_id]
    provider.set_actor_prompt_template(prompt_b)
    captured_templates.clear()

    engine.resume_game(game_id)

    assert captured_templates == [prompt_a]
