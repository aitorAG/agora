from __future__ import annotations

from src.config import runtime as rc


def test_bootstrap_runtime_config_loads_runtime_env_with_override(monkeypatch):
    calls: list[tuple[str, bool]] = []

    monkeypatch.setattr(rc, "_BOOTSTRAPPED", False)
    monkeypatch.setattr(
        rc,
        "load_dotenv",
        lambda path, override=False: calls.append((str(path), bool(override))),
    )
    monkeypatch.setattr(rc, "_apply_derived_defaults", lambda: None)

    rc.bootstrap_runtime_config()

    assert len(calls) == 3
    assert calls[0][1] is False
    assert calls[1][1] is False
    assert calls[-1][1] is True


def test_bootstrap_runtime_config_is_idempotent(monkeypatch):
    calls: list[tuple[str, bool]] = []

    monkeypatch.setattr(rc, "_BOOTSTRAPPED", False)
    monkeypatch.setattr(
        rc,
        "load_dotenv",
        lambda path, override=False: calls.append((str(path), bool(override))),
    )
    monkeypatch.setattr(rc, "_apply_derived_defaults", lambda: None)

    rc.bootstrap_runtime_config()
    rc.bootstrap_runtime_config()

    assert len(calls) == 3
