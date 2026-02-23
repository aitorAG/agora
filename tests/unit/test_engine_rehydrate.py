"""Tests de rehidratación de sesiones en GameEngine."""

import src.core.engine as engine_module
from src.core.engine import GameEngine
from src.persistence.json_provider import JsonPersistenceProvider


def _build_config():
    return {
        "ambientacion": "Roma",
        "contexto_problema": "Intriga política",
        "relevancia_jugador": "Eres clave",
        "player_mission": "Descubrir al culpable",
        "narrativa_inicial": "Comienza la historia",
        "actors": [
            {
                "name": "Livia",
                "personality": "Calculadora",
                "mission": "Ocultar secretos",
                "background": "Senadora",
            }
        ],
    }


def test_engine_rehydrate_restores_state_and_avoids_duplicates(tmp_path, monkeypatch):
    monkeypatch.setattr(engine_module, "create_character_agent", lambda **_: object())
    monkeypatch.setattr(engine_module, "create_observer_agent", lambda **_: object())

    provider = JsonPersistenceProvider(base_path=tmp_path)
    game_id = provider.create_game("Partida", _build_config())
    provider.append_message(
        game_id,
        turn_number=1,
        role="player",
        content="hola",
        metadata_json={"author": "Usuario", "timestamp": "2026-02-18T10:00:00+00:00"},
    )
    provider.save_game_state(
        game_id,
        {
            "turn": 1,
            "messages": [
                {
                    "author": "Usuario",
                    "content": "hola",
                    "timestamp": "2026-02-18T10:00:00+00:00",
                    "turn": 1,
                    "displayed": False,
                }
            ],
            "metadata": {"continuation_decision": {"who_should_respond": "user"}},
            "next_action": "user_input",
            "max_turns": 12,
            "max_messages_before_user": 4,
        },
    )

    engine = GameEngine(persistence_provider=provider)
    resumed = engine.resume_game(game_id)
    assert resumed["loaded_from_memory"] is False

    status = engine.get_status(game_id)
    assert status["turn_current"] == 1
    assert status["turn_max"] == 12
    assert status["player_can_write"] is True
    assert len(status["messages"]) == 1
    assert status["messages"][0]["author"] == "Usuario"

    resumed_again = engine.resume_game(game_id)
    assert resumed_again["loaded_from_memory"] is True

    # Verifica que no se duplica al persistir de nuevo sin mensajes nuevos.
    session = engine._registry[game_id]
    engine._persist_session_state(game_id, session)
    persisted = provider.get_game_messages(game_id)
    assert len(persisted) == 1


def test_engine_resume_invalid_game_state_raises_value_error(tmp_path, monkeypatch):
    monkeypatch.setattr(engine_module, "create_character_agent", lambda **_: object())
    monkeypatch.setattr(engine_module, "create_observer_agent", lambda **_: object())

    provider = JsonPersistenceProvider(base_path=tmp_path)
    game_id = provider.create_game("Partida inválida", {"actors": []})
    engine = GameEngine(persistence_provider=provider)

    try:
        engine.resume_game(game_id)
        assert False, "Debe lanzar ValueError cuando no hay actores válidos"
    except ValueError:
        pass
