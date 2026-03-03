from __future__ import annotations

import json

from src.config import infisical as ic


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_load_infisical_secrets_into_env(monkeypatch):
    monkeypatch.setenv("INFISICAL_ENABLED", "true")
    monkeypatch.setenv("INFISICAL_HOST", "https://eu.infisical.com")
    monkeypatch.setenv("INFISICAL_CLIENT_ID", "cid")
    monkeypatch.setenv("INFISICAL_CLIENT_SECRET", "csecret")
    monkeypatch.setenv("INFISICAL_PROJECT_ID", "pid")
    monkeypatch.setenv("INFISICAL_ENV", "prod")
    monkeypatch.delenv("MY_SECRET", raising=False)

    responses = [
        _FakeResponse({"accessToken": "token-1"}),
        _FakeResponse({"secrets": [{"secretKey": "MY_SECRET", "secretValue": "value-1"}]}),
    ]

    def fake_urlopen(_request, timeout=0):
        _ = timeout
        return responses.pop(0)

    monkeypatch.setattr(ic, "urlopen", fake_urlopen)
    applied = ic.load_infisical_secrets_into_env()
    assert applied == 1


def test_load_infisical_keeps_existing_env_by_default(monkeypatch):
    monkeypatch.setenv("INFISICAL_ENABLED", "true")
    monkeypatch.setenv("INFISICAL_CLIENT_ID", "cid")
    monkeypatch.setenv("INFISICAL_CLIENT_SECRET", "csecret")
    monkeypatch.setenv("INFISICAL_PROJECT_ID", "pid")
    monkeypatch.setenv("MY_SECRET", "local")

    responses = [
        _FakeResponse({"accessToken": "token-1"}),
        _FakeResponse({"secrets": [{"secretKey": "MY_SECRET", "secretValue": "remote"}]}),
    ]

    monkeypatch.setattr(ic, "urlopen", lambda req, timeout=0: responses.pop(0))
    applied = ic.load_infisical_secrets_into_env()
    assert applied == 0
