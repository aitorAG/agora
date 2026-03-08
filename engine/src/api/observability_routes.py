"""Rutas admin integradas para observabilidad dentro de Agora."""

from __future__ import annotations

import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from fastapi import APIRouter, Depends, HTTPException, Request as FastAPIRequest, Response

from .dependencies import require_admin
from .schemas import AuthUserResponse

router = APIRouter(prefix="/admin/observability", tags=["admin-observability"])
_ALLOWED_PREFIXES = ("v1/options/", "v1/analytics/", "v1/metrics/")


def _telemetry_admin_base() -> str:
    explicit = (os.getenv("AGORA_TELEMETRY_ADMIN_BASE") or "").strip().rstrip("/")
    if explicit:
        return explicit

    endpoint = (os.getenv("TELEMETRY_ENDPOINT") or "").strip()
    if endpoint.endswith("/v1/events"):
        return endpoint[: -len("/v1/events")]

    parsed = urlsplit(endpoint)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"

    return "http://localhost:8081"


def _is_allowed_path(path: str) -> bool:
    normalized = path.strip().lstrip("/")
    return any(normalized.startswith(prefix) for prefix in _ALLOWED_PREFIXES)


def _proxy_timeout_seconds() -> float:
    raw = (os.getenv("AGORA_OBSERVABILITY_PROXY_TIMEOUT_SECONDS") or "8.0").strip()
    try:
        return max(0.5, float(raw))
    except ValueError:
        return 8.0


def fetch_observability_bytes(
    path: str,
    query_items: list[tuple[str, str]],
) -> tuple[int, bytes, str]:
    normalized = path.strip().lstrip("/")
    if not _is_allowed_path(normalized):
        raise HTTPException(status_code=404, detail="Observability resource not found")

    query_string = urlencode(query_items, doseq=True)
    url = f"{_telemetry_admin_base()}/{normalized}"
    if query_string:
        url = f"{url}?{query_string}"

    request = Request(url, method="GET")
    timeout = _proxy_timeout_seconds()
    try:
        with urlopen(request, timeout=timeout) as upstream:
            body = upstream.read()
            content_type = upstream.headers.get("Content-Type", "application/json")
            return int(getattr(upstream, "status", 200)), body, content_type
    except HTTPError as exc:
        body = exc.read() if hasattr(exc, "read") else str(exc).encode("utf-8")
        content_type = exc.headers.get("Content-Type", "text/plain") if exc.headers else "text/plain"
        return int(exc.code), body, content_type
    except URLError as exc:
        raise HTTPException(status_code=503, detail=f"Observability backend unavailable: {exc.reason}") from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail="Observability backend timeout") from exc


@router.get("/api/{telemetry_path:path}")
def observability_proxy(
    telemetry_path: str,
    request: FastAPIRequest,
    _current_user: AuthUserResponse = Depends(require_admin),
):
    status_code, body, content_type = fetch_observability_bytes(
        telemetry_path,
        list(request.query_params.multi_items()),
    )
    media_type = (content_type or "application/json").split(";", 1)[0].strip() or "application/json"
    return Response(content=body, status_code=status_code, media_type=media_type)
