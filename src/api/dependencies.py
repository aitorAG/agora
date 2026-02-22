"""Dependencias FastAPI: motor de partida singleton."""

from src.core import create_engine
from src.persistence import create_persistence_provider

_engine = None
_persistence = None


def get_persistence_provider():
    global _persistence
    if _persistence is None:
        _persistence = create_persistence_provider()
    return _persistence


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(persistence_provider=get_persistence_provider())
    return _engine
