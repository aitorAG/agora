"""Capacidades agenticas del Director (turno de palabra, futuras: evaluar misiones, cerrar partida, etc.)."""

from .turno_de_palabra import TurnoDePalabraAgent, normalize_who_should_respond

__all__ = ["TurnoDePalabraAgent", "normalize_who_should_respond"]
