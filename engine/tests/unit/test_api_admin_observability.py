"""Tests para la integración admin de observabilidad en Agora."""

from fastapi.testclient import TestClient

from src.api import observability_routes
from src.api import routes
from src.api.app import app
from src.api.schemas import AuthUserResponse


def test_admin_observability_page_requires_auth(monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    app.dependency_overrides.clear()
    client = TestClient(app)

    response = client.get("/admin/observability/")

    assert response.status_code == 401


def test_admin_observability_page_renders_for_admin():
    admin_override = lambda: AuthUserResponse(
        id="u-admin",
        username="admin",
        is_active=True,
        role="admin",
    )
    app.dependency_overrides[observability_routes.require_admin] = admin_override
    app.dependency_overrides[routes.require_admin] = admin_override
    client = TestClient(app)
    try:
        response = client.get("/admin/observability/")
        assert response.status_code == 200
        assert "Metricas operativas de Agora" in response.text
        assert 'id="agentDetailTable"' in response.text
        assert 'id="notaryLog"' in response.text
        assert '/ui/observability-static/styles.css?v=20260313h' in response.text
        assert '/ui/observability-static/app.js?v=20260313h' in response.text
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
