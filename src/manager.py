"""ConversationManager - Orquestador del estado conversacional."""

from datetime import datetime
from typing import List, Dict, Any
from .state import ConversationState, Message


class ConversationManager:
    """Gestiona el estado de conversación y proporciona acceso controlado."""
    
    def __init__(self):
        """Inicializa el manager con estado vacío."""
        self._state: ConversationState = {
            "messages": [],
            "turn": 0,
            "metadata": {}
        }
    
    @property
    def state(self) -> ConversationState:
        """Retorna el estado completo."""
        return self._state
    
    def add_message(self, author: str, content: str) -> None:
        """Añade un mensaje al estado.
        
        Args:
            author: Nombre del agente/autor
            content: Contenido del mensaje
        """
        message: Message = {
            "author": author,
            "content": content,
            "timestamp": datetime.now(),
            "turn": self._state["turn"]
        }
        self._state["messages"].append(message)
    
    def get_visible_history(self) -> List[Message]:
        """Retorna el historial visible para agentes actores.
        
        Por ahora, retorna todos los mensajes. En el futuro se puede
        filtrar para ocultar ciertos mensajes o metadata.
        
        Returns:
            Lista de mensajes visibles
        """
        return self._state["messages"].copy()
    
    def get_full_history(self) -> List[Message]:
        """Retorna el historial completo para observadores.
        
        Returns:
            Lista completa de mensajes
        """
        return self._state["messages"].copy()
    
    def increment_turn(self) -> None:
        """Incrementa el contador de turnos."""
        self._state["turn"] += 1
    
    def update_metadata(self, key: str, value: Any) -> None:
        """Actualiza un valor en metadata.
        
        Args:
            key: Clave en metadata
            value: Valor a almacenar
        """
        self._state["metadata"][key] = value
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Obtiene un valor de metadata.
        
        Args:
            key: Clave en metadata
            default: Valor por defecto si no existe
            
        Returns:
            Valor almacenado o default
        """
        return self._state["metadata"].get(key, default)
