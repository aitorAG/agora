"""Aplicación FastAPI: motor de partida vía HTTP."""

from fastapi import FastAPI

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
