"""Aplicación FastAPI: motor de partida vía HTTP."""

import os
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from ..observability import flush_langfuse
from .dependencies import get_persistence_provider
from .auth import ensure_seed_user
from .routes import router, auth_router, authz_router, admin_router
from .schemas import HealthResponse

_engine_root = Path(__file__).resolve().parents[2]
_repo_root = _engine_root.parent
_logger = logging.getLogger(__name__)
load_dotenv(_engine_root / ".env")
load_dotenv(_repo_root / ".env")


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    try:
        try:
            # Intenta bootstrap de esquema y usuario admin seed.
            get_persistence_provider()
            ensure_seed_user()
        except Exception as exc:
            _logger.warning("Startup auth bootstrap skipped: %s", exc)
        yield
    finally:
        flush_langfuse()


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


@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok")


# UI de prueba solo si UI_TEST=true
_ui_test_raw = os.getenv("UI_TEST", "")
_ui_enabled = _ui_test_raw.strip().lower() in ("true", "1", "yes")
_static_dir = _repo_root / "frontend" / "static"
if _ui_enabled:
    if _static_dir.is_dir():
        @app.get("/")
        def _redirect_root_to_ui():
            return RedirectResponse(url="/ui/", status_code=302)

        @app.get("/ui")
        def _redirect_ui_to_ui_slash():
            return RedirectResponse(url="/ui/", status_code=302)

        app.mount("/ui", StaticFiles(directory=_static_dir, html=True), name="ui")
