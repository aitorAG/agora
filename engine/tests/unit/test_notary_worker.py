"""Tests del worker del notario."""

from src.notary import HeuristicNotaryProcessor, NotaryWorker


class _FakePersistence:
    def __init__(self):
        self.entry_calls = []
        self.snapshot_calls = []

    def get_game(self, game_id):
        return {
            "id": game_id,
            "config_json": {"player_mission": "Saludar a Antonio"},
        }

    def get_recent_game_messages(self, game_id, limit):
        _ = (game_id, limit)
        return [
            {"author": "Antonio", "content": "Hola", "turn_number": 3, "metadata_json": {}},
            {"author": "Usuario", "content": "Buenas", "turn_number": 3, "metadata_json": {}},
        ]

    def create_notary_entry(
        self,
        game_id,
        turn,
        based_on_message_count,
        window_size,
        summary_text,
        facts_json,
        mission_progress_json,
        open_threads_json,
    ):
        self.entry_calls.append(
            {
                "game_id": game_id,
                "turn": turn,
                "based_on_message_count": based_on_message_count,
                "window_size": window_size,
                "summary_text": summary_text,
                "facts_json": facts_json,
                "mission_progress_json": mission_progress_json,
                "open_threads_json": open_threads_json,
            }
        )
        return "entry-1"

    def upsert_scene_snapshot(
        self,
        game_id,
        source_notary_entry_id,
        version_turn,
        facts_json,
        mission_progress_json,
        open_threads_json,
        summary_text,
    ):
        self.snapshot_calls.append(
            {
                "game_id": game_id,
                "source_notary_entry_id": source_notary_entry_id,
                "version_turn": version_turn,
                "facts_json": facts_json,
                "mission_progress_json": mission_progress_json,
                "open_threads_json": open_threads_json,
                "summary_text": summary_text,
            }
        )


class _FakeQueue:
    def __init__(self):
        self.acked = []

    def ensure_group(self, stream_name, group_name):
        _ = (stream_name, group_name)

    def read_group(self, stream_name, group_name, consumer_name, count=10, block_ms=5000):
        _ = (stream_name, group_name, consumer_name, count, block_ms)
        return [
            {
                "message_id": "redis-1",
                "event_type": "turn_reached_user_input",
                "aggregate_id": "game-1",
                "payload_json": {
                    "game_id": "game-1",
                    "turn": 3,
                    "window_size": 4,
                    "message_count": 12,
                },
            }
        ]

    def ack(self, stream_name, group_name, message_id):
        self.acked.append((stream_name, group_name, message_id))


def test_notary_worker_persists_entry_and_snapshot():
    persistence = _FakePersistence()
    queue = _FakeQueue()
    worker = NotaryWorker(
        persistence=persistence,
        queue_client=queue,
        processor=HeuristicNotaryProcessor(),
        stream_name="agora.domain_events",
        group_name="notary-workers",
        consumer_name="notary-test",
    )

    processed = worker.run_once(count=1, block_ms=1)

    assert processed == 1
    assert len(persistence.entry_calls) == 1
    assert len(persistence.snapshot_calls) == 1
    assert queue.acked == [("agora.domain_events", "notary-workers", "redis-1")]
