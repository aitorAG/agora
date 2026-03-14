"""Tests del streaming incremental de turnos en GameEngine."""

from contextlib import contextmanager
from datetime import datetime, timezone
import uuid

import src.core.engine as engine_module
from src.core.engine import GameEngine, GameSession
from src.manager import ConversationManager
from src.persistence.provider import PersistenceProvider


def _utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


class _InMemoryProvider(PersistenceProvider):
    def __init__(self):
        self.games: dict[str, dict] = {}
        self.messages: dict[str, list[dict]] = {}
        self.outbox_events: list[dict] = []

    def create_game(
        self,
        title,
        config_json,
        username=None,
        game_mode="custom",
        standard_template_id=None,
        template_version=None,
    ) -> str:
        game_id = str(uuid.uuid4())
        now = _utc_now_iso()
        self.games[game_id] = {
            "id": game_id,
            "title": title,
            "status": "active",
            "user": username or "usuario",
            "user_id": "u1",
            "game_mode": game_mode,
            "standard_template_id": standard_template_id,
            "template_version": template_version,
            "created_at": now,
            "updated_at": now,
            "config_json": dict(config_json),
            "state_json": {"turn": 0, "metadata": {}, "next_action": "character"},
        }
        self.messages[game_id] = []
        return game_id

    def save_game_state(self, game_id, state_json):
        self.games[game_id]["state_json"] = dict(state_json)

    def append_message(self, game_id, turn_number, role, content, metadata_json=None):
        self.messages[game_id].append(
            {
                "id": str(uuid.uuid4()),
                "game_id": game_id,
                "turn_number": int(turn_number),
                "author": (metadata_json or {}).get("author") or role,
                "role": role,
                "content": content,
                "metadata_json": metadata_json or {},
                "created_at": _utc_now_iso(),
            }
        )

    def get_game(self, game_id):
        if game_id not in self.games:
            raise KeyError(game_id)
        return dict(self.games[game_id])

    def get_game_messages(self, game_id):
        if game_id not in self.messages:
            raise KeyError(game_id)
        return list(self.messages[game_id])

    def list_games_for_user(self, username):
        return [g for g in self.games.values() if g.get("user") == username]

    def create_feedback(self, game_id, user_id, feedback_text):
        _ = (game_id, user_id, feedback_text)
        return str(uuid.uuid4())

    def list_feedback(self, limit=500):
        _ = limit
        return []

    def enqueue_domain_event(self, event_type, aggregate_type, aggregate_id, payload_json):
        event = {
            "id": str(uuid.uuid4()),
            "event_type": event_type,
            "aggregate_type": aggregate_type,
            "aggregate_id": aggregate_id,
            "payload_json": dict(payload_json),
        }
        self.outbox_events.append(event)
        return event["id"]


@contextmanager
def _no_trace(*_args, **_kwargs):
    yield


def test_execute_turn_stream_emits_actor_messages_before_next_actor_starts(monkeypatch):
    provider = _InMemoryProvider()
    engine = GameEngine(provider)
    game_id = provider.create_game("Partida", {"actors": [{"name": "Livia"}, {"name": "Marco"}]})

    session = GameSession(
        manager=ConversationManager(),
        character_agents={"Livia": object(), "Marco": object()},
        observer_agent=object(),
        setup={"actors": [{"name": "Livia"}, {"name": "Marco"}]},
        max_turns=10,
        next_action="user_input",
    )
    engine._registry[game_id] = session

    monkeypatch.setattr(engine_module, "trace_interaction", _no_trace)

    call_index = {"value": 0}

    def fake_run_one_step(
        manager,
        _character_agents,
        _observer_agent,
        _max_turns,
        *,
        current_next_action,
        character_stream_sink=None,
        event_sink=None,
        **_kwargs,
    ):
        idx = call_index["value"]
        call_index["value"] += 1

        if idx == 0:
            assert current_next_action == "user_input"
            event_sink({"type": "observer_thinking"})
            return {"next_action": "character", "game_ended": False, "events": []}

        if idx == 1:
            assert current_next_action == "character"
            event_sink({"type": "message_start", "author": "Livia"})
            character_stream_sink("Ave")
            event_sink({"type": "observer_thinking"})
            manager.add_message("Livia", "Ave, viajero")
            return {
                "next_action": "character",
                "game_ended": False,
                "events": [{"type": "message", "message": dict(manager.state["messages"][-1])}],
            }

        assert idx == 2
        assert current_next_action == "character"
        event_sink({"type": "message_start", "author": "Marco"})
        character_stream_sink("Salve")
        manager.add_message("Marco", "Salve, ciudadano")
        return {
            "next_action": "user_input",
            "game_ended": False,
            "events": [{"type": "message", "message": dict(manager.state["messages"][-1])}],
        }

    monkeypatch.setattr(engine_module, "run_one_step", fake_run_one_step)

    events = list(engine.execute_turn_stream(game_id, "Hola"))

    assert [event["type"] for event in events] == [
        "observer_thinking",
        "message_start",
        "message_delta",
        "observer_thinking",
        "message",
        "message_start",
        "message_delta",
        "message",
    ]
    assert events[1]["author"] == "Livia"
    assert events[4]["message"]["author"] == "Livia"
    assert events[5]["author"] == "Marco"
    assert events[7]["message"]["author"] == "Marco"
