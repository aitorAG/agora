"""Factory de persistencia por variable de entorno."""

from __future__ import annotations

import os

from .db_provider import DatabasePersistenceProvider
from .json_provider import JsonPersistenceProvider
from .provider import PersistenceProvider


def create_persistence_provider() -> PersistenceProvider:
    mode = os.getenv("PERSISTENCE_MODE", "json").strip().lower() or "json"
    if mode == "db":
        return DatabasePersistenceProvider()
    if mode == "json":
        return JsonPersistenceProvider()
    raise RuntimeError(f"PERSISTENCE_MODE inválido: {mode!r}. Usa 'json' o 'db'.")
