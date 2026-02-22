"""Tests de selección de modo en factory de persistencia."""

import pytest

from src.persistence import factory as persistence_factory


class _DummyJsonProvider:
    pass


class _DummyDbProvider:
    pass


def test_factory_selects_json_mode(monkeypatch):
    monkeypatch.setenv("PERSISTENCE_MODE", "json")
    monkeypatch.setattr(persistence_factory, "JsonPersistenceProvider", _DummyJsonProvider)
    provider = persistence_factory.create_persistence_provider()
    assert isinstance(provider, _DummyJsonProvider)


def test_factory_selects_db_mode(monkeypatch):
    monkeypatch.setenv("PERSISTENCE_MODE", "db")
    monkeypatch.setattr(persistence_factory, "DatabasePersistenceProvider", _DummyDbProvider)
    provider = persistence_factory.create_persistence_provider()
    assert isinstance(provider, _DummyDbProvider)


def test_factory_rejects_invalid_mode(monkeypatch):
    monkeypatch.setenv("PERSISTENCE_MODE", "otro")
    with pytest.raises(RuntimeError):
        persistence_factory.create_persistence_provider()
