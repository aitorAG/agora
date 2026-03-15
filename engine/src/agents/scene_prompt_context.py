"""Construccion del contexto publico de escena para prompts de actores."""

from __future__ import annotations

from typing import Any


def build_scene_participants_block(
    *,
    actor_name: str,
    player_name: str,
    player_public_mission: str | None = None,
    participants: list[dict[str, Any]] | None = None,
) -> str:
    clean_player_name = str(player_name or "").strip()
    clean_actor_name = str(actor_name or "").strip()
    scene_participants = participants if isinstance(participants, list) else []

    lines = ["", "", "Contexto publico de la escena:"]
    if clean_player_name:
        lines.append(f'- Jugador "{clean_player_name}":')
        public_start = str(player_public_mission or "").strip()
        if public_start:
            lines.append(f"  Punto de partida visible: {public_start}")
        else:
            lines.append("  Punto de partida visible: Aun no especificado.")

    if scene_participants:
        lines.append("")
        lines.append("Participantes visibles:")
    for raw_participant in scene_participants:
        participant = raw_participant if isinstance(raw_participant, dict) else {}
        name = str(participant.get("name", "")).strip()
        if not name:
            continue
        personality = str(participant.get("personality", "")).strip()
        public_mission = str(participant.get("public_mission", "")).strip()
        presence = str(participant.get("presencia_escena", "")).strip()
        header = f'Tu ({name})' if clean_actor_name and name == clean_actor_name else name
        lines.append(f"- {header}:")
        if personality:
            lines.append(f"  Personalidad visible: {personality}")
        if public_mission:
            lines.append(f"  Postura publica ante el conflicto: {public_mission}")
        if presence:
            lines.append(f"  Presencia en escena: {presence}")

    lines.extend(
        [
            "",
            "No conoces las misiones privadas ajenas. Solo conoces estas posturas visibles y lo ocurrido en la conversacion.",
        ]
    )
    return "\n".join(lines)
