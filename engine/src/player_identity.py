"""Utilities to resolve the visible identity of the player."""

from __future__ import annotations

from typing import Any

from .state import ConversationState

INTERNAL_PLAYER_AUTHOR = "Usuario"


def player_name_from_state(state: ConversationState | dict[str, Any] | None) -> str:
    """Return the visible player name for prompts and API responses."""
    if not isinstance(state, dict):
        return INTERNAL_PLAYER_AUTHOR
    metadata = state.get("metadata", {})
    if not isinstance(metadata, dict):
        return INTERNAL_PLAYER_AUTHOR
    raw = str(metadata.get("player_name") or "").strip()
    return raw or INTERNAL_PLAYER_AUTHOR


def display_author(
    author: str | None,
    *,
    player_name: str | None = None,
    state: ConversationState | dict[str, Any] | None = None,
) -> str:
    """Translate the internal player author to its visible name."""
    resolved_author = str(author or "")
    if resolved_author != INTERNAL_PLAYER_AUTHOR:
        return resolved_author
    if player_name is None:
        player_name = player_name_from_state(state)
    clean_name = str(player_name or "").strip()
    return clean_name or INTERNAL_PLAYER_AUTHOR
