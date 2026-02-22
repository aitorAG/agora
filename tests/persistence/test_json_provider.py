"""Tests de JsonPersistenceProvider."""

from src.persistence.json_provider import JsonPersistenceProvider


def test_json_provider_create_game_and_get_game(tmp_path):
    provider = JsonPersistenceProvider(base_path=tmp_path)
    config = {
        "ambientacion": "A",
        "contexto_problema": "B",
        "relevancia_jugador": "C",
        "player_mission": "D",
        "narrativa_inicial": "E",
        "actors": [{"name": "Alice"}],
    }

    game_id = provider.create_game("Titulo", config)
    game = provider.get_game(game_id)

    assert game["id"] == game_id
    assert game["title"] == "Titulo"
    assert game["config_json"]["player_mission"] == "D"
    assert game["state_json"]["turn"] == 0


def test_json_provider_append_messages_and_sort(tmp_path):
    provider = JsonPersistenceProvider(base_path=tmp_path)
    game_id = provider.create_game("Titulo", {"actors": []})

    provider.append_message(game_id, turn_number=1, role="actor_a", content="m2")
    provider.append_message(game_id, turn_number=0, role="player", content="m1")
    msgs = provider.get_game_messages(game_id)

    assert len(msgs) == 2
    assert msgs[0]["turn_number"] == 0
    assert msgs[1]["turn_number"] == 1


def test_json_provider_save_game_state_and_list_games(tmp_path):
    provider = JsonPersistenceProvider(base_path=tmp_path)
    game_id = provider.create_game("Partida", {"actors": []})
    provider.save_game_state(game_id, {"turn": 3, "messages": [], "metadata": {"k": "v"}})

    game = provider.get_game(game_id)
    assert game["state_json"]["turn"] == 3
    listed = provider.list_games_for_user("usuario")
    assert any(x["id"] == game_id for x in listed)
