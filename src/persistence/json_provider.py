"""Implementación JSON de PersistenceProvider."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .provider import PersistenceProvider

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class JsonPersistenceProvider(PersistenceProvider):
    """Persistencia en filesystem con estructura por partida."""

    def __init__(self, base_path: Path | None = None, username: str = "usuario") -> None:
        self._username = username
        self._root = self._resolve_base_path(base_path)
        (self._root / "custom").mkdir(parents=True, exist_ok=True)
        (self._root / "standard").mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _resolve_base_path(base_path: Path | None = None) -> Path:
        if base_path is not None:
            return base_path
        configured = os.getenv("AGORA_GAMES_DIR", "").strip()
        if configured:
            candidate = Path(configured)
            return candidate if candidate.is_absolute() else (PROJECT_ROOT / candidate)
        return PROJECT_ROOT / "games"

    def _game_dir(self, game_id: str) -> Path:
        return self._root / "custom" / game_id

    @staticmethod
    def _read_json(path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _write_json(path: Path, data: Any) -> None:
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _require_game(self, game_id: str) -> Path:
        game_dir = self._game_dir(game_id)
        if not game_dir.exists():
            raise KeyError(f"Game not found: {game_id}")
        return game_dir

    def create_game(
        self,
        title: str,
        config_json: dict[str, Any],
        username: str | None = None,
    ) -> str:
        if not isinstance(config_json, dict) or not config_json:
            raise ValueError("config_json inválido")
        actors = config_json.get("actors")
        if not isinstance(actors, list):
            raise ValueError("config_json debe contener actors como lista")

        game_id = str(uuid.uuid4())
        game_dir = self._game_dir(game_id)
        game_dir.mkdir(parents=True, exist_ok=False)
        created_at = _utc_now_iso()
        game_info = {
            "id": game_id,
            "user": (username or self._username),
            "title": (title or "").strip() or "Partida",
            "status": "active",
            "created_at": created_at,
            "updated_at": created_at,
        }
        self._write_json(game_dir / "game.json", game_info)
        self._write_json(game_dir / "config.json", config_json)
        self._write_json(game_dir / "characters.json", actors)
        self._write_json(game_dir / "context.json", {k: v for k, v in config_json.items() if k != "actors"})
        self._write_json(game_dir / "state.json", {"turn": 0, "messages": [], "metadata": {}, "updated_at": created_at})
        self._write_json(game_dir / "messages.json", [])
        return game_id

    def save_game_state(self, game_id: str, state_json: dict[str, Any]) -> None:
        if not isinstance(state_json, dict):
            raise ValueError("state_json inválido")
        game_dir = self._require_game(game_id)
        state = dict(state_json)
        state["updated_at"] = _utc_now_iso()
        self._write_json(game_dir / "state.json", state)
        game_info = self._read_json(game_dir / "game.json", {})
        if isinstance(game_info, dict):
            game_info["updated_at"] = state["updated_at"]
            self._write_json(game_dir / "game.json", game_info)

    def append_message(
        self,
        game_id: str,
        turn_number: int,
        role: str,
        content: str,
        metadata_json: dict[str, Any] | None = None,
    ) -> None:
        if turn_number < 0:
            raise ValueError("turn_number debe ser >= 0")
        game_dir = self._require_game(game_id)
        messages = self._read_json(game_dir / "messages.json", [])
        if not isinstance(messages, list):
            messages = []
        msg = {
            "id": str(uuid.uuid4()),
            "game_id": game_id,
            "turn_number": int(turn_number),
            "role": role or "actor",
            "content": content or "",
            "metadata_json": metadata_json or {},
            "created_at": _utc_now_iso(),
        }
        messages.append(msg)
        messages.sort(key=lambda m: (int(m.get("turn_number", 0)), m.get("created_at", "")))
        self._write_json(game_dir / "messages.json", messages)

    def get_game(self, game_id: str) -> dict[str, Any]:
        game_dir = self._require_game(game_id)
        game_info = self._read_json(game_dir / "game.json", {})
        config_json = self._read_json(game_dir / "config.json", {})
        state_json = self._read_json(game_dir / "state.json", {})
        return {
            "id": game_id,
            "title": game_info.get("title", ""),
            "status": game_info.get("status", "active"),
            "user": game_info.get("user", self._username),
            "created_at": game_info.get("created_at"),
            "updated_at": game_info.get("updated_at"),
            "config_json": config_json,
            "state_json": state_json,
        }

    def get_game_messages(self, game_id: str) -> list[dict[str, Any]]:
        game_dir = self._require_game(game_id)
        messages = self._read_json(game_dir / "messages.json", [])
        if not isinstance(messages, list):
            return []
        messages.sort(key=lambda m: (int(m.get("turn_number", 0)), m.get("created_at", "")))
        return messages

    def list_games_for_user(self, username: str) -> list[dict[str, Any]]:
        games_dir = self._root / "custom"
        if not games_dir.exists():
            return []
        items: list[dict[str, Any]] = []
        for child in games_dir.iterdir():
            if not child.is_dir():
                continue
            game_info = self._read_json(child / "game.json", {})
            if not isinstance(game_info, dict):
                continue
            if game_info.get("user", self._username) != username:
                continue
            items.append(
                {
                    "id": game_info.get("id", child.name),
                    "title": game_info.get("title", ""),
                    "status": game_info.get("status", "active"),
                    "created_at": game_info.get("created_at"),
                    "updated_at": game_info.get("updated_at"),
                }
            )
        items.sort(key=lambda x: (x.get("updated_at") or "", x.get("id") or ""), reverse=True)
        return items
