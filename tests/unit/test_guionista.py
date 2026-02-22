"""Tests unitarios del Guionista (_default_setup y generate_setup con/sin streaming)."""

import pytest
from unittest.mock import patch, MagicMock

from src.agents.guionista import _default_setup, GuionistaAgent


REQUIRED_KEYS = {
    "titulo",
    "descripcion_breve",
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


# JSON mínimo válido para generate_setup (num_actors=2)
_MINIMAL_SETUP_JSON = (
    '{"titulo":"Ecos de Roma Rota","descripcion_breve":"Intrigas en la ciudad eterna.\\nDescubre al asesino del césar.",'
    '"ambientacion":"A","contexto_problema":"B","relevancia_jugador":"C",'
    '"player_mission":"D","narrativa_inicial":"E","actors":['
    '{"name":"X","personality":"P","mission":"M","background":"B","presencia_escena":"S"},'
    '{"name":"Y","personality":"P2","mission":"M2","background":"B2","presencia_escena":"S2"}'
    "]}"
)


def test_guionista_generate_setup_stream_false_returns_setup():
    """Con stream=False, generate_setup devuelve setup con claves requeridas y actors correctos."""
    agent = GuionistaAgent(name="Guionista", model="deepseek-chat")
    with patch("src.agents.guionista.send_message", return_value=_MINIMAL_SETUP_JSON):
        setup = agent.generate_setup(theme=None, num_actors=2, stream=False)
    for key in REQUIRED_KEYS:
        assert key in setup, f"Falta clave: {key}"
    assert len(setup["actors"]) == 2
    assert setup["actors"][0]["name"] == "X"
    assert setup["actors"][1]["name"] == "Y"
    assert isinstance(setup["titulo"], str) and setup["titulo"].strip()
    assert len(setup["titulo"].split()) <= 6
    assert isinstance(setup["descripcion_breve"], str) and setup["descripcion_breve"].strip()


def test_guionista_generate_setup_stream_true_returns_same_setup_and_writes_stdout():
    """Con stream=True, generate_setup devuelve el mismo setup y escribe en stdout."""
    agent = GuionistaAgent(name="Guionista", model="deepseek-chat")
    chunks = [_MINIMAL_SETUP_JSON]

    with patch("src.agents.guionista.send_message", return_value=iter(chunks)):
        with patch("src.agents.guionista.sys.stdout") as mock_stdout:
            mock_stdout.write = MagicMock()
            mock_stdout.flush = MagicMock()
            setup = agent.generate_setup(theme=None, num_actors=2, stream=True)

    for key in REQUIRED_KEYS:
        assert key in setup, f"Falta clave: {key}"
    assert len(setup["actors"]) == 2
    assert setup["actors"][0]["name"] == "X"
    assert setup["actors"][1]["name"] == "Y"
    assert isinstance(setup["titulo"], str) and setup["titulo"].strip()
    assert isinstance(setup["descripcion_breve"], str) and setup["descripcion_breve"].strip()
    assert mock_stdout.write.called
    assert mock_stdout.flush.called
