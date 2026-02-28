"""Contrato básico de PersistenceProvider."""

import os

import pytest

from src.persistence.db_provider import DatabasePersistenceProvider


def assert_provider_contract(provider):
    game_id = provider.create_game(
        "Contrato",
        {
            "ambientacion": "A",
            "contexto_problema": "B",
            "relevancia_jugador": "C",
            "player_mission": "D",
            "narrativa_inicial": "E",
            "actors": [{"name": "Alice"}],
        },
    )
    provider.append_message(game_id, 0, "player", "hola", {"author": "Usuario"})
    provider.save_game_state(game_id, {"turn": 1, "messages": [], "metadata": {"x": 1}})
    game = provider.get_game(game_id)
    msgs = provider.get_game_messages(game_id)
    games = provider.list_games_for_user("usuario")

    assert game["id"] == game_id
    assert len(msgs) == 1
    assert any(g["id"] == game_id for g in games)


def test_contract_db_provider_if_available():
    dsn = os.getenv("DATABASE_URL_TEST") or os.getenv("DATABASE_URL")
    if not dsn:
        pytest.skip("No DATABASE_URL_TEST/DATABASE_URL disponible para contract test de DB.")
    try:
        provider = DatabasePersistenceProvider(dsn=dsn, run_migrations=True, ensure_user=True)
    except RuntimeError as exc:
        pytest.skip(f"Dependencia/DB no disponible: {exc}")
    assert_provider_contract(provider)
