"""Fallbacks para misiones publicas del setup."""

from __future__ import annotations


def fallback_player_public_mission(
    *,
    relevancia_jugador: str | None = None,
    contexto_problema: str | None = None,
) -> str:
    relevancia = str(relevancia_jugador or "").strip()
    if relevancia:
        return relevancia

    contexto = str(contexto_problema or "").strip()
    if contexto:
        return (
            "Tu punto de partida es entrar en este conflicto con margen real "
            "para influir en como se resuelve."
        )

    return (
        "Tu punto de partida es intervenir en la escena y orientar como "
        "evoluciona el conflicto."
    )


def fallback_actor_public_mission(
    *,
    personality: str | None = None,
    presencia_escena: str | None = None,
) -> str:
    personalidad = str(personality or "").strip()
    if personalidad:
        return (
            "Su actitud visible ante el conflicto refleja este talante: "
            f"{personalidad}"
        )

    presencia = str(presencia_escena or "").strip()
    if presencia:
        return f"Su punto de partida en la escena es este: {presencia}"

    return (
        "Tiene una postura visible ante el conflicto y tratara de influir en "
        "como evoluciona."
    )
