"""Tests de observabilidad/coste para DeepSeek adapter."""

from types import SimpleNamespace

from src.agents import deepseek_adapter as da


def test_send_message_non_stream_reports_usage_and_cost(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_INPUT_COST_PER_1M_TOKENS", "0.27")
    monkeypatch.setenv("DEEPSEEK_OUTPUT_COST_PER_1M_TOKENS", "1.10")

    calls = []

    def fake_end_generation(generation, **kwargs):
        calls.append((generation, kwargs))

    monkeypatch.setattr(da, "start_generation", lambda **kwargs: "gen-1")
    monkeypatch.setattr(da, "end_generation", fake_end_generation)

    usage = SimpleNamespace(prompt_tokens=1000, completion_tokens=500, total_tokens=1500)
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
        usage=usage,
    )

    class FakeCompletions:
        @staticmethod
        def create(**_kwargs):
            return response

    class FakeClient:
        chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr(da, "_get_client", lambda: FakeClient())

    out = da.send_message(
        [{"role": "user", "content": "hola"}],
        model="deepseek-chat",
        temperature=0.7,
        stream=False,
    )

    assert out == "ok"
    assert len(calls) == 1
    _, payload = calls[0]
    assert payload["usage_details"] == {"input": 1000, "output": 500, "total": 1500}
    assert payload["cost_details"]["total"] > 0.0


def test_send_message_stream_reports_usage_and_output(monkeypatch):
    calls = []

    def fake_end_generation(generation, **kwargs):
        calls.append((generation, kwargs))

    monkeypatch.setattr(da, "start_generation", lambda **kwargs: "gen-stream")
    monkeypatch.setattr(da, "end_generation", fake_end_generation)

    chunk1 = SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content="ho"))],
        usage=None,
    )
    chunk2 = SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content="la"))],
        usage=None,
    )
    chunk3 = SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content=None))],
        usage=SimpleNamespace(prompt_tokens=20, completion_tokens=10, total_tokens=30),
    )

    class FakeCompletions:
        @staticmethod
        def create(**_kwargs):
            return iter([chunk1, chunk2, chunk3])

    class FakeClient:
        chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr(da, "_get_client", lambda: FakeClient())

    out = "".join(
        da.send_message(
            [{"role": "user", "content": "hola"}],
            model="deepseek-chat",
            stream=True,
        )
    )

    assert out == "hola"
    assert len(calls) == 1
    _, payload = calls[0]
    assert payload["output"] == "hola"
    assert payload["usage_details"] == {"input": 20, "output": 10, "total": 30}
