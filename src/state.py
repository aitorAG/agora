"""Estado de conversación para LangGraph."""

from typing import TypedDict, List, Dict, Any
from datetime import datetime


class Message(TypedDict):
    """Representa un mensaje en la conversación."""
    author: str
    content: str
    timestamp: datetime
    turn: int


class ConversationState(TypedDict):
    """Estado global de la conversación.
    
    Este es el estado que se pasa entre nodos del grafo LangGraph.
    """
    messages: List[Message]
    turn: int
    metadata: Dict[str, Any]
