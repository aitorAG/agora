"""Tests unitarios de la decisión de cierre (game_ended) del Observer."""

from unittest.mock import patch

from src.agents.observer import ObserverAgent


def test_compute_game_ended_false_when_no_mission_achieved():
    """Si ninguna misión lograda -> game_ended False."""
    agent = ObserverAgent(actor_names=["A"])
    ev = {"player_mission_achieved": False, "reasoning": "Nada."}
    ended, reason = agent._compute_game_ended(ev)
    assert ended is False
    assert reason == ""


def test_compute_game_ended_false_when_no_reasoning():
    """Si misión lograda pero reasoning vacío -> game_ended False (falta evidencia narrativa)."""
    agent = ObserverAgent(actor_names=["A"])
    ev = {"player_mission_achieved": True, "reasoning": ""}
    ended, reason = agent._compute_game_ended(ev)
    assert ended is False
    assert reason == ""


def test_compute_game_ended_true_player_achieved():
    """Jugador cumplió misión + reasoning -> game_ended True y reason con jugador."""
    agent = ObserverAgent(actor_names=["A"])
    ev = {"player_mission_achieved": True, "reasoning": "El usuario logró convencer."}
    ended, reason = agent._compute_game_ended(ev)
    assert ended is True
    assert "jugador" in reason.lower() or "El jugador" in reason
    assert "convencer" in reason or "logró" in reason


def test_compute_game_ended_false_when_only_actor_achieved_key_is_present():
    """Aunque venga actor_missions_achieved, no termina si player_mission_achieved es False."""
    agent = ObserverAgent(actor_names=["Alice", "Bob"])
    ev = {"player_mission_achieved": False, "actor_missions_achieved": {"Alice": True, "Bob": False}, "reasoning": "Alice lo logró."}
    ended, reason = agent._compute_game_ended(ev)
    assert ended is False
    assert reason == ""


def test_compute_game_ended_truncates_reason_to_three_sentences():
    agent = ObserverAgent(actor_names=["A"])
    ev = {
        "player_mission_achieved": True,
        "reasoning": "Primera frase. Segunda frase. Tercera frase. Cuarta frase.",
    }
    ended, reason = agent._compute_game_ended(ev)
    assert ended is True
    assert reason == "El jugador ha cumplido su misión. Primera frase. Segunda frase."


def test_evaluate_missions_uses_player_name_in_prompt_and_context():
    agent = ObserverAgent(actor_names=["A"], player_mission="Convencer al consejo.")
    state = {
        "messages": [
            {"author": "Usuario", "content": "Necesito vuestro apoyo.", "timestamp": None, "turn": 1},
        ],
        "turn": 1,
        "metadata": {"player_name": "alice"},
    }

    with patch(
        "src.agents.observer.send_message",
        return_value='{"player_mission_achieved": false, "reasoning": "Aún no."}',
    ) as mocked_send:
        agent.evaluate_missions(state)

    sent_messages = mocked_send.call_args.args[0]
    assert '[alice] Necesito vuestro apoyo.' in sent_messages[1]["content"]
    assert 'participante "alice"' in sent_messages[1]["content"]
    assert "jugador (alice)" in sent_messages[1]["content"]
