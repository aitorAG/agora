"""Tests de autenticación API."""

from fastapi.testclient import TestClient

from src.api import dependencies as dependencies_module
from src.api import routes as routes_module
from src.api.app import app


def test_auth_login_me_logout(monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    monkeypatch.setattr(routes_module, "get_persistence_provider", lambda: None)
    monkeypatch.setattr(routes_module, "ensure_seed_user", lambda: None)
    monkeypatch.setattr(
        routes_module,
        "authenticate_user",
        lambda username, password: (
            {"id": "u1", "username": "alice", "is_active": True, "role": "admin"}
            if username == "alice" and password == "secret123"
            else None
        ),
    )
    monkeypatch.setattr(
        dependencies_module,
        "get_user_by_username",
        lambda username: {"id": "u1", "username": username, "is_active": True, "password_hash": "x", "role": "admin"},
    )

    client = TestClient(app)
    bad = client.post("/auth/login", json={"username": "alice", "password": "wrong"})
    assert bad.status_code == 401

    ok = client.post("/auth/login", json={"username": "alice", "password": "secret123"})
    assert ok.status_code == 200
    assert ok.json()["user"]["username"] == "alice"

    me = client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["username"] == "alice"
    assert me.json()["role"] == "admin"

    out = client.post("/auth/logout")
    assert out.status_code == 200
    assert out.json()["ok"] is True

    me_after = client.get("/auth/me")
    assert me_after.status_code == 401


def test_auth_register_success_and_login(monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    monkeypatch.setattr(routes_module, "get_persistence_provider", lambda: None)
    monkeypatch.setattr(
        routes_module,
        "create_user",
        lambda username, _password: {
            "id": "u2",
            "username": username.strip().lower(),
            "is_active": True,
            "role": "user",
        },
    )
    monkeypatch.setattr(
        routes_module,
        "authenticate_user",
        lambda username, password: (
            {"id": "u2", "username": username.strip().lower(), "is_active": True, "role": "user"}
            if password == "supersecret"
            else None
        ),
    )
    monkeypatch.setattr(
        dependencies_module,
        "get_user_by_username",
        lambda username: {"id": "u2", "username": username.strip().lower(), "is_active": True, "password_hash": "x", "role": "user"},
    )

    client = TestClient(app)
    reg = client.post("/auth/register", json={"username": "Bob", "password": "supersecret"})
    assert reg.status_code == 201
    assert reg.json()["authenticated"] is True
    assert reg.json()["user"]["username"] == "bob"

    me = client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["username"] == "bob"
    assert me.json()["role"] == "user"

    out = client.post("/auth/logout")
    assert out.status_code == 200

    login = client.post("/auth/login", json={"username": "bob", "password": "supersecret"})
    assert login.status_code == 200
    assert login.json()["user"]["username"] == "bob"


def test_auth_register_duplicate_returns_409(monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    monkeypatch.setattr(routes_module, "get_persistence_provider", lambda: None)
    monkeypatch.setattr(
        routes_module,
        "create_user",
        lambda _username, _password: (_ for _ in ()).throw(routes_module.UserAlreadyExistsError()),
    )
    client = TestClient(app)
    second = client.post("/auth/register", json={"username": "ALICE", "password": "another123"})
    assert second.status_code == 409
    assert second.json()["detail"] == "Username already exists"


def test_authz_admin_requires_admin_role(monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    monkeypatch.setattr(routes_module, "get_persistence_provider", lambda: None)
    monkeypatch.setattr(routes_module, "ensure_seed_user", lambda: None)

    monkeypatch.setattr(
        routes_module,
        "authenticate_user",
        lambda username, password: (
            {"id": "u3", "username": username, "is_active": True, "role": "user"}
            if username == "user1" and password == "secret123"
            else {"id": "u4", "username": username, "is_active": True, "role": "admin"}
            if username == "admin1" and password == "secret123"
            else None
        ),
    )

    monkeypatch.setattr(
        dependencies_module,
        "get_user_by_username",
        lambda username: {
            "id": "u4" if username == "admin1" else "u3",
            "username": username,
            "is_active": True,
            "password_hash": "x",
            "role": "admin" if username == "admin1" else "user",
        },
    )

    client = TestClient(app)

    unauthorized = client.get("/authz/admin")
    assert unauthorized.status_code == 401

    login_user = client.post("/auth/login", json={"username": "user1", "password": "secret123"})
    assert login_user.status_code == 200
    forbidden = client.get("/authz/admin")
    assert forbidden.status_code == 403

    client.post("/auth/logout")
    login_admin = client.post("/auth/login", json={"username": "admin1", "password": "secret123"})
    assert login_admin.status_code == 200
    ok = client.get("/authz/admin")
    assert ok.status_code == 200
    assert ok.json()["authorized"] is True
