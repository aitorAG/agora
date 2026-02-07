"""Tests unitarios de ConversationManager."""

import pytest
from src.manager import ConversationManager


def test_initial_state_has_turn_zero_and_empty_messages(manager: ConversationManager):
    """Estado inicial turn=0, messages=[], metadata={}."""
    state = manager.state
    assert state["turn"] == 0
    assert state["messages"] == []
    assert state["metadata"] == {}


def test_add_message_appends_with_current_turn(manager: ConversationManager):
    """add_message('X', 'hola') deja el mensaje con turn igual al turn actual del estado."""
    manager.add_message("X", "hola")
    assert len(manager.state["messages"]) == 1
    assert manager.state["messages"][0]["author"] == "X"
    assert manager.state["messages"][0]["content"] == "hola"
    assert manager.state["messages"][0]["turn"] == 0
    assert manager.state["turn"] == 0


def test_increment_turn_increments_by_one(manager: ConversationManager):
    """Tras increment_turn(), state['turn'] sube 1."""
    assert manager.state["turn"] == 0
    manager.increment_turn()
    assert manager.state["turn"] == 1
    manager.increment_turn()
    assert manager.state["turn"] == 2


def test_add_message_then_increment_turn_message_has_old_turn(manager: ConversationManager):
    """Añadir mensaje en turn 0, luego increment_turn; el mensaje sigue con turn 0."""
    manager.add_message("Usuario", "hola")
    assert manager.state["messages"][0]["turn"] == 0
    manager.increment_turn()
    assert manager.state["turn"] == 1
    assert manager.state["messages"][0]["turn"] == 0


def test_update_metadata_and_get_metadata(manager: ConversationManager):
    """update_metadata(k,v); get_metadata(k) == v; get_metadata('missing', default) == default."""
    manager.update_metadata("key1", "value1")
    assert manager.get_metadata("key1") == "value1"
    manager.update_metadata("key2", {"nested": True})
    assert manager.get_metadata("key2") == {"nested": True}
    assert manager.get_metadata("missing") is None
    assert manager.get_metadata("missing", "default") == "default"


def test_get_visible_history_returns_copy(manager: ConversationManager):
    """get_visible_history() no es la misma lista que state['messages']."""
    manager.add_message("A", "msg1")
    visible = manager.get_visible_history()
    assert visible == manager.state["messages"]
    assert visible is not manager.state["messages"]
    visible.append({"author": "X", "content": "fake", "timestamp": None, "turn": 0})
    assert len(manager.state["messages"]) == 1
