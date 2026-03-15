"""Tests del alias visible del jugador en el SSE de /game/turn."""

import json

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
        yield {
            "type": "message",
            "message": {"author": "Usuario", "content": "Respuesta", "timestamp": None, "turn": 1},
        }


def _client_with_engine(engine):
    app.dependency_overrides[routes_module.get_engine] = lambda: engine
    app.dependency_overrides[routes_module.get_current_user] = lambda: AuthUserResponse(
        id="u1",
        username="alice",
        is_active=True,
    )
    return TestClient(app)


def test_turn_stream_uses_authenticated_username_for_player_messages():
    client = _client_with_engine(_DummyEngine())
    try:
        res = client.post("/game/turn", json={"session_id": "sid-1", "text": "Hola"})
        assert res.status_code == 200
        blocks = [block for block in res.text.split("\n\n") if block.strip()]
        assert len(blocks) == 1
        data_line = next(line for line in blocks[0].splitlines() if line.startswith("data:"))
        payload = json.loads(data_line[5:].strip())
        assert payload["message"]["author"] == "alice"
        assert payload["message"]["content"] == "Respuesta"
    finally:
        app.dependency_overrides.clear()
