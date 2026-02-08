"""Tests unitarios de la decisión de cierre (game_ended) del Observer."""

import pytest
from unittest.mock import MagicMock, patch


@patch("src.agents.observer.ChatDeepSeek", MagicMock())
def test_compute_game_ended_false_when_no_mission_achieved():
    """Si ninguna misión lograda -> game_ended False."""
    from src.agents.observer import ObserverAgent
    agent = ObserverAgent(actor_names=["A"], actor_missions={"A": "Hacer X"})
    ev = {"player_mission_achieved": False, "actor_missions_achieved": {"A": False}, "reasoning": "Nada."}
    ended, reason = agent._compute_game_ended(ev)
    assert ended is False
    assert reason == ""


@patch("src.agents.observer.ChatDeepSeek", MagicMock())
def test_compute_game_ended_false_when_no_reasoning():
    """Si misión lograda pero reasoning vacío -> game_ended False (falta evidencia narrativa)."""
    from src.agents.observer import ObserverAgent
    agent = ObserverAgent(actor_names=["A"], actor_missions={"A": "Hacer X"})
    ev = {"player_mission_achieved": True, "actor_missions_achieved": {"A": False}, "reasoning": ""}
    ended, reason = agent._compute_game_ended(ev)
    assert ended is False
    assert reason == ""


@patch("src.agents.observer.ChatDeepSeek", MagicMock())
def test_compute_game_ended_true_player_achieved():
    """Jugador cumplió misión + reasoning -> game_ended True y reason con jugador."""
    from src.agents.observer import ObserverAgent
    agent = ObserverAgent(actor_names=["A"], actor_missions={"A": "Hacer X"})
    ev = {"player_mission_achieved": True, "actor_missions_achieved": {"A": False}, "reasoning": "El usuario logró convencer."}
    ended, reason = agent._compute_game_ended(ev)
    assert ended is True
    assert "jugador" in reason.lower() or "El jugador" in reason
    assert "convencer" in reason or "logró" in reason


@patch("src.agents.observer.ChatDeepSeek", MagicMock())
def test_compute_game_ended_true_actor_achieved():
    """Actor cumplió misión + reasoning -> game_ended True y reason con nombre del actor."""
    from src.agents.observer import ObserverAgent
    agent = ObserverAgent(actor_names=["Alice", "Bob"], actor_missions={"Alice": "X", "Bob": "Y"})
    ev = {"player_mission_achieved": False, "actor_missions_achieved": {"Alice": True, "Bob": False}, "reasoning": "Alice lo logró."}
    ended, reason = agent._compute_game_ended(ev)
    assert ended is True
    assert "Alice" in reason
