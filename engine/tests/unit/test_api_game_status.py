"""Tests unitarios para GET /game/status."""

from fastapi.testclient import TestClient

from src.api import routes as routes_module
from src.api.app import app
from src.api.schemas import AuthUserResponse


class _DummyEngine:
    def game_belongs_to_user(self, _session_id: str, _username: str):
        return True

    def get_status(self, _session_id: str):
        return {
            "turn_current": 1,
            "turn_max": 10,
            "current_speaker": "",
            "player_can_write": True,
            "game_finished": False,
            "result": None,
            "messages": [
                {"author": "Usuario", "content": "Hola", "timestamp": None, "turn": 1},
                {"author": "Livia", "content": "Te escucho.", "timestamp": None, "turn": 1},
            ],
        }


def _client_with_engine(engine):
    app.dependency_overrides[routes_module.get_engine] = lambda: engine
    app.dependency_overrides[routes_module.get_current_user] = lambda: AuthUserResponse(
        id="u1",
        username="alice",
        is_active=True,
    )
    return TestClient(app)


def test_status_uses_authenticated_username_for_player_messages():
    client = _client_with_engine(_DummyEngine())
    try:
        res = client.get("/game/status", params={"session_id": "sid-1"})
        assert res.status_code == 200
        body = res.json()
        assert body["messages"][0]["author"] == "alice"
        assert body["messages"][1]["author"] == "Livia"
    finally:
        app.dependency_overrides.clear()
