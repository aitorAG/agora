"""Tests unitarios para /game/context."""

from fastapi.testclient import TestClient

from src.api import routes as routes_module
from src.api.app import app
from src.api.schemas import AuthUserResponse


class _DummyEngine:
    def game_belongs_to_user(self, _session_id, _username):
        return True

    def get_context(self, _session_id):
        return {
            "player_mission": "Mision privada",
            "player_public_mission": "Punto de partida visible",
            "ambientacion": "Roma",
            "contexto_problema": "Problema",
            "relevancia_jugador": "Relevancia",
            "narrativa_inicial": "Inicio",
            "characters": [
                {
                    "name": "Bruto",
                    "personality": "Dubitativo",
                    "mission": "Decidir",
                    "public_mission": "Pide cautela",
                    "background": "Senador",
                    "presencia_escena": "Curia",
                }
            ],
        }


def _client_with_engine(engine):
    app.dependency_overrides[routes_module.get_engine] = lambda: engine
    app.dependency_overrides[routes_module.get_current_user] = lambda: AuthUserResponse(
        id="u1",
        username="usuario",
        is_active=True,
    )
    return TestClient(app)


def test_game_context_returns_public_mission_fields():
    engine = _DummyEngine()
    client = _client_with_engine(engine)
    try:
        res = client.get("/game/context", params={"session_id": "sid-1"})
        assert res.status_code == 200
        body = res.json()
        assert body["player_public_mission"] == "Punto de partida visible"
        assert body["characters"][0]["public_mission"] == "Pide cautela"
    finally:
        app.dependency_overrides.clear()
