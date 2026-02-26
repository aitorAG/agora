"""Tests unitarios del cliente de observabilidad Langfuse."""

from types import SimpleNamespace

from src.observability import langfuse_client as lc


def test_get_langfuse_keeps_client_when_tracing_enabled_is_none(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    lc._langfuse_instance = None

    class DummyLangfuse:
        def __init__(self, host=None):
            self.host = host
            self.tracing_enabled = None

    monkeypatch.setitem(__import__("sys").modules, "langfuse", SimpleNamespace(Langfuse=DummyLangfuse))

    client = lc.get_langfuse()
    assert client is not None
    assert isinstance(client, DummyLangfuse)


def test_get_langfuse_uses_base_url_when_host_missing(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    monkeypatch.delenv("LANGFUSE_HOST", raising=False)
    monkeypatch.setenv("LANGFUSE_BASE_URL", "http://localhost:3000")
    lc._langfuse_instance = None

    class DummyLangfuse:
        def __init__(self, host=None):
            self.host = host
            self.tracing_enabled = True

    monkeypatch.setitem(__import__("sys").modules, "langfuse", SimpleNamespace(Langfuse=DummyLangfuse))

    client = lc.get_langfuse()
    assert client is not None
    assert client.host == "http://localhost:3000"


def test_flush_langfuse_calls_flush_if_available(monkeypatch):
    called = {"flush": 0}

    class DummyLangfuse:
        def flush(self):
            called["flush"] += 1

    monkeypatch.setattr(lc, "get_langfuse", lambda: DummyLangfuse())
    lc.flush_langfuse()
    assert called["flush"] == 1


def test_start_generation_inherits_agent_metadata_from_span(monkeypatch):
    captured = {}

    class DummySpan:
        def generation(self, **payload):
            captured.update(payload)
            return object()

        def end(self):
            return None

    class DummyLangfuse:
        def span(self, **_kwargs):
            return DummySpan()

    monkeypatch.setattr(lc, "get_langfuse", lambda: DummyLangfuse())
    with lc.span_agent("observer", metadata={"agent_name": "Observer", "agent_step": "analysis"}):
        _ = lc.start_generation(name="llm_call", metadata={"custom": "x"})

    meta = captured.get("metadata", {})
    assert meta.get("agent_name") == "Observer"
    assert meta.get("agent_step") == "analysis"
    assert meta.get("span_name") == "observer"
    assert meta.get("custom") == "x"
