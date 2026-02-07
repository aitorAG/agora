"""Tests unitarios del Guionista (_default_setup)."""

import pytest
from src.agents.guionista import _default_setup


REQUIRED_KEYS = {
    "ambientacion",
    "contexto_problema",
    "relevancia_jugador",
    "player_mission",
    "narrativa_inicial",
    "actors",
}

ACTOR_KEYS = {"name", "personality", "mission", "background", "presencia_escena"}


def test_default_setup_has_required_keys():
    """_default_setup(3) contiene ambientacion, contexto_problema, relevancia_jugador, player_mission, narrativa_inicial, actors."""
    setup = _default_setup(3)
    for key in REQUIRED_KEYS:
        assert key in setup, f"Falta clave obligatoria: {key}"


def test_default_setup_actors_count_matches_arg():
    """len(actors) == num_actors y cada uno tiene name, personality, mission, background, presencia_escena."""
    for num in (1, 3, 5):
        setup = _default_setup(num)
        actors = setup["actors"]
        assert len(actors) == num
        for a in actors:
            for key in ACTOR_KEYS:
                assert key in a, f"Actor sin clave: {key}"


def test_default_setup_narrativa_inicial_non_empty():
    """narrativa_inicial es string no vacío e incluye al menos un nombre de actor."""
    setup = _default_setup(3)
    narrativa = setup["narrativa_inicial"]
    assert isinstance(narrativa, str)
    assert len(narrativa.strip()) > 0
    # Debe incluir al menos el primer actor (Alice)
    assert "Alice" in narrativa or "Personaje" in narrativa
