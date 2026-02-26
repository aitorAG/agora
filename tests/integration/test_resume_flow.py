"""Flujo integración: crear -> jugar -> reiniciar proceso -> reanudar."""

import uuid
from datetime import datetime, timezone

import src.core.engine as engine_module
from src.core.engine import GameEngine
from src.persistence.provider import PersistenceProvider


def _utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


class _InMemoryProvider(PersistenceProvider):
    def __init__(self):
        self.games = {}
        self.messages = {}

    def create_game(
        self,
        title,
        config_json,
        username=None,
        game_mode="custom",
        standard_template_id=None,
        template_version=None,
    ):
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


def test_resume_flow_create_play_restart_resume(monkeypatch):
    def fake_setup_task(*_args, **_kwargs):
        return {
            "titulo": "Caso en la villa",
            "ambientacion": "Roma",
            "contexto_problema": "Robo misterioso",
            "relevancia_jugador": "Eres investigador",
            "player_mission": "Encuentra al culpable",
            "narrativa_inicial": "La noche comienza",
            "actors": [
                {
                    "name": "Livia",
                    "personality": "Fría",
                    "mission": "Proteger su reputación",
                    "background": "Noble",
                }
            ],
        }

    def fake_run_one_step(
        manager,
        _character_agents,
        _observer_agent,
        _max_turns,
        current_next_action,
        pending_user_text=None,
        **_kwargs,
    ):
        if pending_user_text is not None:
            manager.add_message("Usuario", pending_user_text)
            manager.add_message("Livia", "No sé nada de eso.")
            manager.increment_turn()
            return {"next_action": "user_input", "events": [], "game_ended": False}

        if current_next_action == "character":
            manager.add_message("Livia", "He llegado al salón.")
            return {"next_action": "user_input", "events": [], "game_ended": False}

        return {"next_action": "user_input", "events": [], "game_ended": False}

    monkeypatch.setattr(engine_module, "create_guionista_agent", lambda: object())
    monkeypatch.setattr(engine_module, "run_setup_task", fake_setup_task)
    monkeypatch.setattr(engine_module, "create_character_agent", lambda **_: object())
    monkeypatch.setattr(engine_module, "create_observer_agent", lambda **_: object())
    monkeypatch.setattr(engine_module, "run_one_step", fake_run_one_step)

    provider = _InMemoryProvider()
    engine_1 = GameEngine(persistence_provider=provider)

    game_id, _setup = engine_1.create_game()
    engine_1.player_input(game_id, "Primera pista")

    persisted_before_restart = provider.get_game_messages(game_id)
    assert len(persisted_before_restart) >= 2

    # Simula reinicio de proceso: nuevo engine sin registry en memoria.
    engine_2 = GameEngine(persistence_provider=provider)
    resumed = engine_2.resume_game(game_id)
    assert resumed["session_id"] == game_id

    status = engine_2.get_status(game_id)
    assert status["turn_current"] >= 1
    assert len(status["messages"]) >= 2

    engine_2.player_input(game_id, "Segunda pista")
    persisted_after_resume = provider.get_game_messages(game_id)
    assert len(persisted_after_resume) > len(persisted_before_restart)
