"""Tests de autenticación API."""

import json

from fastapi.testclient import TestClient

from src.api.app import app


def test_auth_login_me_logout_json_mode(monkeypatch, tmp_path):
    monkeypatch.setenv("PERSISTENCE_MODE", "json")
    monkeypatch.setenv("AGORA_GAMES_DIR", str(tmp_path))
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    monkeypatch.setenv("AUTH_SEED_USERNAME", "alice")
    monkeypatch.setenv("AUTH_SEED_PASSWORD", "secret123")

    client = TestClient(app)

    bad = client.post("/auth/login", json={"username": "alice", "password": "wrong"})
    assert bad.status_code == 401

    ok = client.post("/auth/login", json={"username": "alice", "password": "secret123"})
    assert ok.status_code == 200
    assert ok.json()["user"]["username"] == "alice"

    me = client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["username"] == "alice"

    out = client.post("/auth/logout")
    assert out.status_code == 200
    assert out.json()["ok"] is True

    me_after = client.get("/auth/me")
    assert me_after.status_code == 401


def test_auth_register_success_and_login_json_mode(monkeypatch, tmp_path):
    monkeypatch.setenv("PERSISTENCE_MODE", "json")
    monkeypatch.setenv("AGORA_GAMES_DIR", str(tmp_path))
    monkeypatch.setenv("AUTH_REQUIRED", "true")

    client = TestClient(app)

    reg = client.post("/auth/register", json={"username": "Bob", "password": "supersecret"})
    assert reg.status_code == 201
    assert reg.json()["authenticated"] is True
    assert reg.json()["user"]["username"] == "bob"
    assert "set-cookie" in reg.headers

    me = client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["username"] == "bob"

    out = client.post("/auth/logout")
    assert out.status_code == 200

    login = client.post("/auth/login", json={"username": "bob", "password": "supersecret"})
    assert login.status_code == 200
    assert login.json()["user"]["username"] == "bob"

    users_file = tmp_path / "users.json"
    assert users_file.exists()
    data = json.loads(users_file.read_text(encoding="utf-8"))
    assert any(u.get("username") == "bob" for u in data)


def test_auth_register_duplicate_returns_409(monkeypatch, tmp_path):
    monkeypatch.setenv("PERSISTENCE_MODE", "json")
    monkeypatch.setenv("AGORA_GAMES_DIR", str(tmp_path))
    monkeypatch.setenv("AUTH_REQUIRED", "true")

    client = TestClient(app)

    first = client.post("/auth/register", json={"username": "alice", "password": "secret123"})
    assert first.status_code == 201
    second = client.post("/auth/register", json={"username": "ALICE", "password": "another123"})
    assert second.status_code == 409
    assert second.json()["detail"] == "Username already exists"
