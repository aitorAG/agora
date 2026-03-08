"""Tests unitarios para listado standard en API."""

from fastapi.testclient import TestClient

from src.api import routes as routes_module
from src.api.app import app
from src.api.schemas import AuthUserResponse


def test_standard_list_only_returns_active_templates(monkeypatch):
    app.dependency_overrides[routes_module.get_current_user] = lambda: AuthUserResponse(
        id="u1",
        username="usuario",
        is_active=True,
    )
    monkeypatch.setattr(
        routes_module,
        "list_standard_templates",
        lambda: [
            {
                "id": "t1",
                "titulo": "Plantilla 1",
                "descripcion_breve": "Descripcion",
                "version": "1.0.0",
                "num_personajes": 4,
                "active": True,
            },
            {
                "id": "t2",
                "titulo": "Plantilla 2",
                "descripcion_breve": "Oculta",
                "version": "1.0.0",
                "num_personajes": 2,
                "active": False,
            },
        ],
    )
    client = TestClient(app)
    try:
        res = client.get("/game/standard/list")
        assert res.status_code == 200
        body = res.json()
        assert [item["id"] for item in body["templates"]] == ["t1"]
        assert body["templates"][0]["active"] is True
    finally:
        app.dependency_overrides.clear()
