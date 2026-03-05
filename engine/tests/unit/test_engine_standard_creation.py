"""Tests de creación standard en motor."""

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

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

    def create_feedback(self, game_id, user_id, feedback_text):
        _ = (game_id, user_id, feedback_text)
        return str(uuid.uuid4())

    def list_feedback(self, limit=500):
        _ = limit
        return []


def _standard_setup():
    return {
        "titulo": "Plantilla estándar",
        "descripcion_breve": "Descripcion de plantilla",
        "ambientacion": "Roma",
        "contexto_problema": "Intriga",
        "relevancia_jugador": "Clave",
        "player_mission": "Evitar atentado",
        "narrativa_inicial": "Inicio",
        "actors": [
            {
                "name": "Bruto",
                "personality": "Dubitativo",
                "mission": "Elegir bando",
                "background": "Senador",
                "presencia_escena": "Curia",
            }
        ],
    }


def test_create_game_from_setup_persists_standard_metadata(monkeypatch):
    monkeypatch.setattr(
        engine_module,
        "create_character_agent",
        lambda **kwargs: SimpleNamespace(name=kwargs["name"]),
    )
    monkeypatch.setattr(engine_module, "create_observer_agent", lambda **_: object())
    monkeypatch.setattr(
        engine_module,
        "run_character_response",
        lambda agent, *_args, **_kwargs: {
            "author": agent.name,
            "message": f"Mensaje de {agent.name}",
        },
    )
    monkeypatch.setattr(engine_module.random, "shuffle", lambda seq: None)

    provider = _InMemoryProvider()
    engine = GameEngine(persistence_provider=provider)
    game_id, setup = engine.create_game_from_setup(
        setup=_standard_setup(),
        username="usuario",
        standard_template_id="rome_caesar_harry",
        template_version="1.0.0",
    )

    assert setup["titulo"] == "Plantilla estándar"
    game = provider.get_game(game_id)
    assert game["game_mode"] == "standard"
    assert game["standard_template_id"] == "rome_caesar_harry"
    assert game["template_version"] == "1.0.0"
    assert game["config_json"]["titulo"] == "Plantilla estándar"
    assert game["state_json"]["turn"] == 0
    assert game["state_json"]["next_action"] == "user_input"
    assert len(provider.get_game_messages(game_id)) == 1


def test_create_game_from_setup_custom_persists_template_metadata(monkeypatch):
    monkeypatch.setattr(engine_module, "create_character_agent", lambda **_: object())
    monkeypatch.setattr(engine_module, "create_observer_agent", lambda **_: object())
    monkeypatch.setattr(
        engine_module,
        "run_one_step",
        lambda *_args, **_kwargs: {"next_action": "user_input", "game_ended": False, "events": []},
    )

    provider = _InMemoryProvider()
    engine = GameEngine(persistence_provider=provider)
    game_id, _setup = engine.create_game_from_setup(
        setup=_standard_setup(),
        username="usuario",
        game_mode="custom",
        standard_template_id="madrid_1920_el_piernas",
        template_version="2.1.0",
    )

    game = provider.get_game(game_id)
    assert game["game_mode"] == "custom"
    assert game["standard_template_id"] == "madrid_1920_el_piernas"
    assert game["template_version"] == "2.1.0"


def test_standard_warmup_uses_half_of_randomized_actors_without_observer(monkeypatch):
    calls = []

    monkeypatch.setattr(
        engine_module,
        "create_character_agent",
        lambda **kwargs: SimpleNamespace(name=kwargs["name"]),
    )
    monkeypatch.setattr(engine_module, "create_observer_agent", lambda **_: object())
    monkeypatch.setattr(
        engine_module,
        "run_character_response",
        lambda agent, _state, **kwargs: calls.append(
            {
                "name": agent.name,
                "extra_system_instruction": kwargs.get("extra_system_instruction"),
            }
        ) or {
            "author": agent.name,
            "message": f"Mensaje de {agent.name}",
        },
    )
    monkeypatch.setattr(
        engine_module.random,
        "shuffle",
        lambda seq: seq.__setitem__(slice(None), ["Casca", "Bruto", "Marco", "Livia"]),
    )

    setup = _standard_setup()
    setup["actors"] = [
        dict(setup["actors"][0], name="Bruto"),
        dict(setup["actors"][0], name="Livia"),
        dict(setup["actors"][0], name="Marco"),
        dict(setup["actors"][0], name="Casca"),
    ]
    provider = _InMemoryProvider()
    engine = GameEngine(persistence_provider=provider)

    game_id, _setup = engine.create_game_from_setup(
        setup=setup,
        username="usuario",
        standard_template_id="rome_caesar_harry",
        template_version="1.0.0",
    )

    assert [call["name"] for call in calls] == ["Casca", "Bruto"]
    assert isinstance(calls[0]["extra_system_instruction"], str)
    assert "dirigiéndote al jugador" in calls[0]["extra_system_instruction"]
    assert calls[1]["extra_system_instruction"] is None
    game = provider.get_game(game_id)
    assert game["state_json"]["next_action"] == "user_input"
    assert len(provider.get_game_messages(game_id)) == 2


def test_create_game_from_setup_rejects_invalid_contract():
    provider = _InMemoryProvider()
    engine = GameEngine(persistence_provider=provider)
    broken = _standard_setup()
    broken.pop("player_mission")

    try:
        engine.create_game_from_setup(setup=broken, username="usuario")
        assert False, "Debe lanzar ValueError cuando falta un campo obligatorio del setup"
    except ValueError as exc:
        assert "player_mission" in str(exc)
