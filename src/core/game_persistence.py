"""Persistencia de partidas en disco (games/custom y games/standard)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def resolve_games_base_path(base_path: Path | None = None) -> Path:
    """Resuelve la carpeta base de partidas."""
    if base_path is not None:
        return base_path
    configured = os.getenv("AGORA_GAMES_DIR", "").strip()
    if configured:
        candidate = Path(configured)
        return candidate if candidate.is_absolute() else (PROJECT_ROOT / candidate)
    return PROJECT_ROOT / "games"


def ensure_games_structure(base_path: Path | None = None) -> Path:
    """Crea games/, games/custom y games/standard si no existen."""
    root = resolve_games_base_path(base_path)
    (root / "custom").mkdir(parents=True, exist_ok=True)
    (root / "standard").mkdir(parents=True, exist_ok=True)
    return root


def save_custom_game(session_id: str, setup: dict[str, Any], base_path: Path | None = None) -> Path:
    """Guarda personajes y contexto de una partida custom en games/custom/<session_id>/."""
    root = ensure_games_structure(base_path)
    game_dir = root / "custom" / session_id
    game_dir.mkdir(parents=True, exist_ok=True)

    actors = setup.get("actors", [])
    context = {k: v for k, v in setup.items() if k != "actors"}

    with (game_dir / "characters.json").open("w", encoding="utf-8") as f:
        json.dump(actors, f, indent=2, ensure_ascii=False)
    with (game_dir / "context.json").open("w", encoding="utf-8") as f:
        json.dump(context, f, indent=2, ensure_ascii=False)

    return game_dir
