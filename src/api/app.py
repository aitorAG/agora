"""Aplicación FastAPI: motor de partida vía HTTP."""

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from .routes import router
from .schemas import HealthResponse

app = FastAPI(
    title="Agora API",
    description="API del motor narrativo conversacional",
    version="0.1.0",
)
app.include_router(router)


@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok")


# UI de prueba solo si UI_TEST=true
if os.getenv("UI_TEST", "").strip().lower() in ("true", "1", "yes"):
    _static_dir = Path(__file__).resolve().parent / "static"
    if _static_dir.is_dir():
        @app.get("/")
        def _redirect_root_to_ui():
            return RedirectResponse(url="/ui/", status_code=302)

        @app.get("/ui")
        def _redirect_ui_to_ui_slash():
            return RedirectResponse(url="/ui/", status_code=302)

        app.mount("/ui", StaticFiles(directory=_static_dir, html=True), name="ui")
