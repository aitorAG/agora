"""Tests unitarios para flujo standard en API."""

from fastapi.testclient import TestClient

from src.api import routes as routes_module
from src.api.app import app
from src.api.schemas import AuthUserResponse
from src.core.standard_games import StandardTemplateError


class _DummyEngine:
    def __init__(self):
        self.calls = []

    def create_game(self, **_kwargs):
        raise AssertionError("El flujo standard no debe invocar create_game()")

    def create_game_from_setup(
        self,
        setup,
        max_turns=10,
        username=None,
        standard_template_id=None,
        template_version=None,
    ):
        self.calls.append(
            {
                "setup": setup,
                "max_turns": max_turns,
                "username": username,
                "standard_template_id": standard_template_id,
                "template_version": template_version,
            }
        )
        return "sid-standard", setup

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


def _sample_setup():
    return {
        "titulo": "Plantilla",
        "ambientacion": "Roma",
        "contexto_problema": "Problema",
        "relevancia_jugador": "Relevancia",
        "player_mission": "Mision",
        "narrativa_inicial": "Inicio",
        "actors": [
            {
                "name": "Bruto",
                "personality": "Dubitativo",
                "mission": "Decidir",
                "background": "Senador",
                "presencia_escena": "Curia",
            }
        ],
    }


def test_standard_start_uses_prebuilt_setup_without_guionista(monkeypatch):
    engine = _DummyEngine()
    client = _client_with_engine(engine)
    monkeypatch.setattr(
        routes_module,
        "load_standard_template",
        lambda _template_id: {
            "template_id": "rome_caesar_harry",
            "template_version": "1.0.0",
            "setup": _sample_setup(),
            "manifest": {},
        },
    )
    try:
        res = client.post("/game/standard/start", json={"template_id": "rome_caesar_harry"})
        assert res.status_code == 200
        body = res.json()
        assert body["session_id"] == "sid-standard"
        assert body["game_mode"] == "standard"
        assert body["standard_template_id"] == "rome_caesar_harry"
        assert engine.calls[0]["username"] == "usuario"
        assert engine.calls[0]["standard_template_id"] == "rome_caesar_harry"
    finally:
        app.dependency_overrides.clear()


def test_standard_start_returns_400_for_invalid_template(monkeypatch):
    engine = _DummyEngine()
    client = _client_with_engine(engine)
    monkeypatch.setattr(
        routes_module,
        "load_standard_template",
        lambda _template_id: (_ for _ in ()).throw(StandardTemplateError("broken config")),
    )
    try:
        res = client.post("/game/standard/start", json={"template_id": "broken"})
        assert res.status_code == 400
        assert "Invalid standard template" in res.json()["detail"]
    finally:
        app.dependency_overrides.clear()
