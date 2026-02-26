"""Tests de rutas rápidas de latencia del ObserverAgent."""

from src.agents.observer import ObserverAgent


def test_evaluate_continuation_fast_path_non_user(monkeypatch):
    agent = ObserverAgent(actor_names=["Alice"], player_mission="x")

    def _boom(*_args, **_kwargs):
        raise AssertionError("send_message no debería llamarse en fast-path")

    monkeypatch.setattr("src.agents.observer.send_message", _boom)
    monkeypatch.delenv("OBSERVER_ENABLE_NON_USER_CONTINUATION", raising=False)

    state = {
        "messages": [{"author": "Alice", "content": "Hola", "timestamp": None, "turn": 0}],
        "turn": 0,
        "metadata": {},
    }
    decision = agent.evaluate_continuation(state)
    assert decision["needs_response"] is False
    assert decision["who_should_respond"] == "none"


def test_process_user_message_combines_continuation_and_mission(monkeypatch):
    agent = ObserverAgent(actor_names=["Alice"], player_mission="x")
    monkeypatch.setenv("OBSERVER_PARALLEL_EVAL", "false")
    monkeypatch.setattr(
        agent,
        "evaluate_continuation",
        lambda _state: {"needs_response": True, "who_should_respond": "Alice", "reason": "ok"},
    )
    monkeypatch.setattr(
        agent,
        "evaluate_missions",
        lambda _state: {"player_mission_achieved": False, "reasoning": "pendiente"},
    )

    state = {
        "messages": [{"author": "Usuario", "content": "¿Qué pasa?", "timestamp": None, "turn": 1}],
        "turn": 1,
        "metadata": {},
    }
    out = agent.process(state)
    assert out["continuation_decision"]["who_should_respond"] == "Alice"
    assert out["mission_evaluation"]["player_mission_achieved"] is False
    assert out["game_ended"] is False
