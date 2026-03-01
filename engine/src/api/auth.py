"""Utilidades de autenticación (hash de password, JWT y store de usuarios)."""

from __future__ import annotations

import importlib
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

_PWD_CONTEXT = CryptContext(schemes=["bcrypt_sha256"], deprecated="auto")


class UserAlreadyExistsError(Exception):
    """Error de dominio para username duplicado."""


def normalize_username(username: str) -> str:
    return (username or "").strip().lower()


def normalize_role(role: str | None) -> str:
    value = (role or "user").strip().lower()
    return "admin" if value == "admin" else "user"


def auth_cookie_name() -> str:
    return os.getenv("AUTH_COOKIE_NAME", "agora_auth_token").strip() or "agora_auth_token"


def auth_required() -> bool:
    raw = os.getenv("AUTH_REQUIRED", "true").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _auth_secret() -> str:
    return os.getenv("AUTH_SECRET_KEY", "dev-only-change-me").strip() or "dev-only-change-me"


def _auth_algorithm() -> str:
    return os.getenv("AUTH_ALGORITHM", "HS256").strip() or "HS256"


def _auth_exp_minutes() -> int:
    raw = os.getenv("AUTH_TOKEN_EXPIRE_MINUTES", "480").strip()
    try:
        value = int(raw)
    except ValueError:
        value = 480
    return max(5, value)


def hash_password(password: str) -> str:
    return _PWD_CONTEXT.hash(password or "")


def verify_password(password: str, password_hash: str) -> bool:
    if not password_hash:
        return False
    try:
        return _PWD_CONTEXT.verify(password or "", password_hash)
    except Exception:
        return False


def create_access_token(username: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": username,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=_auth_exp_minutes())).timestamp()),
    }
    return jwt.encode(payload, _auth_secret(), algorithm=_auth_algorithm())


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, _auth_secret(), algorithms=[_auth_algorithm()])


def _db_dsn() -> str:
    dsn = os.getenv("DATABASE_URL", "").strip()
    if not dsn:
        raise RuntimeError("DATABASE_URL is required for DB-only auth")
    return dsn


def _db_connect():
    psycopg = importlib.import_module("psycopg")
    return psycopg.connect(_db_dsn(), autocommit=False)


def ensure_seed_user() -> None:
    username = normalize_username(os.getenv("AUTH_SEED_USERNAME", "usuario")) or "usuario"
    password = os.getenv("AUTH_SEED_PASSWORD", "agora123").strip() or "agora123"
    role = normalize_role(os.getenv("AUTH_SEED_ROLE", "admin"))
    pwd_hash = hash_password(password)
    with _db_connect() as conn:
        with conn.cursor() as cur:
            user_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO users (id, username, created_at, password_hash, is_active, role)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (username) DO UPDATE
                SET password_hash = CASE
                    WHEN users.password_hash IS NULL OR users.password_hash = '' THEN EXCLUDED.password_hash
                    ELSE users.password_hash
                END,
                    role = EXCLUDED.role
                """,
                (user_id, username, datetime.now(timezone.utc), pwd_hash, True, role),
            )
        conn.commit()


def get_user_by_username(username: str) -> dict[str, Any] | None:
    normalized = normalize_username(username)
    if not normalized:
        return None
    with _db_connect() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """
                    SELECT id::text, username, password_hash, is_active, role
                    FROM users
                    WHERE LOWER(username) = %s
                    """,
                    (normalized,),
                )
            except Exception as exc:
                sqlstate = getattr(exc, "sqlstate", None) or getattr(exc, "pgcode", None)
                if sqlstate != "42703":
                    raise
                cur.execute(
                    """
                    SELECT id::text, username, password_hash, is_active
                    FROM users
                    WHERE LOWER(username) = %s
                    """,
                    (normalized,),
                )
            row = cur.fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "username": row[1],
        "password_hash": row[2] or "",
        "is_active": bool(row[3]) if row[3] is not None else True,
        "role": normalize_role(row[4] if len(row) > 4 else "user"),
    }


def create_user(username: str, password: str) -> dict[str, Any]:
    normalized = normalize_username(username)
    if not normalized:
        raise ValueError("Username is required")
    if len(password or "") < 6:
        raise ValueError("Password must be at least 6 characters")

    if get_user_by_username(normalized):
        raise UserAlreadyExistsError("Username already exists")

    pwd_hash = hash_password(password)

    try:
        with _db_connect() as conn:
            with conn.cursor() as cur:
                user_id = str(uuid.uuid4())
                cur.execute(
                    """
                    INSERT INTO users (id, username, created_at, password_hash, is_active, role)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (user_id, normalized, datetime.now(timezone.utc), pwd_hash, True, "user"),
                )
            conn.commit()
    except Exception as exc:
        sqlstate = getattr(exc, "sqlstate", None) or getattr(exc, "pgcode", None)
        if sqlstate == "23505":
            raise UserAlreadyExistsError("Username already exists") from exc
        raise
    return {
        "id": user_id,
        "username": normalized,
        "password_hash": pwd_hash,
        "is_active": True,
        "role": "user",
    }


def authenticate_user(username: str, password: str) -> dict[str, Any] | None:
    user = get_user_by_username(username)
    if not user:
        return None
    if not user.get("is_active", True):
        return None
    if not verify_password(password, str(user.get("password_hash", ""))):
        return None
    return user


def username_from_token(token: str) -> str | None:
    if not token:
        return None
    try:
        payload = decode_access_token(token)
    except JWTError:
        return None
    username = payload.get("sub")
    return str(username) if isinstance(username, str) and username else None
