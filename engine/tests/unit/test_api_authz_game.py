"""Tests de autorización en rutas de juego."""

from fastapi.testclient import TestClient

from src.api import dependencies as dependencies_module
from src.api import routes as routes_module
from src.api.app import app
from src.api.schemas import AuthUserResponse


class _EngineListDummy:
    def __init__(self):
        self.called_with = None

    def list_games(self, username: str):
        self.called_with = username
        return []


class _EngineListByUserDummy:
    def list_games(self, username: str):
        if username == "alice":
            return [{"id": "g-alice", "title": "Partida Alice", "status": "active"}]
        if username == "bob":
            return [{"id": "g-bob", "title": "Partida Bob", "status": "active"}]
        return []


class _EngineOwnershipDummy:
    def __init__(self, is_owner: bool):
        self.is_owner = is_owner

    def game_belongs_to_user(self, _session_id: str, _username: str):
        return self.is_owner

    def resume_game(self, session_id: str):
        return {"session_id": session_id, "loaded_from_memory": False}


def test_game_list_requires_auth_without_override(monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    app.dependency_overrides.clear()
    client = TestClient(app)
    res = client.get("/game/list")
    assert res.status_code == 401


def test_game_list_uses_authenticated_username():
    engine = _EngineListDummy()
    app.dependency_overrides[routes_module.get_engine] = lambda: engine
    app.dependency_overrides[routes_module.get_current_user] = lambda: AuthUserResponse(
        id="u-alice",
        username="alice",
        is_active=True,
    )
    client = TestClient(app)
    try:
        res = client.get("/game/list")
        assert res.status_code == 200
        assert engine.called_with == "alice"
    finally:
        app.dependency_overrides.clear()


def test_game_resume_returns_not_found_when_not_owner():
    engine = _EngineOwnershipDummy(is_owner=False)
    app.dependency_overrides[routes_module.get_engine] = lambda: engine
    app.dependency_overrides[routes_module.get_current_user] = lambda: AuthUserResponse(
        id="u-alice",
        username="alice",
        is_active=True,
    )
    client = TestClient(app)
    try:
        res = client.post("/game/resume", json={"session_id": "sid-1"})
        assert res.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_game_list_is_isolated_by_authenticated_user_after_register(monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    monkeypatch.setattr(
        routes_module,
        "create_user",
        lambda username, _password: {
            "id": f"u-{username.strip().lower()}",
            "username": username.strip().lower(),
            "is_active": True,
        },
    )
    monkeypatch.setattr(
        dependencies_module,
        "get_user_by_username",
        lambda username: {
            "id": f"u-{username.strip().lower()}",
            "username": username.strip().lower(),
            "is_active": True,
            "password_hash": "x",
        },
    )

    engine = _EngineListByUserDummy()
    app.dependency_overrides[routes_module.get_engine] = lambda: engine
    client_a = TestClient(app)
    client_b = TestClient(app)
    try:
        reg_a = client_a.post("/auth/register", json={"username": "alice", "password": "secret123"})
        assert reg_a.status_code == 201
        reg_b = client_b.post("/auth/register", json={"username": "bob", "password": "secret123"})
        assert reg_b.status_code == 201

        list_a = client_a.get("/game/list")
        assert list_a.status_code == 200
        assert [g["id"] for g in list_a.json()["games"]] == ["g-alice"]

        list_b = client_b.get("/game/list")
        assert list_b.status_code == 200
        assert [g["id"] for g in list_b.json()["games"]] == ["g-bob"]
    finally:
        app.dependency_overrides.clear()
