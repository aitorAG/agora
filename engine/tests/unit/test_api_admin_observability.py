"""Tests para la integración admin de observabilidad en Agora."""

from fastapi.testclient import TestClient

from src.api import observability_routes
from src.api.app import app
from src.api.schemas import AuthUserResponse


def test_admin_observability_page_requires_auth(monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    app.dependency_overrides.clear()
    client = TestClient(app)

    response = client.get("/admin/observability/")

    assert response.status_code == 401


def test_admin_observability_page_renders_for_admin():
    app.dependency_overrides[observability_routes.require_admin] = lambda: AuthUserResponse(
        id="u-admin",
        username="admin",
        is_active=True,
        role="admin",
    )
    client = TestClient(app)
    try:
        response = client.get("/admin/observability/")
        assert response.status_code == 200
        assert "Metricas operativas de Agora" in response.text
        assert 'class="topbar"' in response.text
        assert 'id="navAgora"' not in response.text
        assert 'id="backToAgora"' not in response.text
    finally:
        app.dependency_overrides.clear()


def test_admin_observability_proxy_uses_engine_auth(monkeypatch):
    app.dependency_overrides[observability_routes.require_admin] = lambda: AuthUserResponse(
        id="u-admin",
        username="admin",
        is_active=True,
        role="admin",
    )
    monkeypatch.setattr(
        observability_routes,
        "fetch_observability_bytes",
        lambda path, query_items: (
            200,
            b'{"ok":true,"path":"%s","query_count":%d}' % (
                path.encode("utf-8"),
                len(query_items),
            ),
            "application/json",
        ),
    )
    client = TestClient(app)
    try:
        response = client.get("/admin/observability/api/v1/analytics/general?user_id=u1")
        assert response.status_code == 200
        assert response.json() == {"ok": True, "path": "v1/analytics/general", "query_count": 1}
    finally:
        app.dependency_overrides.clear()
