"""Procesadores del notario para resumir el estado reciente de la escena."""

from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Any

from ..agents.deepseek_adapter import send_message

logger = logging.getLogger(__name__)

_VALID_FACT_KINDS = {
    "fact",
    "inference",
    "contradiction",
    "state_change",
    "threat",
    "alliance",
    "emotion_signal",
    "mission_signal",
}
_VALID_MISSION_STATUS = {"unknown", "blocked", "in_progress", "advanced", "achieved", "failed"}


def _strip_json_fence(content: str) -> str:
    content = (content or "").strip()
    if "```json" in content:
        return content.split("```json", 1)[1].split("```", 1)[0].strip()
    if "```" in content:
        return content.split("```", 1)[1].split("```", 1)[0].strip()
    return content


class NotaryProcessor(ABC):
    """Contrato de procesamiento del notario."""

    @abstractmethod
    def process(
        self,
        game_id: str,
        turn: int,
        recent_messages: list[dict[str, Any]],
        player_mission: str = "",
    ) -> dict[str, Any]:
        """Construye facts y snapshot a partir de la ventana reciente."""


class HeuristicNotaryProcessor(NotaryProcessor):
    """Implementación barata y determinista para fallback operativo."""

    def process(
        self,
        game_id: str,
        turn: int,
        recent_messages: list[dict[str, Any]],
        player_mission: str = "",
    ) -> dict[str, Any]:
        _ = game_id
        facts: list[dict[str, Any]] = []
        open_threads: list[str] = []
        player_mentioned = False
        normalized_messages = recent_messages[-4:]
        for msg in normalized_messages:
            author = str(msg.get("author") or "").strip() or "Desconocido"
            content = str(msg.get("content") or "").strip()
            if not content:
                continue
            facts.append(
                {
                    "kind": "fact",
                    "subject": author,
                    "object": "escena",
                    "summary": f"{author} dijo: {content}",
                    "confidence": 0.55,
                }
            )
            if author == "Usuario":
                player_mentioned = True
        if player_mission:
            status = "in_progress" if player_mentioned else "unknown"
            mission_reason = "La misión del jugador sigue abierta en la escena reciente."
        else:
            status = "unknown"
            mission_reason = "No hay misión del jugador disponible."
        if facts:
            open_threads.append("La conversación reciente sigue abierta.")
        summary_text = (
            f"Turno {turn}. "
            f"Se han registrado {len(facts)} hechos recientes relevantes para el estado de la escena."
        )
        return {
            "summary_text": summary_text,
            "facts_json": facts[:6],
            "mission_progress_json": {
                "status": status,
                "reason": mission_reason,
            },
            "open_threads_json": open_threads[:4],
        }


class LLMNotaryProcessor(NotaryProcessor):
    """Procesador del notario apoyado en LLM con salida JSON estricta."""

    def __init__(
        self,
        model: str = "deepseek-chat",
        fallback_processor: NotaryProcessor | None = None,
    ) -> None:
        self._model = model
        self._temperature = 0.1
        self._fallback = fallback_processor or HeuristicNotaryProcessor()
        try:
            self._max_output_tokens = int(os.getenv("NOTARY_MAX_OUTPUT_TOKENS", "420"))
        except ValueError:
            self._max_output_tokens = 420

    def _build_system_prompt(self) -> str:
        return """Eres el Notario de una escena narrativa conversacional.

Tu trabajo es registrar el estado reciente de la escena de forma objetiva, útil y compacta.

Debes analizar únicamente:
- la misión del jugador
- la ventana reciente de mensajes
- el turno actual

Tu objetivo es producir un resumen estructurado que sirva como memoria operativa del sistema.

Reglas:
- Prioriza hechos observables o inferencias prudentes.
- Si una conclusión no es segura, indícalo con menor confianza.
- No inventes eventos no apoyados por la conversación.
- No escribas prosa larga.
- No hables como personaje.
- No des consejos.
- No repitas literalmente toda la conversación.
- Si hay contradicciones entre mensajes, regístralas.
- Si la misión del jugador parece bloqueada, desviada o avanzada, indícalo.
- El resultado debe ser útil para que otros agentes entiendan qué está pasando en la escena.
- Limita facts_json a un máximo de 6 elementos.
- Limita open_threads_json a un máximo de 4 elementos.

Responde SOLO con JSON válido, sin markdown, sin comentarios, sin texto adicional.

Usa exactamente este esquema:
{
  "summary_text": "resumen corto de 1 a 3 frases",
  "facts_json": [
    {
      "kind": "fact|inference|contradiction|state_change|threat|alliance|emotion_signal|mission_signal",
      "subject": "quien o que elemento central",
      "object": "a quien o que afecta, si aplica",
      "summary": "frase corta y concreta",
      "confidence": 0.0
    }
  ],
  "mission_progress_json": {
    "status": "unknown|blocked|in_progress|advanced|achieved|failed",
    "reason": "explicacion corta"
  },
  "open_threads_json": [
    "lista de hilos abiertos relevantes"
  ]
}"""

    @staticmethod
    def _format_recent_messages(recent_messages: list[dict[str, Any]]) -> str:
        if not recent_messages:
            return "[sin mensajes recientes]"
        lines = []
        for msg in recent_messages:
            turn = int(msg.get("turn") or 0)
            author = str(msg.get("author") or "").strip() or "Desconocido"
            content = str(msg.get("content") or "").strip()
            lines.append(f"[Turno {turn}] {author}: {content}")
        return "\n".join(lines)

    def _build_user_prompt(
        self,
        turn: int,
        recent_messages: list[dict[str, Any]],
        player_mission: str,
    ) -> str:
        mission = player_mission.strip() or "No hay misión del jugador disponible."
        return f"""Analiza el estado reciente de esta partida.

Turno actual: {turn}

Misión del jugador:
{mission}

Ventana reciente de mensajes:
{self._format_recent_messages(recent_messages)}

Instrucciones específicas:
- Registra qué ha pasado recientemente en la escena.
- Detecta cambios de estado relevantes.
- Detecta contradicciones o tensiones.
- Evalúa si el jugador parece avanzar, estancarse o desviarse respecto a su misión.
- Si hay violencia, amenazas, confesiones, ocultación, evasivas o alianzas, regístralo.
- Si no hay suficiente información para afirmar algo, usa una inferencia prudente con menor confianza.
- El resumen debe ser compacto y reutilizable por el sistema.

Devuelve SOLO el JSON."""

    @staticmethod
    def _normalize_fact(raw_fact: Any) -> dict[str, Any] | None:
        if not isinstance(raw_fact, dict):
            return None
        kind = str(raw_fact.get("kind") or "fact").strip().lower()
        if kind not in _VALID_FACT_KINDS:
            kind = "fact"
        subject = str(raw_fact.get("subject") or "").strip() or "escena"
        object_value = str(raw_fact.get("object") or "").strip() or "escena"
        summary = str(raw_fact.get("summary") or "").strip()
        if not summary:
            return None
        try:
            confidence = float(raw_fact.get("confidence", 0.5))
        except (TypeError, ValueError):
            confidence = 0.5
        confidence = max(0.0, min(confidence, 1.0))
        return {
            "kind": kind,
            "subject": subject,
            "object": object_value,
            "summary": summary,
            "confidence": round(confidence, 3),
        }

    @staticmethod
    def _normalize_result(raw_result: dict[str, Any]) -> dict[str, Any]:
        summary_text = str(raw_result.get("summary_text") or "").strip()
        if not summary_text:
            summary_text = "Sin resumen disponible del estado reciente de la escena."
        normalized_facts = []
        for raw_fact in raw_result.get("facts_json", []):
            normalized = LLMNotaryProcessor._normalize_fact(raw_fact)
            if normalized is not None:
                normalized_facts.append(normalized)
        mission_raw = raw_result.get("mission_progress_json", {})
        if not isinstance(mission_raw, dict):
            mission_raw = {}
        status = str(mission_raw.get("status") or "unknown").strip().lower()
        if status not in _VALID_MISSION_STATUS:
            status = "unknown"
        reason = str(mission_raw.get("reason") or "").strip() or "Sin evaluación de misión."
        open_threads = [
            str(item).strip()
            for item in raw_result.get("open_threads_json", [])
            if str(item).strip()
        ]
        return {
            "summary_text": summary_text,
            "facts_json": normalized_facts[:6],
            "mission_progress_json": {
                "status": status,
                "reason": reason,
            },
            "open_threads_json": open_threads[:4],
        }

    def _fallback_result(
        self,
        game_id: str,
        turn: int,
        recent_messages: list[dict[str, Any]],
        player_mission: str,
    ) -> dict[str, Any]:
        return self._fallback.process(
            game_id=game_id,
            turn=turn,
            recent_messages=recent_messages,
            player_mission=player_mission,
        )

    def process(
        self,
        game_id: str,
        turn: int,
        recent_messages: list[dict[str, Any]],
        player_mission: str = "",
    ) -> dict[str, Any]:
        llm_messages = [
            {"role": "system", "content": self._build_system_prompt()},
            {
                "role": "user",
                "content": self._build_user_prompt(
                    turn=turn,
                    recent_messages=recent_messages,
                    player_mission=player_mission,
                ),
            },
        ]
        try:
            content = send_message(
                llm_messages,
                model=self._model,
                temperature=self._temperature,
                stream=False,
                max_tokens=self._max_output_tokens,
            )
            assert isinstance(content, str)
            parsed = json.loads(_strip_json_fence(content))
            if not isinstance(parsed, dict):
                raise ValueError("Respuesta del notario no es un objeto JSON")
            return self._normalize_result(parsed)
        except Exception as exc:
            logger.warning("Notary LLM failed for game_id=%s turn=%s: %s", game_id, turn, exc)
            return self._fallback_result(
                game_id=game_id,
                turn=turn,
                recent_messages=recent_messages,
                player_mission=player_mission,
            )
