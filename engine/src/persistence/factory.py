"""Factory de persistencia (DB-only)."""

from __future__ import annotations

from .db_provider import DatabasePersistenceProvider
from .provider import PersistenceProvider


def create_persistence_provider() -> PersistenceProvider:
    return DatabasePersistenceProvider()
