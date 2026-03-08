"""Tests unitarios de /game/new para seed y defaults."""

from fastapi.testclient import TestClient

from src.api import routes as routes_module
from src.api.app import app
from src.api.schemas import AuthUserResponse


class _DummyEngine:
    def __init__(self):
        self.calls = []

    def create_game(
        self,
        theme=None,
        era=None,
        topic=None,
        style=None,
        num_actors=3,
        max_turns=10,
        username=None,
    ):
        self.calls.append(
            {
                "theme": theme,
                "era": era,
                "topic": topic,
                "style": style,
                "num_actors": num_actors,
                "max_turns": max_turns,
                "username": username,
            }
        )
        setup = {
            "player_mission": "Misión",
            "narrativa_inicial": "Inicio",
            "actors": [{"name": "A", "personality": "P", "mission": "M", "background": "B"}],
        }
        return "sid-1", setup

    def get_status(self, _session_id):
        return {
            "turn_current": 0,
            "turn_max": 10,
            "player_can_write": True,
            "game_finished": False,
            "messages": [],
        }


def _client_with_engine(engine):
    app.dependency_overrides[routes_module.get_engine] = lambda: engine
    app.dependency_overrides[routes_module.get_current_user] = lambda: AuthUserResponse(
        id="u1",
        username="usuario",
        is_active=True,
    )
    return TestClient(app)


def test_new_game_empty_body_uses_env_theme_and_default_num_actors(monkeypatch):
    monkeypatch.setenv("GAME_THEME", "Tema desde .env")
    engine = _DummyEngine()
    client = _client_with_engine(engine)
    try:
        res = client.post("/game/new", json={})
        assert res.status_code == 200
        assert engine.calls[0]["theme"] == "Tema desde .env"
        assert engine.calls[0]["num_actors"] == 3
        assert engine.calls[0]["username"] == "usuario"
    finally:
        app.dependency_overrides.clear()


def test_new_game_partial_theme_uses_custom_seed_without_env(monkeypatch):
    monkeypatch.setenv("GAME_THEME", "Tema desde .env")
    engine = _DummyEngine()
    client = _client_with_engine(engine)
    try:
        res = client.post("/game/new", json={"theme": "Tema: llegar a un acuerdo"})
        assert res.status_code == 200
        assert engine.calls[0]["theme"] == "Tema: llegar a un acuerdo"
        assert engine.calls[0]["num_actors"] == 3
    finally:
        app.dependency_overrides.clear()


def test_new_game_num_actors_only_does_not_use_env_theme(monkeypatch):
    monkeypatch.setenv("GAME_THEME", "Tema desde .env")
    engine = _DummyEngine()
    client = _client_with_engine(engine)
    try:
        res = client.post("/game/new", json={"num_actors": 5})
        assert res.status_code == 200
        assert engine.calls[0]["theme"] is None
        assert engine.calls[0]["num_actors"] == 5
    finally:
        app.dependency_overrides.clear()


def test_new_game_accepts_structured_custom_seed():
    engine = _DummyEngine()
    client = _client_with_engine(engine)
    try:
        res = client.post(
            "/game/new",
            json={
                "era": "Roma republicana tardía",
                "topic": "Desactivar una conspiración del Senado",
                "style": "Thriller político",
                "num_actors": 4,
            },
        )
        assert res.status_code == 200
        assert engine.calls[0]["era"] == "Roma republicana tardía"
        assert engine.calls[0]["topic"] == "Desactivar una conspiración del Senado"
        assert engine.calls[0]["style"] == "Thriller político"
        assert engine.calls[0]["theme"] is None
    finally:
        app.dependency_overrides.clear()


def test_new_game_rejects_theme_and_structured_seed_together():
    engine = _DummyEngine()
    client = _client_with_engine(engine)
    try:
        res = client.post("/game/new", json={"theme": "algo", "era": "Roma"})
        assert res.status_code == 422
        assert res.json()["detail"] == "Usa theme o los campos custom estructurados, pero no ambos a la vez."
    finally:
        app.dependency_overrides.clear()


def test_new_game_rejects_structured_seed_with_too_many_words():
    engine = _DummyEngine()
    client = _client_with_engine(engine)
    try:
        era = " ".join(["a"] * 31)
        res = client.post("/game/new", json={"era": era})
        assert res.status_code == 422
        assert res.json()["detail"] == "El campo Época/contexto no puede superar 30 palabras."
    finally:
        app.dependency_overrides.clear()


def test_new_game_rejects_num_actors_below_range():
    engine = _DummyEngine()
    client = _client_with_engine(engine)
    try:
        res = client.post("/game/new", json={"num_actors": 0})
        assert res.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_new_game_rejects_num_actors_above_range():
    engine = _DummyEngine()
    client = _client_with_engine(engine)
    try:
        res = client.post("/game/new", json={"num_actors": 6})
        assert res.status_code == 422
    finally:
        app.dependency_overrides.clear()
