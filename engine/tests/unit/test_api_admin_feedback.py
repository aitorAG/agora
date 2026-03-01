"""Tests unitarios de endpoints admin de feedback."""

from fastapi.testclient import TestClient

from src.api import routes as routes_module
from src.api.app import app
from src.api.schemas import AuthUserResponse


class _AdminFeedbackEngineDummy:
    def list_feedback(self, limit: int = 500):
        _ = limit
        return [
            {
                "id": "fb-1",
                "game_id": "g-1",
                "user_id": "u-1",
                "username": "alice",
                "feedback_text": "Texto de feedback",
                "created_at": "2026-03-01T10:00:00+00:00",
            }
        ]


def _admin_user():
    return AuthUserResponse(id="u-admin", username="admin", is_active=True, role="admin")


def test_admin_feedback_list_returns_items():
    engine = _AdminFeedbackEngineDummy()
    app.dependency_overrides[routes_module.get_engine] = lambda: engine
    app.dependency_overrides[routes_module.require_admin] = _admin_user
    client = TestClient(app)
    try:
        res = client.get("/admin/feedback/list")
        assert res.status_code == 200
        body = res.json()
        assert len(body["items"]) == 1
        assert body["items"][0]["feedback_text"] == "Texto de feedback"
        assert body["items"][0]["username"] == "alice"
    finally:
        app.dependency_overrides.clear()


def test_admin_feedback_page_is_served():
    app.dependency_overrides[routes_module.require_admin] = _admin_user
    client = TestClient(app)
    try:
        res = client.get("/admin/feedback/")
        assert res.status_code == 200
        assert "Feedback de usuarios" in res.text
    finally:
        app.dependency_overrides.clear()
