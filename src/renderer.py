"""Renderer - Renderizado de mensajes en terminal."""

from typing import List
from .state import Message


def render_message(message: Message) -> None:
    """Renderiza un mensaje en terminal.
    
    Formato: [NOMBRE_AGENTE] texto del mensaje
    
    Args:
        message: Mensaje a renderizar
    """
    print(f"[{message['author']}] {message['content']}")


def render_messages(messages: List[Message]) -> None:
    """Renderiza una lista de mensajes.
    
    Args:
        messages: Lista de mensajes a renderizar
    """
    for message in messages:
        render_message(message)
