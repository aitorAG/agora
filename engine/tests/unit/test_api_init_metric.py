"""Tests para ingesta de TTFA cliente en /game/init-metric."""

from fastapi.testclient import TestClient

from src import observability as obs_module
from src.api import routes as routes_module
from src.api.app import app
from src.api.schemas import AuthUserResponse


class _EngineOwnershipDummy:
    def __init__(self, is_owner: bool):
        self.is_owner = is_owner

    def game_belongs_to_user(self, _session_id: str, _username: str):
        return self.is_owner


class _ProviderDummy:
    @staticmethod
    def get_game(_session_id: str):
        return {
            "id": "sid-1",
            "user_id": "u-1",
            "user": "alice",
            "game_mode": "custom",
        }


def test_init_metric_emits_client_ttfa_event(monkeypatch):
    events = []
    monkeypatch.setattr(obs_module, "emit_event", lambda event_type, metadata=None: events.append((event_type, metadata)))

    app.dependency_overrides[routes_module.get_engine] = lambda: _EngineOwnershipDummy(is_owner=True)
    app.dependency_overrides[routes_module.get_current_user] = lambda: AuthUserResponse(
        id="u-1",
        username="alice",
        is_active=True,
    )
    monkeypatch.setattr(routes_module, "get_persistence_provider", lambda: _ProviderDummy())
    client = TestClient(app)
    try:
        response = client.post(
            "/game/init-metric",
            json={"session_id": "sid-1", "ttfa_client_ms": 812},
        )
        assert response.status_code == 200
        assert response.json() == {"ok": True}
        assert len(events) == 1
        event_type, metadata = events[0]
        assert event_type == "game_init_client"
        assert metadata["game_id"] == "sid-1"
        assert metadata["game_mode"] == "custom"
        assert metadata["duration_ms"] == 812
    finally:
        app.dependency_overrides.clear()


def test_init_metric_returns_404_when_not_owner(monkeypatch):
    app.dependency_overrides[routes_module.get_engine] = lambda: _EngineOwnershipDummy(is_owner=False)
    app.dependency_overrides[routes_module.get_current_user] = lambda: AuthUserResponse(
        id="u-1",
        username="alice",
        is_active=True,
    )
    monkeypatch.setattr(routes_module, "get_persistence_provider", lambda: _ProviderDummy())
    client = TestClient(app)
    try:
        response = client.post(
            "/game/init-metric",
            json={"session_id": "sid-other", "ttfa_client_ms": 150},
        )
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()
