"""Tests de emisión de eventos outbox desde el engine."""

import uuid
from datetime import datetime, timezone

from src.core.engine import GameEngine, GameSession
from src.manager import ConversationManager
from src.persistence.provider import PersistenceProvider


def _utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


class _InMemoryProvider(PersistenceProvider):
    def __init__(self):
        self.games = {}
        self.messages = {}
        self.outbox_events = []

    def create_game(
        self,
        title,
        config_json,
        username=None,
        game_mode="custom",
        standard_template_id=None,
        template_version=None,
    ):
        game_id = str(uuid.uuid4())
        self.games[game_id] = {
            "id": game_id,
            "title": title,
            "status": "active",
            "user": username or "usuario",
            "config_json": dict(config_json),
            "state_json": {"turn": 0, "metadata": {}, "next_action": "character"},
            "created_at": _utc_now_iso(),
            "updated_at": _utc_now_iso(),
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
        return dict(self.games[game_id])

    def get_game_messages(self, game_id):
        return list(self.messages[game_id])

    def list_games_for_user(self, username):
        return [game for game in self.games.values() if game.get("user") == username]

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


def test_persist_session_state_enqueues_turn_reached_user_input():
    provider = _InMemoryProvider()
    game_id = provider.create_game("Partida", {"actors": [{"name": "A"}, {"name": "B"}]})
    engine = GameEngine(persistence_provider=provider)
    manager = ConversationManager()
    manager.add_message("Usuario", "hola")
    manager.add_message("A", "respuesta")
    session = GameSession(
        manager=manager,
        character_agents={"A": object(), "B": object()},
        observer_agent=object(),
        setup={"actors": [{"name": "A"}, {"name": "B"}]},
        max_turns=10,
        next_action="user_input",
    )

    engine._persist_session_state(game_id, session)

    assert len(provider.outbox_events) == 1
    event = provider.outbox_events[0]
    assert event["event_type"] == "turn_reached_user_input"
    assert event["payload_json"]["window_size"] == 6
    assert event["payload_json"]["message_count"] == 2
