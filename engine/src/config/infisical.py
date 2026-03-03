"""Infisical integration for runtime secret loading."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class InfisicalSettings:
    enabled: bool
    host: str
    client_id: str
    client_secret: str
    project_id: str
    environment: str
    secret_path: str
    include_imports: bool
    override_existing: bool
    timeout_seconds: float


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _build_settings() -> InfisicalSettings:
    return InfisicalSettings(
        enabled=_as_bool(os.getenv("INFISICAL_ENABLED"), default=False),
        host=(os.getenv("INFISICAL_HOST") or "https://eu.infisical.com").strip().rstrip("/"),
        client_id=(os.getenv("INFISICAL_CLIENT_ID") or "").strip(),
        client_secret=(os.getenv("INFISICAL_CLIENT_SECRET") or "").strip(),
        project_id=(os.getenv("INFISICAL_PROJECT_ID") or "").strip(),
        environment=(os.getenv("INFISICAL_ENV") or "prod").strip(),
        secret_path=(os.getenv("INFISICAL_SECRET_PATH") or "/").strip() or "/",
        include_imports=_as_bool(os.getenv("INFISICAL_INCLUDE_IMPORTS"), default=True),
        override_existing=_as_bool(os.getenv("INFISICAL_OVERRIDE_EXISTING"), default=False),
        timeout_seconds=max(0.5, float((os.getenv("INFISICAL_TIMEOUT_SECONDS") or "5").strip())),
    )


def _post_form(url: str, payload: dict[str, str], timeout_seconds: float) -> dict[str, Any]:
    body = urlencode(payload).encode("utf-8")
    req = Request(
        url=url,
        method="POST",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urlopen(req, timeout=timeout_seconds) as response:
        raw = response.read().decode("utf-8")
        if not raw:
            return {}
        return json.loads(raw)


def _get_json(url: str, token: str, timeout_seconds: float) -> dict[str, Any]:
    req = Request(
        url=url,
        method="GET",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    with urlopen(req, timeout=timeout_seconds) as response:
        raw = response.read().decode("utf-8")
        if not raw:
            return {}
        return json.loads(raw)


def _login(settings: InfisicalSettings) -> str:
    payload = {
        "clientId": settings.client_id,
        "clientSecret": settings.client_secret,
    }
    data = _post_form(
        f"{settings.host}/api/v1/auth/universal-auth/login",
        payload=payload,
        timeout_seconds=settings.timeout_seconds,
    )
    token = str(data.get("accessToken") or "").strip()
    if not token:
        raise RuntimeError("Infisical login did not return accessToken")
    return token


def _read_secret_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(payload.get("secrets"), list):
        return [item for item in payload["secrets"] if isinstance(item, dict)]
    data = payload.get("data")
    if isinstance(data, dict) and isinstance(data.get("secrets"), list):
        return [item for item in data["secrets"] if isinstance(item, dict)]
    return []


def fetch_secrets_from_infisical() -> dict[str, str]:
    settings = _build_settings()
    if not settings.enabled:
        return {}
    required = {
        "INFISICAL_CLIENT_ID": settings.client_id,
        "INFISICAL_CLIENT_SECRET": settings.client_secret,
        "INFISICAL_PROJECT_ID": settings.project_id,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise RuntimeError(f"Missing required Infisical config: {', '.join(missing)}")

    token = _login(settings)
    payload: dict[str, Any] = {}
    errors: list[str] = []
    for project_key in ("workspaceId", "projectSlug"):
        query = urlencode(
            {
                project_key: settings.project_id,
                "environment": settings.environment,
                "secretPath": settings.secret_path,
                "include_imports": str(settings.include_imports).lower(),
            }
        )
        try:
            payload = _get_json(
                f"{settings.host}/api/v3/secrets/raw?{query}",
                token=token,
                timeout_seconds=settings.timeout_seconds,
            )
            if _read_secret_items(payload):
                break
        except Exception as exc:
            errors.append(str(exc))
            continue

    parsed: dict[str, str] = {}
    for item in _read_secret_items(payload):
        key = str(item.get("secretKey") or "").strip()
        if not key:
            continue
        value = str(item.get("secretValue") or "")
        parsed[key] = value
    if not parsed and errors:
        raise RuntimeError("; ".join(errors))
    return parsed


def load_infisical_secrets_into_env() -> int:
    settings = _build_settings()
    if not settings.enabled:
        return 0

    try:
        secrets = fetch_secrets_from_infisical()
    except (HTTPError, URLError, TimeoutError, ValueError, RuntimeError) as exc:
        LOGGER.warning("Infisical secrets load skipped: %s", exc)
        return 0
    except Exception as exc:  # pragma: no cover
        LOGGER.warning("Infisical secrets load unexpected error: %s", exc)
        return 0

    applied = 0
    for key, value in secrets.items():
        if key in os.environ and not settings.override_existing:
            continue
        os.environ[key] = value
        applied += 1
    if applied:
        LOGGER.info("Infisical loaded %s secrets into runtime environment", applied)
    return applied
