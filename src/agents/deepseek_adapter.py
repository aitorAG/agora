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

from openai import OpenAI

from src.logging_config import get_logger

_BASE_URL = "https://api.deepseek.com"
_HIGH_LATENCY_THRESHOLD_S = 30.0
_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key or not api_key.strip():
            raise ValueError(
                "DEEPSEEK_API_KEY no está definida. Configúrala en el entorno o en un archivo .env."
            )
        _client = OpenAI(api_key=api_key.strip(), base_url=_BASE_URL)
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
    t0 = time.perf_counter()
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        stream=stream,
    )
    if not stream:
        if not response.choices or len(response.choices) == 0:
            raise ValueError("La respuesta de DeepSeek no tiene choices")
        content = response.choices[0].message.content
        if content is None:
            raise ValueError("La respuesta de DeepSeek no tiene contenido")
        elapsed = time.perf_counter() - t0
        logger.info("LLM response received (duration=%.2f s)", elapsed)
        if elapsed > _HIGH_LATENCY_THRESHOLD_S:
            logger.warning("High LLM latency: %.2f s", elapsed)
        return content

    # stream=True: devolver generador de chunks; no registrar "duration" aquí (sería engañoso)
    logger.info("LLM streaming started")

    def _stream() -> Iterator[str]:
        try:
            for chunk in response:
                if chunk.choices and len(chunk.choices) > 0 and chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content
        finally:
            elapsed = time.perf_counter() - t0
            logger.info("LLM streaming finished (duration=%.2f s)", elapsed)
            if elapsed > _HIGH_LATENCY_THRESHOLD_S:
                logger.warning("High LLM latency: %.2f s", elapsed)

    return _stream()
