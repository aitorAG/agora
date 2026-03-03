from __future__ import annotations

import importlib
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

DB_PATH = Path(os.getenv("TELEMETRY_DB_PATH", "/data/telemetry.db"))
INGEST_KEY = (os.getenv("TELEMETRY_INGEST_KEY") or "").strip()
MAX_BATCH_SIZE = max(1, int((os.getenv("TELEMETRY_MAX_BATCH") or "256").strip()))


class TelemetryEventIn(BaseModel):
    event_type: str = "llm_call"
    timestamp: str | None = None
    flow: str = ""
    interaction_id: str = ""
    user_id: str = ""
    game_id: str = ""
    turn: int = 0
    agent_name: str = ""
    agent_type: str = ""
    agent_step: str = ""
    username: str = ""
    provider: str = ""
    model: str = ""
    generation_name: str = ""
    duration_ms: int = 0
    status: str = "ok"
    status_message: str = ""
    stream: bool = False
    usage_input_tokens: int = 0
    usage_output_tokens: int = 0
    usage_total_tokens: int = 0
    cost_input: float = 0.0
    cost_output: float = 0.0
    cost_total: float = 0.0
    output_chars: int = 0


class TelemetryBatchIn(BaseModel):
    events: list[TelemetryEventIn] = Field(default_factory=list)


TelemetryEventIn.model_rebuild()
TelemetryBatchIn.model_rebuild()


def _normalize_timestamp(value: str | None) -> str:
    if not value:
        return datetime.now(timezone.utc).isoformat()
    try:
        return (
            datetime.fromisoformat(value.replace("Z", "+00:00"))
            .astimezone(timezone.utc)
            .isoformat()
        )
    except ValueError:
        return datetime.now(timezone.utc).isoformat()


def _iso_day(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        try:
            return str(value.isoformat())[:10]
        except Exception:
            return str(value)[:10]
    return str(value)[:10]


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _normalize_agent_type_value(agent_name: str, agent_type: str) -> str:
    cleaned = (agent_type or "").strip()
    if cleaned:
        return cleaned
    if (agent_name or "").strip() == "Observer":
        return "observer"
    if (agent_name or "").strip() == "Guionista":
        return "guionista"
    return "unknown"


def _agent_group(agent_type: str) -> str:
    cleaned = (agent_type or "").strip().lower()
    if cleaned in {"actor", "observer", "guionista"}:
        return cleaned
    return "unknown"


def _agent_group_label(agent_type: str) -> str:
    group = _agent_group(agent_type)
    if group == "actor":
        return "Actores"
    if group == "observer":
        return "Observer"
    if group == "guionista":
        return "Guionista"
    return "Otros"


def _runtime_context() -> str:
    explicit = (os.getenv("AGORA_RUNTIME_CONTEXT") or "").strip().lower()
    if explicit:
        return explicit
    if Path("/.dockerenv").exists():
        return "docker"
    return "host"


def _derive_app_db_dsn() -> str:
    direct = (os.getenv("DATABASE_URL") or "").strip()
    if direct:
        return direct
    user = (os.getenv("POSTGRES_USER") or "agora_user").strip()
    password = (os.getenv("POSTGRES_PASSWORD") or "").strip()
    database = (os.getenv("POSTGRES_DB") or "agora").strip()
    if not password:
        return ""
    default_host = "postgres" if _runtime_context() == "docker" else "localhost"
    host = (os.getenv("AGORA_DB_HOST") or default_host).strip()
    port = (os.getenv("AGORA_DB_PORT") or "5432").strip()
    return f"postgresql://{quote(user)}:{quote(password)}@{host}:{port}/{quote(database)}"


def _db_connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


@contextmanager
def _sqlite_cursor() -> Any:
    conn = _db_connect()
    try:
        cur = conn.cursor()
        yield cur
        conn.commit()
    finally:
        conn.close()


def _sqlite_column_exists(cur: sqlite3.Cursor, table: str, column: str) -> bool:
    rows = cur.execute(f"PRAGMA table_info({table})").fetchall()
    return any(str(row[1]) == column for row in rows)


def _sqlite_fetchone(
    query: str,
    params: list[Any] | tuple[Any, ...] | None = None,
) -> sqlite3.Row | None:
    with _sqlite_cursor() as cur:
        return cur.execute(query, params or []).fetchone()


def _sqlite_fetchall(
    query: str,
    params: list[Any] | tuple[Any, ...] | None = None,
) -> list[sqlite3.Row]:
    with _sqlite_cursor() as cur:
        return cur.execute(query, params or []).fetchall()


def _app_db_connect():
    dsn = _derive_app_db_dsn()
    if not dsn:
        raise HTTPException(status_code=503, detail="Main database is not configured")
    try:
        psycopg = importlib.import_module("psycopg")
    except ModuleNotFoundError as exc:
        raise HTTPException(status_code=503, detail="Missing psycopg dependency") from exc
    try:
        return psycopg.connect(dsn, autocommit=True)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Main database unavailable: {exc}",
        ) from exc


@contextmanager
def _app_cursor() -> Any:
    conn = _app_db_connect()
    try:
        with conn.cursor() as cur:
            yield cur
    finally:
        conn.close()


def _app_fetchone(
    query: str,
    params: list[Any] | tuple[Any, ...] | None = None,
) -> Any:
    with _app_cursor() as cur:
        return cur.execute(query, params or []).fetchone()


def _app_fetchall(
    query: str,
    params: list[Any] | tuple[Any, ...] | None = None,
) -> list[Any]:
    with _app_cursor() as cur:
        return cur.execute(query, params or []).fetchall()

def _init_db() -> None:
    with _sqlite_cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS llm_calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                flow TEXT NOT NULL,
                interaction_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                game_id TEXT NOT NULL,
                turn INTEGER NOT NULL,
                agent_name TEXT NOT NULL,
                agent_type TEXT NOT NULL DEFAULT '',
                agent_step TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                generation_name TEXT NOT NULL,
                duration_ms INTEGER NOT NULL,
                status TEXT NOT NULL,
                status_message TEXT NOT NULL,
                stream INTEGER NOT NULL,
                usage_input_tokens INTEGER NOT NULL,
                usage_output_tokens INTEGER NOT NULL,
                usage_total_tokens INTEGER NOT NULL,
                cost_input REAL NOT NULL,
                cost_output REAL NOT NULL,
                cost_total REAL NOT NULL,
                output_chars INTEGER NOT NULL
            )
            """
        )
        if not _sqlite_column_exists(cur, "llm_calls", "agent_type"):
            cur.execute("ALTER TABLE llm_calls ADD COLUMN agent_type TEXT NOT NULL DEFAULT ''")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS user_access_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                user_id TEXT NOT NULL,
                username TEXT NOT NULL,
                status TEXT NOT NULL,
                status_message TEXT NOT NULL
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_llm_calls_timestamp ON llm_calls(timestamp)")
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_llm_calls_user_game ON llm_calls(user_id, game_id)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_llm_calls_game_turn ON llm_calls(game_id, turn)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_llm_calls_agent ON llm_calls(agent_name, agent_type)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_user_access_timestamp ON user_access_events(timestamp)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_user_access_user_id ON user_access_events(user_id)"
        )


def _ingest_auth(x_agora_ingest_key: str | None) -> None:
    if not INGEST_KEY:
        return
    if (x_agora_ingest_key or "").strip() != INGEST_KEY:
        raise HTTPException(status_code=401, detail="Invalid ingest key")


def _game_display_name(title: Any, created_at: Any) -> str:
    base = str(title or "Partida").strip() or "Partida"
    timestamp = str(created_at.isoformat() if hasattr(created_at, "isoformat") else created_at or "")
    return f"{base}_{timestamp}" if timestamp else base


def _llm_where(
    user_keys: list[str] | None = None,
    game_id: str | None = None,
    require_game: bool = False,
) -> tuple[str, list[Any]]:
    clauses: list[str] = ["NOT (TRIM(agent_name) = '' AND TRIM(agent_type) = '')"]
    params: list[Any] = []
    if require_game:
        clauses.append("TRIM(game_id) <> ''")
    safe_user_keys = [key for key in (user_keys or []) if key]
    if safe_user_keys:
        placeholders = ", ".join("?" for _ in safe_user_keys)
        clauses.append(f"user_id IN ({placeholders})")
        params.extend(safe_user_keys)
    if game_id:
        clauses.append("game_id = ?")
        params.append(game_id)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    return where, params


def _user_keys(user_id: str) -> list[str]:
    row = _app_fetchone("SELECT id::text, username FROM users WHERE id = %s", [user_id])
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return [str(row[0] or ""), str(row[1] or "")]


def _user_directory() -> list[dict[str, Any]]:
    rows = _app_fetchall(
        """
        SELECT id::text, username, created_at
        FROM users
        ORDER BY username ASC, created_at ASC
        """
    )
    return [
        {
            "id": str(row[0] or ""),
            "username": str(row[1] or ""),
            "created_at": (
                row[2].isoformat() if hasattr(row[2], "isoformat") else str(row[2] or "")
            ),
        }
        for row in rows
    ]


def _users_ranked_by_cost() -> list[dict[str, Any]]:
    directory = _user_directory()
    by_key: dict[str, dict[str, Any]] = {}
    ranked: list[dict[str, Any]] = []
    for user in directory:
        item = {
            "user_id": user["id"],
            "username": user["username"],
            "created_at": user["created_at"],
            "total_cost": 0.0,
            "total_tokens": 0,
            "games": set(),
        }
        ranked.append(item)
        by_key[user["id"]] = item
        by_key[user["username"]] = item

    rows = _sqlite_fetchall(
        """
        SELECT user_id, game_id, COALESCE(SUM(cost_total), 0.0), COALESCE(SUM(usage_total_tokens), 0)
        FROM llm_calls
        WHERE TRIM(user_id) <> ''
          AND TRIM(game_id) <> ''
          AND NOT (TRIM(agent_name) = '' AND TRIM(agent_type) = '')
        GROUP BY user_id, game_id
        """
    )
    for row in rows:
        key = str(row[0] or "")
        target = by_key.get(key)
        if not target:
            continue
        target["total_cost"] += _safe_float(row[2])
        target["total_tokens"] += _safe_int(row[3])
        game_id = str(row[1] or "").strip()
        if game_id:
            target["games"].add(game_id)

    items = [
        {
            "user_id": item["user_id"],
            "username": item["username"],
            "created_at": item["created_at"],
            "total_cost": round(float(item["total_cost"]), 12),
            "total_tokens": int(item["total_tokens"]),
            "tracked_games": len(item["games"]),
        }
        for item in ranked
    ]
    items.sort(
        key=lambda item: (
            float(item["total_cost"]),
            int(item["total_tokens"]),
            item["username"],
        ),
        reverse=True,
    )
    return items


def _general_metrics() -> dict[str, Any]:
    total_users_row = _app_fetchone("SELECT COUNT(*) FROM users")
    user_series_rows = _app_fetchall(
        """
        SELECT DATE(created_at) AS day, COUNT(*) AS value
        FROM users
        GROUP BY DATE(created_at)
        ORDER BY DATE(created_at) ASC
        """
    )
    games_played_rows = _app_fetchall(
        """
        SELECT DATE(created_at) AS day, COUNT(DISTINCT game_id) AS value
        FROM messages
        GROUP BY DATE(created_at)
        ORDER BY DATE(created_at) ASC
        """
    )
    access_rows = _sqlite_fetchall(
        """
        SELECT substr(timestamp, 1, 10) AS day, COUNT(*) AS value
        FROM user_access_events
        WHERE event_type = 'user_login' AND status = 'ok'
        GROUP BY substr(timestamp, 1, 10)
        ORDER BY day ASC
        """
    )
    token_cost_row = _sqlite_fetchone(
        """
        SELECT
            COALESCE(AVG(total_tokens), 0) AS avg_tokens_per_game,
            COALESCE(MAX(total_tokens), 0) AS max_tokens_per_game,
            COALESCE(AVG(total_cost), 0.0) AS avg_cost_per_game,
            COALESCE(MAX(total_cost), 0.0) AS max_cost_per_game,
            COALESCE(SUM(total_cost), 0.0) AS historical_total_cost
        FROM (
            SELECT game_id,
                   SUM(usage_total_tokens) AS total_tokens,
                   SUM(cost_total) AS total_cost
            FROM llm_calls
            WHERE game_id <> ''
              AND NOT (TRIM(agent_name) = '' AND TRIM(agent_type) = '')
            GROUP BY game_id
        ) aggregated_games
        """
    )
    daily_tokens_rows = _sqlite_fetchall(
        """
        SELECT substr(timestamp, 1, 10) AS day, COALESCE(SUM(usage_total_tokens), 0) AS value
        FROM llm_calls
        WHERE TRIM(game_id) <> ''
          AND NOT (TRIM(agent_name) = '' AND TRIM(agent_type) = '')
        GROUP BY substr(timestamp, 1, 10)
        ORDER BY day ASC
        """
    )
    wait_row = _sqlite_fetchone(
        """
        SELECT COALESCE(AVG(interaction_duration), 0) AS avg_wait_ms
        FROM (
            SELECT interaction_id, SUM(duration_ms) AS interaction_duration
            FROM llm_calls
            WHERE interaction_id <> ''
              AND TRIM(game_id) <> ''
              AND NOT (TRIM(agent_name) = '' AND TRIM(agent_type) = '')
            GROUP BY interaction_id
        ) interactions
        """
    )
    users_ranked = _users_ranked_by_cost()
    active_games_today = _safe_int(games_played_rows[-1][1]) if games_played_rows else 0
    total_tracked_tokens = sum(_safe_int(item["total_tokens"]) for item in users_ranked)
    return {
        "kpis": {
            "total_users": _safe_int(total_users_row[0] if total_users_row else 0),
            "active_games_today": active_games_today,
            "avg_tokens_per_game": _safe_int(token_cost_row[0] if token_cost_row else 0),
            "max_tokens_per_game": _safe_int(token_cost_row[1] if token_cost_row else 0),
            "total_tracked_tokens": total_tracked_tokens,
            "avg_cost_per_game": _safe_float(token_cost_row[2] if token_cost_row else 0.0),
            "max_cost_per_game": _safe_float(token_cost_row[3] if token_cost_row else 0.0),
            "historical_total_cost": _safe_float(token_cost_row[4] if token_cost_row else 0.0),
            "avg_wait_ms": _safe_int(wait_row[0] if wait_row else 0),
        },
        "series": {
            "registered_users_per_day": [
                {"day": _iso_day(row[0]), "value": _safe_int(row[1])}
                for row in user_series_rows
            ],
            "user_accesses_per_day": [
                {"day": str(row[0] or ""), "value": _safe_int(row[1])}
                for row in access_rows
            ],
            "games_played_per_day": [
                {"day": _iso_day(row[0]), "value": _safe_int(row[1])}
                for row in games_played_rows
            ],
            "tokens_per_day": [
                {"day": str(row[0] or ""), "value": _safe_int(row[1])}
                for row in daily_tokens_rows
            ],
        },
        "rankings": {
            "users_by_cost": users_ranked,
        },
    }


def _agent_metrics() -> dict[str, Any]:
    rows = _sqlite_fetchall(
        """
        SELECT
            CASE
                WHEN TRIM(agent_type) <> '' THEN agent_type
                WHEN agent_name = 'Observer' THEN 'observer'
                WHEN agent_name = 'Guionista' THEN 'guionista'
                ELSE 'unknown'
            END AS normalized_agent_type,
            COUNT(*) AS calls,
            COALESCE(SUM(usage_input_tokens), 0) AS input_tokens,
            COALESCE(SUM(usage_output_tokens), 0) AS output_tokens,
            COALESCE(SUM(usage_total_tokens), 0) AS total_tokens,
            COALESCE(SUM(cost_input), 0.0) AS cost_input,
            COALESCE(SUM(cost_output), 0.0) AS cost_output,
            COALESCE(SUM(cost_total), 0.0) AS cost_total,
            COALESCE(MIN(duration_ms), 0) AS min_duration_ms,
            COALESCE(MAX(duration_ms), 0) AS max_duration_ms,
            COALESCE(AVG(duration_ms), 0) AS avg_duration_ms,
            COALESCE(MIN(usage_total_tokens), 0) AS min_tokens_per_call,
            COALESCE(MAX(usage_total_tokens), 0) AS max_tokens_per_call,
            COALESCE(AVG(usage_total_tokens), 0) AS avg_tokens_per_call
        FROM llm_calls
        WHERE TRIM(game_id) <> ''
          AND NOT (TRIM(agent_name) = '' AND TRIM(agent_type) = '')
        GROUP BY normalized_agent_type
        ORDER BY 8 DESC, 5 DESC, 11 DESC
        """
    )
    return {
        "items": [
            {
                "agent_type": _agent_group(str(row[0] or "unknown")),
                "agent_label": _agent_group_label(str(row[0] or "unknown")),
                "calls": _safe_int(row[1]),
                "input_tokens": _safe_int(row[2]),
                "output_tokens": _safe_int(row[3]),
                "total_tokens": _safe_int(row[4]),
                "cost_input": _safe_float(row[5]),
                "cost_output": _safe_float(row[6]),
                "cost_total": _safe_float(row[7]),
                "min_duration_ms": _safe_int(row[8]),
                "max_duration_ms": _safe_int(row[9]),
                "avg_duration_ms": _safe_int(row[10]),
                "min_tokens_per_call": _safe_int(row[11]),
                "max_tokens_per_call": _safe_int(row[12]),
                "avg_tokens_per_call": _safe_int(row[13]),
            }
            for row in rows
            if str(row[0] or "").strip()
        ]
    }

def _all_users_detail() -> dict[str, Any]:
    telemetry_row = _sqlite_fetchone(
        """
        SELECT
            COALESCE(SUM(usage_input_tokens), 0),
            COALESCE(SUM(usage_output_tokens), 0),
            COALESCE(SUM(usage_total_tokens), 0),
            COALESCE(SUM(cost_input), 0.0),
            COALESCE(SUM(cost_output), 0.0),
            COALESCE(SUM(cost_total), 0.0)
        FROM llm_calls
        WHERE TRIM(game_id) <> ''
          AND NOT (TRIM(agent_name) = '' AND TRIM(agent_type) = '')
        """
    )
    games_rows = _app_fetchall(
        """
        SELECT
            g.id::text,
            g.title,
            g.status,
            g.created_at,
            COALESCE((gs.state_json ->> 'turn')::int, 0) AS turns,
            MAX(CASE WHEN m.role = 'player' THEN m.created_at ELSE NULL END) AS last_player_message_at,
            u.username
        FROM games g
        JOIN users u ON u.id = g.user_id
        JOIN game_states gs ON gs.game_id = g.id
        LEFT JOIN messages m ON m.game_id = g.id
        GROUP BY g.id, g.title, g.status, g.created_at, gs.state_json, u.username
        ORDER BY COALESCE(MAX(m.created_at), g.created_at) DESC
        """
    )
    total_users_row = _app_fetchone("SELECT COUNT(*) FROM users")
    return {
        "user": {
            "id": "__all__",
            "username": "Todos los usuarios",
            "created_at": "",
            "game_count": len(games_rows),
            "user_count": _safe_int(total_users_row[0] if total_users_row else 0),
        },
        "tokens": {
            "input": _safe_int(telemetry_row[0] if telemetry_row else 0),
            "output": _safe_int(telemetry_row[1] if telemetry_row else 0),
            "total": _safe_int(telemetry_row[2] if telemetry_row else 0),
        },
        "cost": {
            "input": _safe_float(telemetry_row[3] if telemetry_row else 0.0),
            "output": _safe_float(telemetry_row[4] if telemetry_row else 0.0),
            "total": _safe_float(telemetry_row[5] if telemetry_row else 0.0),
        },
        "games": [
            {
                "game_id": str(row[0] or ""),
                "display_name": f"{str(row[6] or '')} / {_game_display_name(row[1], row[3])}",
                "title": str(row[1] or "Partida"),
                "status": str(row[2] or "unknown"),
                "created_at": (
                    row[3].isoformat() if hasattr(row[3], "isoformat") else str(row[3] or "")
                ),
                "turns": _safe_int(row[4]),
                "last_player_message_at": (
                    row[5].isoformat()
                    if hasattr(row[5], "isoformat")
                    else (str(row[5] or "") if row[5] else "")
                ),
            }
            for row in games_rows
        ],
    }


def _user_detail(user_id: str | None) -> dict[str, Any]:
    if not user_id or user_id == "__all__":
        return _all_users_detail()
    user_row = _app_fetchone(
        "SELECT id::text, username, created_at FROM users WHERE id = %s",
        [user_id],
    )
    if not user_row:
        raise HTTPException(status_code=404, detail="User not found")
    user_keys = [str(user_row[0] or ""), str(user_row[1] or "")]
    summary_where, summary_params = _llm_where(user_keys=user_keys, require_game=True)
    telemetry_row = _sqlite_fetchone(
        f"""
        SELECT
            COALESCE(SUM(usage_input_tokens), 0),
            COALESCE(SUM(usage_output_tokens), 0),
            COALESCE(SUM(usage_total_tokens), 0),
            COALESCE(SUM(cost_input), 0.0),
            COALESCE(SUM(cost_output), 0.0),
            COALESCE(SUM(cost_total), 0.0)
        FROM llm_calls
        {summary_where}
        """,
        summary_params,
    )
    games_rows = _app_fetchall(
        """
        SELECT
            g.id::text,
            g.title,
            g.status,
            g.created_at,
            COALESCE((gs.state_json ->> 'turn')::int, 0) AS turns,
            MAX(CASE WHEN m.role = 'player' THEN m.created_at ELSE NULL END) AS last_player_message_at
        FROM games g
        JOIN game_states gs ON gs.game_id = g.id
        LEFT JOIN messages m ON m.game_id = g.id
        WHERE g.user_id = %s
        GROUP BY g.id, g.title, g.status, g.created_at, gs.state_json
        ORDER BY COALESCE(MAX(m.created_at), g.created_at) DESC
        """,
        [user_id],
    )
    return {
        "user": {
            "id": str(user_row[0] or ""),
            "username": str(user_row[1] or ""),
            "created_at": (
                user_row[2].isoformat()
                if hasattr(user_row[2], "isoformat")
                else str(user_row[2] or "")
            ),
            "game_count": len(games_rows),
        },
        "tokens": {
            "input": _safe_int(telemetry_row[0] if telemetry_row else 0),
            "output": _safe_int(telemetry_row[1] if telemetry_row else 0),
            "total": _safe_int(telemetry_row[2] if telemetry_row else 0),
        },
        "cost": {
            "input": _safe_float(telemetry_row[3] if telemetry_row else 0.0),
            "output": _safe_float(telemetry_row[4] if telemetry_row else 0.0),
            "total": _safe_float(telemetry_row[5] if telemetry_row else 0.0),
        },
        "games": [
            {
                "game_id": str(row[0] or ""),
                "display_name": _game_display_name(row[1], row[3]),
                "title": str(row[1] or "Partida"),
                "status": str(row[2] or "unknown"),
                "created_at": (
                    row[3].isoformat() if hasattr(row[3], "isoformat") else str(row[3] or "")
                ),
                "turns": _safe_int(row[4]),
                "last_player_message_at": (
                    row[5].isoformat()
                    if hasattr(row[5], "isoformat")
                    else (str(row[5] or "") if row[5] else "")
                ),
            }
            for row in games_rows
        ],
    }


def _game_detail(game_id: str) -> dict[str, Any]:
    game_row = _app_fetchone(
        """
        SELECT
            g.id::text,
            g.user_id::text,
            u.username,
            g.title,
            g.status,
            g.created_at,
            COALESCE((gs.state_json ->> 'turn')::int, 0) AS turns
        FROM games g
        JOIN users u ON u.id = g.user_id
        JOIN game_states gs ON gs.game_id = g.id
        WHERE g.id = %s
        """,
        [game_id],
    )
    if not game_row:
        raise HTTPException(status_code=404, detail="Game not found")
    user_keys = [str(game_row[1] or ""), str(game_row[2] or "")]
    summary_where, summary_params = _llm_where(user_keys=user_keys, game_id=game_id)
    telemetry_row = _sqlite_fetchone(
        f"""
        SELECT
            COALESCE(SUM(usage_input_tokens), 0),
            COALESCE(SUM(usage_output_tokens), 0),
            COALESCE(SUM(usage_total_tokens), 0),
            COALESCE(SUM(cost_input), 0.0),
            COALESCE(SUM(cost_output), 0.0),
            COALESCE(SUM(cost_total), 0.0)
        FROM llm_calls
        {summary_where}
        """,
        summary_params,
    )
    agent_rows = _sqlite_fetchall(
        f"""
        SELECT
            agent_name,
            CASE
                WHEN TRIM(agent_type) <> '' THEN agent_type
                WHEN agent_name = 'Observer' THEN 'observer'
                WHEN agent_name = 'Guionista' THEN 'guionista'
                ELSE 'unknown'
            END AS normalized_agent_type,
            COALESCE(SUM(usage_input_tokens), 0),
            COALESCE(SUM(usage_output_tokens), 0),
            COALESCE(SUM(usage_total_tokens), 0),
            COALESCE(SUM(cost_input), 0.0),
            COALESCE(SUM(cost_output), 0.0),
            COALESCE(SUM(cost_total), 0.0),
            COALESCE(MIN(duration_ms), 0),
            COALESCE(MAX(duration_ms), 0),
            COALESCE(AVG(duration_ms), 0),
            COUNT(*)
        FROM llm_calls
        {summary_where}
        GROUP BY agent_name, normalized_agent_type
        ORDER BY 8 DESC, 5 DESC, 11 DESC
        """,
        summary_params,
    )
    message_rows = _app_fetchall(
        """
        SELECT role, content, metadata_json, created_at
        FROM messages
        WHERE game_id = %s
        ORDER BY turn_number ASC, created_at ASC
        """,
        [game_id],
    )
    messages = []
    for row in message_rows:
        metadata = row[2] if isinstance(row[2], dict) else {}
        sender = str(metadata.get("author") or row[0] or "")
        messages.append(
            {
                "sender": sender,
                "timestamp": (
                    row[3].isoformat() if hasattr(row[3], "isoformat") else str(row[3] or "")
                ),
                "content": str(row[1] or ""),
            }
        )
    return {
        "game": {
            "game_id": str(game_row[0] or ""),
            "user_id": str(game_row[1] or ""),
            "username": str(game_row[2] or ""),
            "title": str(game_row[3] or "Partida"),
            "display_name": _game_display_name(game_row[3], game_row[5]),
            "status": str(game_row[4] or "unknown"),
            "created_at": (
                game_row[5].isoformat()
                if hasattr(game_row[5], "isoformat")
                else str(game_row[5] or "")
            ),
            "turns": _safe_int(game_row[6]),
        },
        "tokens": {
            "input": _safe_int(telemetry_row[0] if telemetry_row else 0),
            "output": _safe_int(telemetry_row[1] if telemetry_row else 0),
            "total": _safe_int(telemetry_row[2] if telemetry_row else 0),
        },
        "cost": {
            "input": _safe_float(telemetry_row[3] if telemetry_row else 0.0),
            "output": _safe_float(telemetry_row[4] if telemetry_row else 0.0),
            "total": _safe_float(telemetry_row[5] if telemetry_row else 0.0),
        },
        "agents": [
            {
                "agent_name": str(row[0] or "unknown"),
                "agent_type": str(row[1] or "unknown"),
                "input_tokens": _safe_int(row[2]),
                "output_tokens": _safe_int(row[3]),
                "total_tokens": _safe_int(row[4]),
                "cost_input": _safe_float(row[5]),
                "cost_output": _safe_float(row[6]),
                "cost_total": _safe_float(row[7]),
                "min_duration_ms": _safe_int(row[8]),
                "max_duration_ms": _safe_int(row[9]),
                "avg_duration_ms": _safe_int(row[10]),
                "calls": _safe_int(row[11]),
            }
            for row in agent_rows
            if str(row[0] or "").strip()
        ],
        "messages": messages,
    }

app = FastAPI(title="Agora Telemetry", version="2.0.0")


@app.on_event("startup")
def _startup() -> None:
    _init_db()


STATIC_DIR = Path(__file__).resolve().parent / "static"
if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def dashboard() -> FileResponse:
    page = STATIC_DIR / "index.html"
    if not page.is_file():
        raise HTTPException(status_code=404, detail="Dashboard not found")
    return FileResponse(page)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/events")
def ingest_events(
    payload: TelemetryBatchIn,
    x_agora_ingest_key: str | None = Header(default=None),
) -> dict[str, int]:
    _ingest_auth(x_agora_ingest_key)
    events = payload.events[:MAX_BATCH_SIZE]
    if not events:
        return {"accepted": 0}
    with _sqlite_cursor() as cur:
        for ev in events:
            normalized_ts = _normalize_timestamp(ev.timestamp)
            event_type = (ev.event_type or "llm_call").strip().lower()
            if event_type == "llm_call":
                cur.execute(
                    """
                    INSERT INTO llm_calls (
                        timestamp, flow, interaction_id, user_id, game_id, turn, agent_name, agent_type, agent_step,
                        provider, model, generation_name, duration_ms, status, status_message, stream,
                        usage_input_tokens, usage_output_tokens, usage_total_tokens,
                        cost_input, cost_output, cost_total, output_chars
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        normalized_ts,
                        ev.flow[:120],
                        ev.interaction_id[:150],
                        ev.user_id[:150],
                        ev.game_id[:150],
                        max(0, int(ev.turn)),
                        ev.agent_name[:120],
                        _normalize_agent_type_value(ev.agent_name[:120], ev.agent_type[:80]),
                        ev.agent_step[:120],
                        ev.provider[:80],
                        ev.model[:120],
                        ev.generation_name[:120],
                        max(0, int(ev.duration_ms)),
                        "error" if ev.status == "error" else "ok",
                        ev.status_message[:500],
                        1 if ev.stream else 0,
                        max(0, int(ev.usage_input_tokens)),
                        max(0, int(ev.usage_output_tokens)),
                        max(0, int(ev.usage_total_tokens)),
                        max(0.0, float(ev.cost_input)),
                        max(0.0, float(ev.cost_output)),
                        max(0.0, float(ev.cost_total)),
                        max(0, int(ev.output_chars)),
                    ),
                )
                continue
            if event_type in {"user_login", "user_access"}:
                cur.execute(
                    """
                    INSERT INTO user_access_events (
                        timestamp, event_type, user_id, username, status, status_message
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        normalized_ts,
                        event_type,
                        ev.user_id[:150],
                        ev.username[:120],
                        (ev.status or "ok")[:40],
                        ev.status_message[:500],
                    ),
                )
                continue
            if event_type == "link_interaction":
                if ev.interaction_id and ev.game_id:
                    cur.execute(
                        """
                        UPDATE llm_calls
                        SET game_id = ?
                        WHERE interaction_id = ?
                          AND TRIM(game_id) = ''
                        """,
                        (
                            ev.game_id[:150],
                            ev.interaction_id[:150],
                        ),
                    )
    return {"accepted": len(events)}


@app.get("/v1/options/users")
def options_users() -> dict[str, Any]:
    rows = _user_directory()
    return {
        "items": [
            {
                "user_id": row["id"],
                "username": row["username"],
                "created_at": row["created_at"],
                "label": row["username"],
            }
            for row in rows
        ]
    }


@app.get("/v1/options/games")
def options_games(user_id: str | None = Query(default=None)) -> dict[str, Any]:
    params: list[Any] = []
    where = ""
    if user_id:
        where = "WHERE g.user_id = %s"
        params.append(user_id)
    rows = _app_fetchall(
        f"""
        SELECT g.id::text, g.title, g.created_at, g.status, u.username
        FROM games g
        JOIN users u ON u.id = g.user_id
        {where}
        ORDER BY g.updated_at DESC, g.created_at DESC
        """,
        params,
    )
    return {
        "items": [
            {
                "game_id": str(row[0] or ""),
                "title": str(row[1] or "Partida"),
                "created_at": (
                    row[2].isoformat() if hasattr(row[2], "isoformat") else str(row[2] or "")
                ),
                "status": str(row[3] or "unknown"),
                "username": str(row[4] or ""),
                "label": _game_display_name(row[1], row[2]),
            }
            for row in rows
        ]
    }


@app.get("/v1/analytics/general")
def analytics_general() -> dict[str, Any]:
    return _general_metrics()


@app.get("/v1/analytics/agents")
def analytics_agents() -> dict[str, Any]:
    return _agent_metrics()


@app.get("/v1/analytics/user-detail")
def analytics_user_detail(user_id: str | None = Query(default=None)) -> dict[str, Any]:
    return _user_detail(user_id)


@app.get("/v1/analytics/game-detail")
def analytics_game_detail(game_id: str = Query(..., min_length=1)) -> dict[str, Any]:
    return _game_detail(game_id)

@app.get("/v1/metrics/summary")
def metrics_summary(
    user_id: str | None = Query(default=None),
    game_id: str | None = Query(default=None),
) -> dict[str, Any]:
    user_keys = _user_keys(user_id) if user_id else []
    where, params = _llm_where(user_keys=user_keys, game_id=game_id, require_game=True)
    row = _sqlite_fetchone(
        f"""
        SELECT
            COUNT(*) AS calls,
            COALESCE(SUM(duration_ms), 0) AS duration_ms,
            COALESCE(SUM(usage_input_tokens), 0) AS input_tokens,
            COALESCE(SUM(usage_output_tokens), 0) AS output_tokens,
            COALESCE(SUM(usage_total_tokens), 0) AS total_tokens,
            COALESCE(SUM(cost_total), 0.0) AS total_cost,
            COALESCE(SUM(CASE WHEN status='error' THEN 1 ELSE 0 END), 0) AS errors
        FROM llm_calls
        {where}
        """,
        params,
    )
    calls = _safe_int(row[0] if row else 0)
    duration_ms = _safe_int(row[1] if row else 0)
    return {
        "calls": calls,
        "duration_ms": duration_ms,
        "avg_duration_ms": int(duration_ms / calls) if calls else 0,
        "input_tokens": _safe_int(row[2] if row else 0),
        "output_tokens": _safe_int(row[3] if row else 0),
        "total_tokens": _safe_int(row[4] if row else 0),
        "total_cost": _safe_float(row[5] if row else 0.0),
        "errors": _safe_int(row[6] if row else 0),
    }


@app.get("/v1/metrics/by-game")
def metrics_by_game(
    user_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
) -> dict[str, Any]:
    user_keys = _user_keys(user_id) if user_id else []
    where, params = _llm_where(user_keys=user_keys, require_game=True)
    rows = _sqlite_fetchall(
        f"""
        SELECT
            game_id,
            COUNT(*) AS calls,
            COALESCE(SUM(duration_ms), 0) AS duration_ms,
            COALESCE(SUM(usage_total_tokens), 0) AS total_tokens,
            COALESCE(SUM(cost_total), 0.0) AS total_cost
        FROM llm_calls
        {where}
        GROUP BY game_id
        ORDER BY duration_ms DESC
        LIMIT ?
        """,
        [*params, limit],
    )
    return {
        "items": [
            {
                "game_id": str(row[0] or ""),
                "calls": _safe_int(row[1]),
                "duration_ms": _safe_int(row[2]),
                "total_tokens": _safe_int(row[3]),
                "total_cost": _safe_float(row[4]),
            }
            for row in rows
            if str(row[0] or "").strip()
        ]
    }


@app.get("/v1/metrics/by-agent")
def metrics_by_agent(
    user_id: str | None = Query(default=None),
    game_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
) -> dict[str, Any]:
    user_keys = _user_keys(user_id) if user_id else []
    where, params = _llm_where(user_keys=user_keys, game_id=game_id, require_game=True)
    rows = _sqlite_fetchall(
        f"""
        SELECT
            agent_name,
            CASE
                WHEN TRIM(agent_type) <> '' THEN agent_type
                WHEN agent_name = 'Observer' THEN 'observer'
                WHEN agent_name = 'Guionista' THEN 'guionista'
                ELSE 'unknown'
            END AS normalized_agent_type,
            COUNT(*) AS calls,
            COALESCE(SUM(duration_ms), 0) AS duration_ms,
            COALESCE(SUM(usage_total_tokens), 0) AS total_tokens,
            COALESCE(SUM(cost_total), 0.0) AS total_cost
        FROM llm_calls
        {where}
        GROUP BY agent_name, normalized_agent_type
        ORDER BY duration_ms DESC
        LIMIT ?
        """,
        [*params, limit],
    )
    return {
        "items": [
            {
                "agent_name": str(row[0] or "unknown"),
                "agent_type": str(row[1] or "unknown"),
                "calls": _safe_int(row[2]),
                "duration_ms": _safe_int(row[3]),
                "total_tokens": _safe_int(row[4]),
                "total_cost": _safe_float(row[5]),
            }
            for row in rows
        ]
    }


@app.get("/v1/metrics/by-turn")
def metrics_by_turn(
    game_id: str = Query(..., min_length=1),
    limit: int = Query(default=200, ge=1, le=1000),
) -> dict[str, Any]:
    rows = _sqlite_fetchall(
        """
        SELECT
            turn,
            COUNT(*) AS calls,
            COALESCE(SUM(duration_ms), 0) AS duration_ms,
            COALESCE(SUM(usage_total_tokens), 0) AS total_tokens,
            COALESCE(SUM(cost_total), 0.0) AS total_cost
        FROM llm_calls
        WHERE game_id = ?
        GROUP BY turn
        ORDER BY turn ASC
        LIMIT ?
        """,
        [game_id, limit],
    )
    return {
        "items": [
            {
                "turn": _safe_int(row[0]),
                "calls": _safe_int(row[1]),
                "duration_ms": _safe_int(row[2]),
                "total_tokens": _safe_int(row[3]),
                "total_cost": _safe_float(row[4]),
            }
            for row in rows
        ]
    }
