"""Agentes del sistema conversacional."""

from .base import Agent
from .character import CharacterAgent
from .observer import ObserverAgent
from .guionista import GuionistaAgent

__all__ = ["Agent", "CharacterAgent", "ObserverAgent", "GuionistaAgent"]
