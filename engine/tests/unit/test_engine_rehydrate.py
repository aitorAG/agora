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
            "state_json": {"turn": 0, "messages": [], "metadata": {}},
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
            "messages": [
                {
                    "author": "Usuario",
                    "content": "hola",
                    "timestamp": "2026-02-18T10:00:00+00:00",
                    "turn": 1,
                    "displayed": False,
                }
            ],
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
