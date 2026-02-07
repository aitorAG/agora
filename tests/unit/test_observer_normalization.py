"""Tests unitarios de la normalización who_should_respond del Observer."""

import pytest
from src.agents.observer import normalize_who_should_respond


def test_normalize_user_returns_user():
    """decision {who_should_respond: 'user'} -> 'user'."""
    assert normalize_who_should_respond({"who_should_respond": "user"}, ["Alice"]) == "user"


def test_normalize_none_returns_none():
    """'none' / 'None' -> 'none'."""
    assert normalize_who_should_respond({"who_should_respond": "none"}, ["Alice"]) == "none"
    assert normalize_who_should_respond({"who_should_respond": "None"}, []) == "none"


def test_normalize_one_actor_name_returns_character():
    """actor_names=['Alice'], who='Alice' -> 'character'."""
    assert normalize_who_should_respond({"who_should_respond": "Alice"}, ["Alice"]) == "character"


def test_normalize_three_actors_matching_name_returns_concrete_name():
    """actor_names=['A','B','C'], who='B' -> 'B'."""
    assert normalize_who_should_respond({"who_should_respond": "B"}, ["A", "B", "C"]) == "B"
    assert normalize_who_should_respond({"who_should_respond": "A"}, ["A", "B", "C"]) == "A"


def test_normalize_three_actors_unknown_name_returns_none():
    """who='Otro' no en lista -> 'none'."""
    assert normalize_who_should_respond({"who_should_respond": "Otro"}, ["Alice", "Bob"]) == "none"


def test_normalize_case_insensitive_match():
    """'alice' con actor_names=['Alice'] -> 'character' (1 actor)."""
    assert normalize_who_should_respond({"who_should_respond": "alice"}, ["Alice"]) == "character"
    assert normalize_who_should_respond({"who_should_respond": "ALICE"}, ["Alice"]) == "character"
    # Con 3 actores debe devolver el nombre concreto (conservando el de la lista)
    assert normalize_who_should_respond({"who_should_respond": "bob"}, ["Alice", "Bob", "Claire"]) == "Bob"
