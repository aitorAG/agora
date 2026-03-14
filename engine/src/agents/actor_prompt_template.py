"""Template runtime del prompt interno de actores."""

from __future__ import annotations

from string import Formatter
from typing import Any

DEFAULT_ACTOR_PROMPT_TEMPLATE = """Eres {name}, un personaje en una conversación grupal.
Tu personalidad: {personality}

Estas presente en la conversacion y responderas de manera natural y coherente con tu personalidad adressing un personaje presente en la escena, siguiendo la conversacion de los personajes y queriendo avanzar en tu objetivo.
Mantén tus respuestas concisas y no superes nunca 3 frases.
Solo responde con el contenido del mensaje, sin prefijos ni explicaciones.{background_block}{mission_block}{extra_system_instruction_block}"""

REQUIRED_ACTOR_PROMPT_FIELDS = (
    {
        "key": "name",
        "label": "Nombre del actor",
        "description": "Identidad visible del personaje que habla.",
    },
    {
        "key": "personality",
        "label": "Personalidad",
        "description": "Descripción breve del carácter del actor.",
    },
    {
        "key": "background_block",
        "label": "Bloque de background",
        "description": "Texto opcional con el contexto del personaje o cadena vacía.",
    },
    {
        "key": "mission_block",
        "label": "Bloque de misión",
        "description": "Texto opcional con la misión secreta o cadena vacía.",
    },
    {
        "key": "extra_system_instruction_block",
        "label": "Bloque extra",
        "description": "Instrucción extra puntual o cadena vacía.",
    },
)

_FIELD_KEYS = {item["key"] for item in REQUIRED_ACTOR_PROMPT_FIELDS}


def default_actor_prompt_template() -> str:
    return DEFAULT_ACTOR_PROMPT_TEMPLATE


def actor_prompt_required_fields() -> list[dict[str, str]]:
    return [dict(item) for item in REQUIRED_ACTOR_PROMPT_FIELDS]


def validate_actor_prompt_template(template: str) -> dict[str, Any]:
    raw = str(template or "").strip()
    if not raw:
        return {
            "valid": False,
            "missing_fields": sorted(_FIELD_KEYS),
            "unknown_fields": [],
            "format_error": "El prompt no puede estar vacío.",
        }

    formatter = Formatter()
    found_fields: set[str] = set()
    try:
        for _, field_name, _, _ in formatter.parse(raw):
            if field_name:
                found_fields.add(field_name)
    except ValueError as exc:
        return {
            "valid": False,
            "missing_fields": [],
            "unknown_fields": [],
            "format_error": str(exc),
        }

    missing_fields = sorted(_FIELD_KEYS - found_fields)
    unknown_fields = sorted(found_fields - _FIELD_KEYS)
    return {
        "valid": not missing_fields and not unknown_fields,
        "missing_fields": missing_fields,
        "unknown_fields": unknown_fields,
        "format_error": None,
    }


def _background_block(background: str | None) -> str:
    value = str(background or "").strip()
    if not value:
        return ""
    return (
        "\n\n"
        f"Tu background (contexto de tu personaje): {value}\n"
        "Actúa de forma coherente con este contexto."
    )


def _mission_block(mission: str | None) -> str:
    value = str(mission or "").strip()
    if not value:
        return ""
    return (
        "\n\n"
        "Tienes una misión secreta que debes intentar cumplir durante la conversación. "
        "No la reveles explícitamente, aunque puedes dar pistas sobre ella.\n"
        f"Tu misión: {value}"
    )


def _extra_system_instruction_block(extra_system_instruction: str | None) -> str:
    value = str(extra_system_instruction or "").strip()
    if not value:
        return ""
    return f"\n\n{value}"


def render_actor_prompt(
    *,
    template: str | None,
    name: str,
    personality: str,
    background: str | None = None,
    mission: str | None = None,
    extra_system_instruction: str | None = None,
) -> str:
    prompt_template = str(template or DEFAULT_ACTOR_PROMPT_TEMPLATE)
    validation = validate_actor_prompt_template(prompt_template)
    if not validation["valid"]:
        prompt_template = DEFAULT_ACTOR_PROMPT_TEMPLATE
    return prompt_template.format(
        name=name,
        personality=personality,
        background_block=_background_block(background),
        mission_block=_mission_block(mission),
        extra_system_instruction_block=_extra_system_instruction_block(extra_system_instruction),
    )
