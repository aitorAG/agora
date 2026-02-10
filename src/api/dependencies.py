"""Dependencias FastAPI: motor de partida singleton."""

from src.core import create_engine

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine()
    return _engine
