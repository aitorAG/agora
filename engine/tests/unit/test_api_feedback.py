"""Tests unitarios de /game/feedback."""

from fastapi.testclient import TestClient

from src.api import routes as routes_module
from src.api.app import app
from src.api.schemas import AuthUserResponse


class _FeedbackEngineDummy:
    def __init__(self, is_owner: bool = True):
        self.is_owner = is_owner
        self.feedback_calls = []

    def game_belongs_to_user(self, _session_id: str, _username: str):
        return self.is_owner

    def submit_feedback(self, game_id: str, user_id: str, feedback_text: str) -> str:
        self.feedback_calls.append(
            {
                "game_id": game_id,
                "user_id": user_id,
                "feedback_text": feedback_text,
            }
        )
        return "fb-1"


def _client_with_engine(engine):
    app.dependency_overrides[routes_module.get_engine] = lambda: engine
    app.dependency_overrides[routes_module.get_current_user] = lambda: AuthUserResponse(
        id="u-1",
        username="alice",
        is_active=True,
    )
    return TestClient(app)


def test_feedback_stores_payload_with_user_and_session():
    engine = _FeedbackEngineDummy(is_owner=True)
    client = _client_with_engine(engine)
    try:
        res = client.post("/game/feedback", json={"session_id": "sid-1", "text": "Buen ritmo narrativo"})
        assert res.status_code == 201
        body = res.json()
        assert body["feedback_id"] == "fb-1"
        assert body["session_id"] == "sid-1"
        assert body["user_id"] == "u-1"
        assert engine.feedback_calls == [
            {
                "game_id": "sid-1",
                "user_id": "u-1",
                "feedback_text": "Buen ritmo narrativo",
            }
        ]
    finally:
        app.dependency_overrides.clear()


def test_feedback_rejects_non_owner_as_not_found():
    engine = _FeedbackEngineDummy(is_owner=False)
    client = _client_with_engine(engine)
    try:
        res = client.post("/game/feedback", json={"session_id": "sid-1", "text": "x"})
        assert res.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_feedback_rejects_blank_text():
    engine = _FeedbackEngineDummy(is_owner=True)
    client = _client_with_engine(engine)
    try:
        res = client.post("/game/feedback", json={"session_id": "sid-1", "text": "   "})
        assert res.status_code == 422
    finally:
        app.dependency_overrides.clear()
