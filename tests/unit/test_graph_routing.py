"""Tests unitarios de la lógica de routing del grafo."""

import pytest
from src.graph import route_continuation, route_should_continue
from src.state import ConversationState


def test_route_continuation_needs_response_false_returns_continue():
    """Si needs_response=False -> 'continue'."""
    assert route_continuation({"needs_response": False, "who_should_respond": "user"}, ["Alice"]) == "continue"
    assert route_continuation({}, ["Alice"]) == "continue"


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


def test_route_continuation_who_unknown_returns_continue():
    """who_should_respond no en lista -> 'continue'."""
    assert route_continuation(
        {"needs_response": True, "who_should_respond": "Otro"},
        ["Alice", "Bob"],
    ) == "continue"


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
