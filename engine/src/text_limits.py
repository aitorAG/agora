"""Validaciones y truncados de texto para input/output del juego."""

from __future__ import annotations

import re
from typing import Any

USER_MESSAGE_MAX_SENTENCES = 5
USER_MESSAGE_MAX_WORDS = 120
USER_MESSAGE_MAX_CHARS = 600

CUSTOM_ERA_MAX_SENTENCES = 2
CUSTOM_ERA_MAX_WORDS = 30
CUSTOM_ERA_MAX_CHARS = 160

CUSTOM_TOPIC_MAX_SENTENCES = 2
CUSTOM_TOPIC_MAX_WORDS = 30
CUSTOM_TOPIC_MAX_CHARS = 160

CUSTOM_STYLE_MAX_SENTENCES = 1
CUSTOM_STYLE_MAX_WORDS = 18
CUSTOM_STYLE_MAX_CHARS = 100

CUSTOM_TOTAL_MAX_SENTENCES = 5
CUSTOM_TOTAL_MAX_WORDS = 70
CUSTOM_TOTAL_MAX_CHARS = 400

AGENT_OUTPUT_MAX_SENTENCES = 3
AGENT_OUTPUT_MAX_CHARS = 280

_SENTENCE_SPLIT_RE = re.compile(r"[.!?…]+")
_WORD_RE = re.compile(r"\S+")


def normalize_text(value: Any) -> str:
    return str(value or "").strip()


def count_words(text: str) -> int:
    return len(_WORD_RE.findall(normalize_text(text)))


def count_sentences(text: str) -> int:
    cleaned = normalize_text(text)
    if not cleaned:
        return 0
    parts = [part.strip() for part in _SENTENCE_SPLIT_RE.split(cleaned) if part.strip()]
    return len(parts) if parts else 1


def _validate_text(
    text: str,
    *,
    label: str,
    max_sentences: int,
    max_words: int,
    max_chars: int,
) -> str:
    cleaned = normalize_text(text)
    if not cleaned:
        return ""
    if len(cleaned) > max_chars:
        raise ValueError(f"{label} no puede superar {max_chars} caracteres.")
    if count_words(cleaned) > max_words:
        raise ValueError(f"{label} no puede superar {max_words} palabras.")
    if count_sentences(cleaned) > max_sentences:
        raise ValueError(f"{label} no puede superar {max_sentences} frases.")
    return cleaned


def validate_user_message(text: str) -> str:
    return _validate_text(
        text,
        label="El mensaje del usuario",
        max_sentences=USER_MESSAGE_MAX_SENTENCES,
        max_words=USER_MESSAGE_MAX_WORDS,
        max_chars=USER_MESSAGE_MAX_CHARS,
    )


def compose_custom_theme(*, era: str = "", topic: str = "", style: str = "") -> str:
    parts: list[str] = []
    if era:
        parts.append(f"Época/contexto: {era}")
    if topic:
        parts.append(f"Tema: {topic}")
    if style:
        parts.append(f"Estilo: {style}")
    return " | ".join(parts)


def validate_custom_seed(
    *,
    theme: str | None = None,
    era: str | None = None,
    topic: str | None = None,
    style: str | None = None,
) -> dict[str, str]:
    clean_theme = normalize_text(theme)
    clean_era = _validate_text(
        normalize_text(era),
        label="El campo Época/contexto",
        max_sentences=CUSTOM_ERA_MAX_SENTENCES,
        max_words=CUSTOM_ERA_MAX_WORDS,
        max_chars=CUSTOM_ERA_MAX_CHARS,
    )
    clean_topic = _validate_text(
        normalize_text(topic),
        label="El campo Tema",
        max_sentences=CUSTOM_TOPIC_MAX_SENTENCES,
        max_words=CUSTOM_TOPIC_MAX_WORDS,
        max_chars=CUSTOM_TOPIC_MAX_CHARS,
    )
    clean_style = _validate_text(
        normalize_text(style),
        label="El campo Estilo",
        max_sentences=CUSTOM_STYLE_MAX_SENTENCES,
        max_words=CUSTOM_STYLE_MAX_WORDS,
        max_chars=CUSTOM_STYLE_MAX_CHARS,
    )
    has_structured = bool(clean_era or clean_topic or clean_style)
    if clean_theme and has_structured:
        raise ValueError("Usa theme o los campos custom estructurados, pero no ambos a la vez.")

    aggregate_source = clean_theme or " ".join(
        part for part in (clean_era, clean_topic, clean_style) if part
    )
    aggregate = _validate_text(
        aggregate_source,
        label="La descripción custom",
        max_sentences=CUSTOM_TOTAL_MAX_SENTENCES,
        max_words=CUSTOM_TOTAL_MAX_WORDS,
        max_chars=CUSTOM_TOTAL_MAX_CHARS,
    )
    effective_theme = clean_theme
    if not effective_theme and has_structured:
        effective_theme = compose_custom_theme(
            era=clean_era,
            topic=clean_topic,
            style=clean_style,
        )

    return {
        "theme": aggregate if clean_theme else effective_theme,
        "era": clean_era,
        "topic": clean_topic,
        "style": clean_style,
    }


def truncate_agent_output(
    text: str,
    *,
    max_sentences: int = AGENT_OUTPUT_MAX_SENTENCES,
    max_chars: int = AGENT_OUTPUT_MAX_CHARS,
) -> str:
    cleaned = normalize_text(text)
    if not cleaned:
        return ""

    sentence_count = 0
    end_index = len(cleaned)
    for idx, char in enumerate(cleaned):
        if char in ".!?…":
            sentence_count += 1
            if sentence_count >= max_sentences:
                end_index = idx + 1
                break

    limited = cleaned[:end_index].strip()
    if len(limited) <= max_chars:
        return limited

    clipped = limited[:max_chars].rstrip()
    last_space = clipped.rfind(" ")
    if last_space >= 40:
        clipped = clipped[:last_space].rstrip()
    return clipped.rstrip(".!?… ")
