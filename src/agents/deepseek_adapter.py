"""
Adaptador centralizado para llamadas a DeepSeek usando el cliente OpenAI.

Configuración:
- base_url: https://api.deepseek.com (API compatible con OpenAI).
- api_key: variable de entorno DEEPSEEK_API_KEY. Obligatoria; se lanza error si falta.

Uso básico (sin streaming):
    from src.agents.deepseek_adapter import send_message
    content = send_message([
        {"role": "system", "content": "Eres un asistente."},
        {"role": "user", "content": "Hola"},
    ])

Con streaming (para UI gráfica o Android):
    for chunk in send_message(messages, stream=True):
        print(chunk, end="")
"""

from __future__ import annotations

import os
import time
from typing import Iterator

from src.logging_config import get_logger
from src.observability import start_generation, end_generation

_BASE_URL = "https://api.deepseek.com"
_HIGH_LATENCY_THRESHOLD_S = 30.0
_client = None


def _to_int(value) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _extract_usage_details(usage_obj) -> dict[str, int]:
    if usage_obj is None:
        return {}
    prompt_tokens = _to_int(getattr(usage_obj, "prompt_tokens", None))
    completion_tokens = _to_int(getattr(usage_obj, "completion_tokens", None))
    total_tokens = _to_int(getattr(usage_obj, "total_tokens", None))
    if total_tokens == 0 and (prompt_tokens or completion_tokens):
        total_tokens = prompt_tokens + completion_tokens
    details = {
        "input": prompt_tokens,
        "output": completion_tokens,
        "total": total_tokens,
    }
    return details if any(v > 0 for v in details.values()) else {}


def _to_float_env(var_name: str, default: float = 0.0) -> float:
    raw = os.getenv(var_name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _calculate_cost_details(usage_details: dict[str, int]) -> dict[str, float]:
    if not usage_details:
        return {}
    input_rate = _to_float_env("DEEPSEEK_INPUT_COST_PER_1M_TOKENS", 0.0)
    output_rate = _to_float_env("DEEPSEEK_OUTPUT_COST_PER_1M_TOKENS", 0.0)
    if input_rate <= 0.0 and output_rate <= 0.0:
        return {}
    input_cost = (usage_details.get("input", 0) / 1_000_000.0) * input_rate
    output_cost = (usage_details.get("output", 0) / 1_000_000.0) * output_rate
    total_cost = input_cost + output_cost
    return {
        "input": round(input_cost, 12),
        "output": round(output_cost, 12),
        "total": round(total_cost, 12),
    }


def _get_client():
    """Devuelve cliente OpenAI para DeepSeek."""
    global _client
    if _client is not None:
        return _client
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key or not api_key.strip():
        raise ValueError(
            "DEEPSEEK_API_KEY no está definida. Configúrala en el entorno o en un archivo .env."
        )
    api_key = api_key.strip()
    from openai import OpenAI
    _client = OpenAI(api_key=api_key, base_url=_BASE_URL)
    return _client


def send_message(
    messages: list[dict[str, str]],
    model: str = "deepseek-chat",
    temperature: float = 0.7,
    stream: bool = False,
) -> str | Iterator[str]:
    """Envía mensajes a DeepSeek y devuelve la respuesta (texto o stream de chunks).

    Args:
        messages: Lista de dicts con "role" ("system"|"user"|"assistant") y "content" (str).
        model: Modelo a usar (p. ej. "deepseek-chat").
        temperature: Temperatura para la generación.
        stream: Si True, devuelve un iterador de strings (chunks). Si False, devuelve un único str.

    Returns:
        Si stream=False: contenido de texto de la respuesta (str).
        Si stream=True: iterador que produce strings (fragmentos de contenido).

    Raises:
        ValueError: Si DEEPSEEK_API_KEY no está configurada o la respuesta no tiene contenido.
    """
    client = _get_client()
    logger = get_logger("LLM")
    logger.info("LLM call started (model=%s)", model)
    generation = start_generation(
        name="llm_call",
        model=model,
        model_parameters={"temperature": temperature, "provider": "deepseek"},
        input_data=messages,
        metadata={"stream": str(bool(stream)).lower(), "model_family": "deepseek"},
    )
    t0 = time.perf_counter()
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            stream=stream,
        )
    except Exception as exc:
        end_generation(generation, level="ERROR", status_message=str(exc)[:500])
        raise
    if not stream:
        if not response.choices or len(response.choices) == 0:
            end_generation(generation, level="ERROR", status_message="La respuesta de DeepSeek no tiene choices")
            raise ValueError("La respuesta de DeepSeek no tiene choices")
        content = response.choices[0].message.content
        if content is None:
            end_generation(generation, level="ERROR", status_message="La respuesta de DeepSeek no tiene contenido")
            raise ValueError("La respuesta de DeepSeek no tiene contenido")
        usage_details = _extract_usage_details(getattr(response, "usage", None))
        cost_details = _calculate_cost_details(usage_details)
        end_generation(
            generation,
            output=content,
            usage_details=usage_details or None,
            cost_details=cost_details or None,
        )
        elapsed = time.perf_counter() - t0
        logger.info("LLM response received (duration=%.2f s)", elapsed)
        if elapsed > _HIGH_LATENCY_THRESHOLD_S:
            logger.warning("High LLM latency: %.2f s", elapsed)
        return content

    # stream=True: devolver generador de chunks; no registrar "duration" aquí (sería engañoso)
    logger.info("LLM streaming started")

    def _stream() -> Iterator[str]:
        full_content: list[str] = []
        usage_details: dict[str, int] = {}
        try:
            for chunk in response:
                chunk_usage = _extract_usage_details(getattr(chunk, "usage", None))
                if chunk_usage:
                    usage_details = chunk_usage
                if chunk.choices and len(chunk.choices) > 0 and chunk.choices[0].delta.content is not None:
                    piece = chunk.choices[0].delta.content
                    full_content.append(piece)
                    yield piece
        finally:
            cost_details = _calculate_cost_details(usage_details)
            end_generation(
                generation,
                output="".join(full_content) if full_content else None,
                usage_details=usage_details or None,
                cost_details=cost_details or None,
            )
            elapsed = time.perf_counter() - t0
            logger.info("LLM streaming finished (duration=%.2f s)", elapsed)
            if elapsed > _HIGH_LATENCY_THRESHOLD_S:
                logger.warning("High LLM latency: %.2f s", elapsed)

    return _stream()
