"""Tests unitarios del dispatcher de outbox."""

from src.queueing.outbox_dispatcher import OutboxDispatcher


class _FakePersistence:
    def __init__(self, events):
        self._events = list(events)
        self.dispatched = []
        self.retried = []

    def claim_outbox_events(self, limit=50):
        _ = limit
        events = list(self._events)
        self._events.clear()
        return events

    def mark_outbox_event_dispatched(self, event_id):
        self.dispatched.append(event_id)

    def mark_outbox_event_retry(self, event_id, error_message=None):
        self.retried.append((event_id, error_message))


class _FakeQueue:
    def __init__(self, fail_ids=None):
        self.fail_ids = set(fail_ids or [])
        self.published = []

    def publish_event(self, stream_name, event):
        if event["id"] in self.fail_ids:
            raise RuntimeError("boom")
        self.published.append((stream_name, event))


def test_dispatcher_marks_success_and_retry():
    events = [
        {"id": "e1", "event_type": "turn_reached_user_input", "aggregate_type": "game", "aggregate_id": "g1", "payload_json": {}},
        {"id": "e2", "event_type": "turn_reached_user_input", "aggregate_type": "game", "aggregate_id": "g1", "payload_json": {}},
    ]
    persistence = _FakePersistence(events)
    queue = _FakeQueue(fail_ids={"e2"})
    dispatcher = OutboxDispatcher(persistence=persistence, queue_client=queue, stream_name="agora.domain_events")

    count = dispatcher.dispatch_once()

    assert count == 1
    assert persistence.dispatched == ["e1"]
    assert persistence.retried == [("e2", "boom")]
    assert len(queue.published) == 1
