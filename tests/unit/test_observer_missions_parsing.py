"""Tests unitarios del parsing de evaluación de misiones del Observer."""

import json
import pytest
from src.agents.observer import parse_mission_evaluation_response


def test_parse_mission_evaluation_valid_json():
    """JSON válido -> player_mission_achieved, actor_missions_achieved con claves esperadas, reasoning."""
    content = json.dumps({
        "player_mission_achieved": True,
        "actor_missions_achieved": {"Alice": True, "Bob": False},
        "reasoning": "El jugador logró su objetivo.",
    })
    result = parse_mission_evaluation_response(content, ["Alice", "Bob"])
    assert result["player_mission_achieved"] is True
    assert result["actor_missions_achieved"] == {"Alice": True, "Bob": False}
    assert "reasoning" in result
    assert result["reasoning"] == "El jugador logró su objetivo."


def test_parse_mission_evaluation_with_markdown_fence():
    """String con ```json ... ``` se parsea igual."""
    inner = '{"player_mission_achieved": false, "actor_missions_achieved": {"A": false}, "reasoning": "Nada aún."}'
    content = "```json\n" + inner + "\n```"
    result = parse_mission_evaluation_response(content, ["A"])
    assert result["player_mission_achieved"] is False
    assert result["actor_missions_achieved"] == {"A": False}


def test_parse_mission_evaluation_missing_actor_key_defaults_false():
    """Si falta un actor en actor_missions_achieved -> False para ese actor."""
    content = json.dumps({
        "player_mission_achieved": False,
        "actor_missions_achieved": {"Alice": True},
        "reasoning": "Solo Alice.",
    })
    result = parse_mission_evaluation_response(content, ["Alice", "Bob"])
    assert result["actor_missions_achieved"]["Alice"] is True
    assert result["actor_missions_achieved"]["Bob"] is False
