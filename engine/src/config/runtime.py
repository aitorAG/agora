"""Centralized runtime bootstrap (dotenv + external secret providers)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from .infisical import load_infisical_secrets_into_env

_BOOTSTRAPPED = False


def _resolve_target() -> str:
    target = (os.getenv("AGORA_DEPLOY_TARGET") or "local").strip().lower()
    return "vps" if target == "vps" else "local"


def _resolve_runtime_context() -> str:
    context = (os.getenv("AGORA_RUNTIME_CONTEXT") or "").strip().lower()
    return context


def _resolve_public_base_url() -> str:
    target = _resolve_target()
    public_url = (os.getenv("AGORA_PUBLIC_URL") or "").strip().rstrip("/")
    if target == "vps" and public_url:
        return public_url

    legacy_vps = (os.getenv("AGORA_BASE_URL_VPS") or "").strip().rstrip("/")
    if target == "vps" and legacy_vps:
        return legacy_vps

    legacy_local = (os.getenv("AGORA_BASE_URL_LOCAL") or "").strip().rstrip("/")
    if target == "local" and legacy_local:
        return legacy_local

    return "http://localhost"


def _resolve_db_host() -> str:
    context = _resolve_runtime_context()
    if context == "docker":
        return "postgres"
    return (os.getenv("AGORA_POSTGRES_HOST") or "localhost").strip() or "localhost"


def _resolve_database_url() -> str:
    explicit = (os.getenv("DATABASE_URL") or "").strip()
    if explicit:
        return explicit

    db_name = (os.getenv("POSTGRES_DB") or "agora").strip() or "agora"
    db_user = (os.getenv("POSTGRES_USER") or "agora_user").strip() or "agora_user"
    db_password = (os.getenv("POSTGRES_PASSWORD") or "").strip()
    db_host = _resolve_db_host()
    return f"postgresql://{db_user}:{db_password}@{db_host}:5432/{db_name}"


def _resolve_telemetry_endpoint() -> str:
    explicit = (os.getenv("TELEMETRY_ENDPOINT") or "").strip()
    if explicit:
        return explicit
    context = _resolve_runtime_context()
    if context == "docker":
        return "http://telemetry:8081/v1/events"
    return "http://localhost:8081/v1/events"


def _apply_derived_defaults() -> None:
    resolved_base = _resolve_public_base_url()
    os.environ["AGORA_RESOLVED_BASE_URL"] = resolved_base
    os.environ["AGORA_OBSERVABILITY_URL"] = f"{resolved_base}/admin/observability"
    os.environ["DATABASE_URL"] = _resolve_database_url()
    os.environ["TELEMETRY_ENDPOINT"] = _resolve_telemetry_endpoint()


def bootstrap_runtime_config() -> None:
    global _BOOTSTRAPPED
    if _BOOTSTRAPPED:
        return

    engine_root = Path(__file__).resolve().parents[2]
    repo_root = engine_root.parent
    load_dotenv(engine_root / ".env")
    load_dotenv(repo_root / ".env")
    load_dotenv(repo_root / ".env.runtime")
    load_infisical_secrets_into_env()
    _apply_derived_defaults()
    _BOOTSTRAPPED = True
