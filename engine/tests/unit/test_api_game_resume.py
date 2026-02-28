"""Tests unitarios para POST /game/resume."""

from fastapi.testclient import TestClient

from src.api import routes as routes_module
from src.api.app import app
from src.api.schemas import AuthUserResponse


class _DummyEngine:
    def __init__(self, mode: str = "ok"):
        self.mode = mode

    def resume_game(self, session_id: str):
        if self.mode == "not_found":
            raise KeyError(session_id)
        if self.mode == "invalid":
            raise ValueError("invalid state")
        return {"session_id": session_id, "loaded_from_memory": False}

    def game_belongs_to_user(self, _session_id: str, _username: str):
        return True


def _client_with_engine(engine):
    app.dependency_overrides[routes_module.get_engine] = lambda: engine
    app.dependency_overrides[routes_module.get_current_user] = lambda: AuthUserResponse(
        id="u1",
        username="usuario",
        is_active=True,
    )
    return TestClient(app)


def test_resume_game_existing():
    engine = _DummyEngine(mode="ok")
    client = _client_with_engine(engine)
    try:
        res = client.post("/game/resume", json={"session_id": "sid-1"})
        assert res.status_code == 200
        assert res.json()["session_id"] == "sid-1"
    finally:
        app.dependency_overrides.clear()


def test_resume_game_not_found():
    engine = _DummyEngine(mode="not_found")
    client = _client_with_engine(engine)
    try:
        res = client.post("/game/resume", json={"session_id": "sid-404"})
        assert res.status_code == 404
        assert res.json()["detail"] == "Session not found"
    finally:
        app.dependency_overrides.clear()


def test_resume_game_invalid_state():
    engine = _DummyEngine(mode="invalid")
    client = _client_with_engine(engine)
    try:
        res = client.post("/game/resume", json={"session_id": "sid-bad"})
        assert res.status_code == 400
        assert res.json()["detail"] == "Session cannot be resumed"
    finally:
        app.dependency_overrides.clear()
