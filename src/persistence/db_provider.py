"""Implementación PostgreSQL de PersistenceProvider."""

from __future__ import annotations

import importlib
import json
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .provider import PersistenceProvider

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DatabasePersistenceProvider(PersistenceProvider):
    """Persistencia transaccional en PostgreSQL."""

    def __init__(self, dsn: str | None = None, run_migrations: bool = True, ensure_user: bool = True) -> None:
        self._dsn = (dsn or os.getenv("DATABASE_URL", "")).strip()
        if not self._dsn:
            raise RuntimeError("DATABASE_URL no configurada para PERSISTENCE_MODE=db")
        try:
            self._psycopg = importlib.import_module("psycopg")
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Falta dependencia 'psycopg'. Instala el driver PostgreSQL para usar PERSISTENCE_MODE=db."
            ) from exc
        if run_migrations:
            self.apply_migrations()
        if ensure_user:
            self.ensure_default_user()

    @contextmanager
    def _connection(self):
        conn = self._psycopg.connect(self._dsn, autocommit=False)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def _split_sql_script(script: str) -> list[str]:
        chunks = []
        current = []
        for line in script.splitlines():
            current.append(line)
            if line.strip().endswith(";"):
                statement = "\n".join(current).strip()
                if statement:
                    chunks.append(statement)
                current = []
        if current:
            statement = "\n".join(current).strip()
            if statement:
                chunks.append(statement)
        return chunks

    def apply_migrations(self) -> None:
        migrations_dir = PROJECT_ROOT / "migrations"
        if not migrations_dir.exists():
            return
        migration_files = sorted(p for p in migrations_dir.glob("*.sql") if p.is_file())
        if not migration_files:
            return
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        version VARCHAR PRIMARY KEY,
                        applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )
                for migration in migration_files:
                    version = migration.name
                    cur.execute("SELECT 1 FROM schema_migrations WHERE version = %s", (version,))
                    if cur.fetchone():
                        continue
                    sql_script = migration.read_text(encoding="utf-8")
                    for statement in self._split_sql_script(sql_script):
                        cur.execute(statement)
                    cur.execute(
                        "INSERT INTO schema_migrations (version, applied_at) VALUES (%s, %s)",
                        (version, _utc_now()),
                    )

    def _get_user_id(self, cur, username: str) -> str:
        cur.execute("SELECT id::text FROM users WHERE username = %s", (username,))
        row = cur.fetchone()
        if not row:
            raise KeyError(f"User not found: {username}")
        return row[0]

    def ensure_default_user(self, username: str = "usuario") -> None:
        with self._connection() as conn:
            with conn.cursor() as cur:
                user_id = str(uuid.uuid4())
                cur.execute(
                    """
                    INSERT INTO users (id, username, created_at)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (username) DO NOTHING
                    """,
                    (user_id, username, _utc_now()),
                )

    def create_game(self, title: str, config_json: dict[str, Any]) -> str:
        if not isinstance(config_json, dict) or not config_json:
            raise ValueError("config_json inválido")
        game_id = str(uuid.uuid4())
        with self._connection() as conn:
            with conn.cursor() as cur:
                user_id = self._get_user_id(cur, "usuario")
                now = _utc_now()
                cur.execute(
                    """
                    INSERT INTO games (id, user_id, title, status, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (game_id, user_id, (title or "").strip() or "Partida", "active", now, now),
                )
                cur.execute(
                    "INSERT INTO game_configs (game_id, config_json) VALUES (%s, %s::jsonb)",
                    (game_id, json.dumps(config_json, ensure_ascii=False)),
                )
                cur.execute(
                    "INSERT INTO game_states (game_id, state_json, updated_at) VALUES (%s, %s::jsonb, %s)",
                    (game_id, json.dumps({"turn": 0, "messages": [], "metadata": {}}, ensure_ascii=False), now),
                )
        return game_id

    def save_game_state(self, game_id: str, state_json: dict[str, Any]) -> None:
        if not isinstance(state_json, dict):
            raise ValueError("state_json inválido")
        with self._connection() as conn:
            with conn.cursor() as cur:
                now = _utc_now()
                cur.execute(
                    """
                    UPDATE game_states
                    SET state_json = %s::jsonb, updated_at = %s
                    WHERE game_id = %s
                    """,
                    (json.dumps(state_json, ensure_ascii=False), now, game_id),
                )
                if cur.rowcount == 0:
                    raise KeyError(f"Game not found: {game_id}")
                cur.execute("UPDATE games SET updated_at = %s WHERE id = %s", (now, game_id))

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
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM games WHERE id = %s", (game_id,))
                if not cur.fetchone():
                    raise KeyError(f"Game not found: {game_id}")
                msg_id = str(uuid.uuid4())
                now = _utc_now()
                cur.execute(
                    """
                    INSERT INTO messages (id, game_id, turn_number, role, content, metadata_json, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s)
                    """,
                    (
                        msg_id,
                        game_id,
                        int(turn_number),
                        role or "actor",
                        content or "",
                        json.dumps(metadata_json or {}, ensure_ascii=False),
                        now,
                    ),
                )
                cur.execute("UPDATE games SET updated_at = %s WHERE id = %s", (now, game_id))

    def get_game(self, game_id: str) -> dict[str, Any]:
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT g.id::text, u.username, g.title, g.status, g.created_at, g.updated_at,
                           gc.config_json, gs.state_json
                    FROM games g
                    JOIN users u ON u.id = g.user_id
                    JOIN game_configs gc ON gc.game_id = g.id
                    JOIN game_states gs ON gs.game_id = g.id
                    WHERE g.id = %s
                    """,
                    (game_id,),
                )
                row = cur.fetchone()
                if not row:
                    raise KeyError(f"Game not found: {game_id}")
                return {
                    "id": row[0],
                    "user": row[1],
                    "title": row[2],
                    "status": row[3],
                    "created_at": row[4].isoformat() if row[4] else None,
                    "updated_at": row[5].isoformat() if row[5] else None,
                    "config_json": row[6] or {},
                    "state_json": row[7] or {},
                }

    def get_game_messages(self, game_id: str) -> list[dict[str, Any]]:
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM games WHERE id = %s", (game_id,))
                if not cur.fetchone():
                    raise KeyError(f"Game not found: {game_id}")
                cur.execute(
                    """
                    SELECT id::text, game_id::text, turn_number, role, content, metadata_json, created_at
                    FROM messages
                    WHERE game_id = %s
                    ORDER BY turn_number ASC, created_at ASC
                    """,
                    (game_id,),
                )
                rows = cur.fetchall()
                return [
                    {
                        "id": r[0],
                        "game_id": r[1],
                        "turn_number": r[2],
                        "role": r[3],
                        "content": r[4],
                        "metadata_json": r[5] or {},
                        "created_at": r[6].isoformat() if r[6] else None,
                    }
                    for r in rows
                ]

    def list_games_for_user(self, username: str) -> list[dict[str, Any]]:
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT g.id::text, g.title, g.status, g.created_at, g.updated_at
                    FROM games g
                    JOIN users u ON u.id = g.user_id
                    WHERE u.username = %s
                    ORDER BY g.updated_at DESC
                    """,
                    (username,),
                )
                rows = cur.fetchall()
                return [
                    {
                        "id": r[0],
                        "title": r[1],
                        "status": r[2],
                        "created_at": r[3].isoformat() if r[3] else None,
                        "updated_at": r[4].isoformat() if r[4] else None,
                    }
                    for r in rows
                ]
