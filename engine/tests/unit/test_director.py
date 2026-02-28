"""Tests unitarios de la lógica de routing del Director (antes grafo)."""

import pytest
from src.crew_roles.director import (
    route_continuation,
    route_should_continue,
    _messages_since_user,
)
from src.state import ConversationState


def test_route_continuation_needs_response_false_returns_user_input():
    """Si needs_response=False se da palabra al usuario por defecto -> 'user_input'."""
    assert route_continuation({"needs_response": False, "who_should_respond": "user"}, ["Alice"]) == "user_input"
    assert route_continuation({}, ["Alice"]) == "user_input"


def test_route_continuation_who_user_returns_user_input():
    """who_should_respond=='user' -> 'user_input'."""
    assert route_continuation(
        {"needs_response": True, "who_should_respond": "user"},
        ["Alice"],
    ) == "user_input"


def test_route_continuation_who_character_single_agent_returns_character():
    """who_should_respond=='character' y 1 nombre en lista -> 'character'."""
    assert route_continuation(
        {"needs_response": True, "who_should_respond": "character"},
        ["Alice"],
    ) == "character"


def test_route_continuation_who_concrete_name_in_list_returns_character():
    """who_should_respond=='Alice' y 'Alice' en character_agent_names -> 'character'."""
    assert route_continuation(
        {"needs_response": True, "who_should_respond": "Alice"},
        ["Alice", "Bob", "Claire"],
    ) == "character"
    assert route_continuation(
        {"needs_response": True, "who_should_respond": "Bob"},
        ["Alice", "Bob", "Claire"],
    ) == "character"


def test_route_continuation_who_unknown_returns_user_input():
    """who_should_respond no en lista -> se da palabra al usuario -> 'user_input'."""
    assert route_continuation(
        {"needs_response": True, "who_should_respond": "Otro"},
        ["Alice", "Bob"],
    ) == "user_input"


def test_route_should_continue_user_exit_returns_end():
    """metadata.user_exit True -> 'end'."""
    state: ConversationState = {
        "messages": [],
        "turn": 0,
        "metadata": {"user_exit": True},
    }
    assert route_should_continue(state, 10) == "end"


def test_route_should_continue_turn_ge_max_turns_returns_end():
    """turn >= max_turns -> 'end'."""
    state: ConversationState = {"messages": [], "turn": 10, "metadata": {}}
    assert route_should_continue(state, 10) == "end"
    state["turn"] = 11
    assert route_should_continue(state, 10) == "end"


def test_route_should_continue_turn_below_max_returns_continue():
    """turn < max_turns y no user_exit -> 'continue'."""
    state: ConversationState = {"messages": [], "turn": 0, "metadata": {}}
    assert route_should_continue(state, 10) == "continue"
    state["turn"] = 9
    assert route_should_continue(state, 10) == "continue"


def test_messages_since_user_empty_returns_zero():
    """Sin mensajes -> 0."""
    assert _messages_since_user([]) == 0


def test_messages_since_user_last_is_user_returns_zero():
    """Último mensaje es Usuario -> 0."""
    msgs = [
        {"author": "Alice", "content": "Hola", "timestamp": None, "turn": 0},
        {"author": "Usuario", "content": "Hola", "timestamp": None, "turn": 0},
    ]
    assert _messages_since_user(msgs) == 0


def test_messages_since_user_three_non_user_returns_three():
    """Tres mensajes seguidos sin Usuario al final -> 3."""
    msgs = [
        {"author": "Alice", "content": "A", "timestamp": None, "turn": 0},
        {"author": "Bob", "content": "B", "timestamp": None, "turn": 0},
        {"author": "Alice", "content": "C", "timestamp": None, "turn": 0},
    ]
    assert _messages_since_user(msgs) == 3


def test_messages_since_user_user_then_two_returns_two():
    """Usuario habló y luego dos personajes -> 2."""
    msgs = [
        {"author": "Usuario", "content": "Yo", "timestamp": None, "turn": 0},
        {"author": "Alice", "content": "A", "timestamp": None, "turn": 1},
        {"author": "Bob", "content": "B", "timestamp": None, "turn": 1},
    ]
    assert _messages_since_user(msgs) == 2
