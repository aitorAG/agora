"""Tests del procesador LLM del notario."""

import src.notary.processor as processor_module
from src.notary import HeuristicNotaryProcessor, LLMNotaryProcessor


def test_llm_notary_processor_normalizes_json_response(monkeypatch):
    response = """```json
    {
      "summary_text": "Antonio sigue esperando un saludo.",
      "facts_json": [
        {
          "kind": "mission_signal",
          "subject": "Usuario",
          "object": "Antonio",
          "summary": "El jugador todavía no ha saludado a Antonio.",
          "confidence": 0.97
        },
        {
          "kind": "emotion_signal",
          "subject": "Antonio",
          "object": "escena",
          "summary": "Antonio muestra molestia.",
          "confidence": 2.3
        }
      ],
      "mission_progress_json": {
        "status": "blocked",
        "reason": "El objetivo sigue pendiente."
      },
      "open_threads_json": [
        "Antonio sigue esperando un saludo"
      ]
    }
    ```"""
    monkeypatch.setattr(processor_module, "send_message", lambda *args, **kwargs: response)
    processor = LLMNotaryProcessor()

    result = processor.process(
        game_id="game-1",
        turn=3,
        recent_messages=[
            {"turn": 3, "author": "Antonio", "content": "No me vais a saludar?"},
            {"turn": 3, "author": "Usuario", "content": "Todavía no."},
        ],
        player_mission="Saludar a Antonio",
    )

    assert result["summary_text"] == "Antonio sigue esperando un saludo."
    assert result["mission_progress_json"]["status"] == "blocked"
    assert result["facts_json"][0]["kind"] == "mission_signal"
    assert result["facts_json"][1]["confidence"] == 1.0


def test_llm_notary_processor_falls_back_when_json_is_invalid(monkeypatch):
    monkeypatch.setattr(processor_module, "send_message", lambda *args, **kwargs: "no es json")
    processor = LLMNotaryProcessor(fallback_processor=HeuristicNotaryProcessor())

    result = processor.process(
        game_id="game-2",
        turn=5,
        recent_messages=[
            {"turn": 5, "author": "Usuario", "content": "hola"},
        ],
        player_mission="Investigar",
    )

    assert result["summary_text"].startswith("Turno 5.")
    assert result["mission_progress_json"]["status"] in {"in_progress", "unknown"}
    assert result["facts_json"]
