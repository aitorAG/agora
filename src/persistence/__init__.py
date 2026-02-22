"""Capa de persistencia (json/db) para partidas."""

from .provider import PersistenceProvider
from .factory import create_persistence_provider

__all__ = ["PersistenceProvider", "create_persistence_provider"]
