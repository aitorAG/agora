"""Tests unitarios para la capa de observabilidad interna."""

from src.observability import runtime as rt


def test_start_generation_inherits_metadata_from_span():
    with rt.trace_interaction("g-1", "u-1", "i-1"):
        with rt.span_agent("observer", metadata={"agent_name": "Observer", "turn": 4}):
            generation = rt.start_generation(
                name="llm_call",
                model="deepseek-chat",
                metadata={"custom": "x"},
            )
    assert generation.metadata["agent_name"] == "Observer"
    assert generation.metadata["turn"] == "4"
    assert generation.metadata["custom"] == "x"


def test_end_generation_emits_event(monkeypatch):
    events = []
    monkeypatch.setattr(rt, "emit_telemetry_event", lambda payload: events.append(payload))
    with rt.trace_interaction("g-1", "u-1", "i-1"):
        with rt.span_agent(
            "observer",
            metadata={"agent_name": "Observer", "agent_type": "observer", "turn": 2},
        ):
            generation = rt.start_generation(
                name="llm_call",
                model="deepseek-chat",
                model_parameters={"provider": "deepseek", "stream": False},
            )
            rt.end_generation(
                generation,
                output="hola",
                usage_details={"input": 10, "output": 8, "total": 18},
                cost_details={"input": 0.1, "output": 0.2, "total": 0.3},
            )

    assert len(events) == 1
    event = events[0]
    assert event["game_id"] == "g-1"
    assert event["user_id"] == "u-1"
    assert event["agent_name"] == "Observer"
    assert event["agent_type"] == "observer"
    assert event["turn"] == 2
    assert event["usage_total_tokens"] == 18
    assert event["cost_total"] == 0.3


def test_record_user_login_emits_custom_event(monkeypatch):
    events = []
    monkeypatch.setattr(rt, "emit_telemetry_event", lambda payload: events.append(payload))

    rt.record_user_login("u-9", "alice")

    assert len(events) == 1
    event = events[0]
    assert event["event_type"] == "user_login"
    assert event["user_id"] == "u-9"
    assert event["username"] == "alice"
    assert event["status"] == "ok"


def test_trace_setup_preserves_interaction_id(monkeypatch):
    events = []
    monkeypatch.setattr(rt, "emit_telemetry_event", lambda payload: events.append(payload))

    with rt.trace_setup("u-setup", "setup-123"):
        rt.emit_event("link_interaction", {"game_id": "g-setup"})

    assert len(events) == 1
    event = events[0]
    assert event["event_type"] == "link_interaction"
    assert event["user_id"] == "u-setup"
    assert event["interaction_id"] == "setup-123"
    assert event["game_id"] == "g-setup"
