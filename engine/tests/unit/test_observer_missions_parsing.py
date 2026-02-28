"""Tests unitarios del parsing de evaluación de misiones del Observer."""

import json
from src.agents.observer import parse_mission_evaluation_response


def test_parse_mission_evaluation_valid_json():
    """JSON válido -> player_mission_achieved y reasoning."""
    content = json.dumps({
        "player_mission_achieved": True,
        "reasoning": "El jugador logró su objetivo.",
    })
    result = parse_mission_evaluation_response(content)
    assert result["player_mission_achieved"] is True
    assert "reasoning" in result
    assert result["reasoning"] == "El jugador logró su objetivo."


def test_parse_mission_evaluation_with_markdown_fence():
    """String con ```json ... ``` se parsea igual."""
    inner = '{"player_mission_achieved": false, "reasoning": "Nada aún."}'
    content = "```json\n" + inner + "\n```"
    result = parse_mission_evaluation_response(content)
    assert result["player_mission_achieved"] is False
