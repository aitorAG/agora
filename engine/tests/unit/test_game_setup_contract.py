"""Tests del contrato de game setup."""

import pytest

from src.core.game_setup_contract import validate_game_setup


def _valid_setup():
    return {
        "titulo": "Caso",
        "descripcion_breve": "Descripcion",
        "ambientacion": "Roma",
        "contexto_problema": "Problema",
        "relevancia_jugador": "Relevancia",
        "player_mission": "Mision",
        "player_public_mission": "Punto de partida",
        "narrativa_inicial": "Inicio",
        "actors": [
            {
                "name": "Bruto",
                "personality": "Dubitativo",
                "mission": "Decidir",
                "public_mission": "Pide cautela ante el conflicto.",
                "background": "Senador",
                "presencia_escena": "Curia",
            }
        ],
    }


def test_validate_game_setup_accepts_valid_payload():
    setup = validate_game_setup(_valid_setup())
    assert setup["titulo"] == "Caso"
    assert len(setup["actors"]) == 1
    assert setup["player_public_mission"] == "Punto de partida"
    assert setup["actors"][0]["public_mission"] == "Pide cautela ante el conflicto."


def test_validate_game_setup_rejects_duplicate_actor_names():
    setup = _valid_setup()
    setup["actors"].append(dict(setup["actors"][0], name="  BRUTO "))
    with pytest.raises(ValueError, match="duplicate actor name"):
        validate_game_setup(setup)


def test_validate_game_setup_rejects_missing_top_level_field():
    setup = _valid_setup()
    setup.pop("narrativa_inicial")
    with pytest.raises(ValueError, match="narrativa_inicial"):
        validate_game_setup(setup)


def test_validate_game_setup_backfills_public_missions_for_legacy_payloads():
    setup = _valid_setup()
    setup.pop("player_public_mission")
    setup["actors"][0].pop("public_mission")

    normalized = validate_game_setup(setup)

    assert normalized["player_public_mission"]
    assert normalized["actors"][0]["public_mission"]
