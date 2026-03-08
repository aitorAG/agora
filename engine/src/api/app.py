"""Aplicación FastAPI: motor de partida vía HTTP."""

import os
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from ..config import bootstrap_runtime_config
bootstrap_runtime_config()

from ..observability import flush_observability
from .dependencies import get_persistence_provider
from .auth import InvalidAuthConfigurationError, ensure_seed_user, validate_auth_configuration
from .observability_routes import router as observability_router
from .routes import router, auth_router, authz_router, admin_router
from .schemas import HealthResponse

_engine_root = Path(__file__).resolve().parents[2]
_repo_root = _engine_root.parent
_logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    try:
        try:
            validate_auth_configuration()
            # Intenta bootstrap de esquema y usuario admin seed.
            get_persistence_provider()
            ensure_seed_user()
        except Exception as exc:
            if isinstance(exc, InvalidAuthConfigurationError):
                raise
            _logger.warning("Startup auth bootstrap skipped: %s", exc)
        yield
    finally:
        flush_observability()


app = FastAPI(
    title="Agora API",
    description="API del motor narrativo conversacional",
    version="0.1.0",
    lifespan=_lifespan,
)
app.include_router(router)
app.include_router(auth_router)
app.include_router(authz_router)
app.include_router(admin_router)
app.include_router(observability_router)


@app.middleware("http")
async def apply_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if request.url.path.startswith("/auth/"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok")


# UI de prueba solo si UI_TEST=true
_ui_test_raw = os.getenv("UI_TEST", "")
_ui_enabled = _ui_test_raw.strip().lower() in ("true", "1", "yes")
_static_dir = _repo_root / "frontend" / "static"
_observability_static_dir = _repo_root / "observability_static"
if not _observability_static_dir.is_dir():
    _observability_static_dir = _repo_root / "observability-platform" / "telemetry-service" / "static"
if _observability_static_dir.is_dir():
    app.mount(
        "/ui/observability-static",
        StaticFiles(directory=_observability_static_dir),
        name="observability-static",
    )
if _ui_enabled:
    if _static_dir.is_dir():
        @app.get("/")
        def _redirect_root_to_ui():
            return RedirectResponse(url="/ui/", status_code=302)

        @app.get("/ui")
        def _redirect_ui_to_ui_slash():
            return RedirectResponse(url="/ui/", status_code=302)

        app.mount("/ui", StaticFiles(directory=_static_dir, html=True), name="ui")
