"""Clase base para agentes."""

from abc import ABC, abstractmethod
from typing import Dict, Any
from ..state import ConversationState


class Agent(ABC):
    """Clase abstracta base para todos los agentes."""
    
    def __init__(self, name: str):
        """Inicializa el agente.
        
        Args:
            name: Nombre del agente
        """
        self._name = name
    
    @property
    def name(self) -> str:
        """Nombre del agente."""
        return self._name
    
    @property
    @abstractmethod
    def is_actor(self) -> bool:
        """Indica si el agente es actor (escribe mensajes) o observador."""
        pass
    
    @abstractmethod
    def process(self, state: ConversationState) -> Dict[str, Any]:
        """Procesa el estado y retorna resultado.
        
        Args:
            state: Estado actual de la conversación
            
        Returns:
            Diccionario con resultados del procesamiento
        """
        pass
