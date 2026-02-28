"""Core: motor headless de partida (sin I/O ni FastAPI)."""

from .engine import GameEngine, GameSession, create_engine

__all__ = ["GameEngine", "GameSession", "create_engine"]
