"""Tests unitarios para GET /game/list."""

from fastapi.testclient import TestClient

from src.api import routes as routes_module
from src.api.app import app
from src.api.schemas import AuthUserResponse


class _DummyEngine:
    def __init__(self, games):
        self._games = games

    def list_games(self, username: str):
        assert username == "usuario"
        return self._games


def _client_with_engine(engine):
    app.dependency_overrides[routes_module.get_engine] = lambda: engine
    app.dependency_overrides[routes_module.get_current_user] = lambda: AuthUserResponse(
        id="u1",
        username="usuario",
        is_active=True,
    )
    return TestClient(app)


def test_game_list_with_data():
    engine = _DummyEngine(
        [
            {
                "id": "g1",
                "title": "Partida 1",
                "status": "active",
                "created_at": "2026-01-01T10:00:00+00:00",
                "updated_at": "2026-01-01T10:05:00+00:00",
            }
        ]
    )
    client = _client_with_engine(engine)
    try:
        res = client.get("/game/list")
        assert res.status_code == 200
        body = res.json()
        assert "games" in body
        assert len(body["games"]) == 1
        assert body["games"][0]["id"] == "g1"
    finally:
        app.dependency_overrides.clear()


def test_game_list_empty():
    engine = _DummyEngine([])
    client = _client_with_engine(engine)
    try:
        res = client.get("/game/list")
        assert res.status_code == 200
        assert res.json() == {"games": []}
    finally:
        app.dependency_overrides.clear()
