"""Tests de factory DB-only."""

from src.persistence import factory as persistence_factory


class _DummyDbProvider:
    pass


def test_factory_always_returns_db_provider(monkeypatch):
    monkeypatch.setenv("PERSISTENCE_MODE", "db")
    monkeypatch.setattr(persistence_factory, "DatabasePersistenceProvider", _DummyDbProvider)
    provider = persistence_factory.create_persistence_provider()
    assert isinstance(provider, _DummyDbProvider)


def test_factory_ignores_legacy_mode_env(monkeypatch):
    monkeypatch.setenv("PERSISTENCE_MODE", "json")
    monkeypatch.setattr(persistence_factory, "DatabasePersistenceProvider", _DummyDbProvider)
    provider = persistence_factory.create_persistence_provider()
    assert isinstance(provider, _DummyDbProvider)
