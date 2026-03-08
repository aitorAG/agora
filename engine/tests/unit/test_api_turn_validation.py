"""Tests de validación de límites en /game/turn."""

from fastapi.testclient import TestClient

from src.api import routes as routes_module
from src.api.app import app
from src.api.schemas import AuthUserResponse


class _DummyEngine:
    def game_belongs_to_user(self, _game_id, _username):
        return True

    def get_status(self, _session_id):
        return {
            "turn_current": 1,
            "turn_max": 10,
            "current_speaker": "",
            "player_can_write": True,
            "game_finished": False,
            "messages": [],
        }

    def execute_turn_stream(self, _session_id, _text, user_exit=False):
        _ = user_exit
        yield {"type": "observer_thinking"}


def _client_with_engine(engine):
    app.dependency_overrides[routes_module.get_engine] = lambda: engine
    app.dependency_overrides[routes_module.get_current_user] = lambda: AuthUserResponse(
        id="u1",
        username="usuario",
        is_active=True,
    )
    return TestClient(app)


def test_turn_rejects_more_than_five_sentences():
    engine = _DummyEngine()
    client = _client_with_engine(engine)
    try:
        text = "Uno. Dos. Tres. Cuatro. Cinco. Seis."
        res = client.post("/game/turn", json={"session_id": "sid-1", "text": text})
        assert res.status_code == 422
        assert res.json()["detail"] == "El mensaje del usuario no puede superar 5 frases."
    finally:
        app.dependency_overrides.clear()


def test_turn_rejects_message_without_punctuation_if_too_long():
    engine = _DummyEngine()
    client = _client_with_engine(engine)
    try:
        text = " ".join(["a"] * 121)
        res = client.post("/game/turn", json={"session_id": "sid-1", "text": text})
        assert res.status_code == 422
        assert res.json()["detail"] == "El mensaje del usuario no puede superar 120 palabras."
    finally:
        app.dependency_overrides.clear()
