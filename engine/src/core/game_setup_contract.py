"""Contrato y validación del setup de partida."""

from __future__ import annotations

from typing import Any, Callable
from ..public_missions import (
    fallback_actor_public_mission,
    fallback_player_public_mission,
)

REQUIRED_SETUP_FIELDS = (
    "titulo",
    "descripcion_breve",
    "ambientacion",
    "contexto_problema",
    "relevancia_jugador",
    "player_mission",
    "narrativa_inicial",
    "actors",
)

REQUIRED_ACTOR_FIELDS = (
    "name",
    "personality",
    "mission",
    "background",
    "presencia_escena",
)


def validate_game_setup(
    setup: dict[str, Any],
    *,
    error_factory: Callable[[str], Exception] = ValueError,
    source_name: str = "setup",
) -> dict[str, Any]:
    """Valida y normaliza el setup esperado por el motor."""
    if not isinstance(setup, dict):
        raise error_factory(f"{source_name} must be an object")

    normalized: dict[str, Any] = dict(setup)

    missing = [k for k in REQUIRED_SETUP_FIELDS if k not in normalized]
    if missing:
        raise error_factory(f"Missing keys in {source_name}: {', '.join(missing)}")

    for field in REQUIRED_SETUP_FIELDS:
        if field == "actors":
            continue
        value = str(normalized.get(field, "")).strip()
        if not value:
            raise error_factory(f"{source_name} field '{field}' must be a non-empty string")
        normalized[field] = value

    player_public_mission = str(normalized.get("player_public_mission", "")).strip()
    if not player_public_mission:
        player_public_mission = fallback_player_public_mission(
            relevancia_jugador=normalized.get("relevancia_jugador"),
            contexto_problema=normalized.get("contexto_problema"),
        )
    normalized["player_public_mission"] = player_public_mission

    actors = normalized.get("actors")
    if not isinstance(actors, list) or not actors:
        raise error_factory(f"{source_name} actors must be a non-empty list")

    normalized_actors: list[dict[str, Any]] = []
    seen_actor_names: set[str] = set()
    for idx, actor in enumerate(actors, start=1):
        if not isinstance(actor, dict):
            raise error_factory(f"{source_name} actor #{idx} must be an object")
        actor_copy = dict(actor)
        for field in REQUIRED_ACTOR_FIELDS:
            value = str(actor_copy.get(field, "")).strip()
            if not value:
                raise error_factory(
                    f"{source_name} actor #{idx} field '{field}' must be a non-empty string"
                )
            actor_copy[field] = value
        public_mission = str(actor_copy.get("public_mission", "")).strip()
        if not public_mission:
            public_mission = fallback_actor_public_mission(
                personality=actor_copy.get("personality"),
                presencia_escena=actor_copy.get("presencia_escena"),
            )
        actor_copy["public_mission"] = public_mission

        actor_name_key = actor_copy["name"].lower()
        if actor_name_key in seen_actor_names:
            raise error_factory(f"{source_name} has duplicate actor name '{actor_copy['name']}'")
        seen_actor_names.add(actor_name_key)
        normalized_actors.append(actor_copy)

    normalized["actors"] = normalized_actors
    return normalized
