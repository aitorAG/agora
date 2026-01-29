"""CharacterAgent - Agente actor que participa en la conversación."""

from typing import Dict, Any
from langchain_deepseek import ChatDeepSeek
from langchain_core.messages import HumanMessage, SystemMessage
from ..state import ConversationState
from .base import Agent


class CharacterAgent(Agent):
    """Agente que representa un personaje en la conversación."""
    
    def __init__(self, name: str, personality: str, model: str = "deepseek-chat"):
        """Inicializa el CharacterAgent.
        
        Args:
            name: Nombre del personaje
            personality: Descripción de la personalidad
            model: Modelo de DeepSeek a usar
        """
        super().__init__(name)
        self._personality = personality
        self._llm = ChatDeepSeek(model=model, temperature=0.8)
    
    @property
    def is_actor(self) -> bool:
        """CharacterAgent es un actor."""
        return True
    
    @property
    def personality(self) -> str:
        """Personalidad del personaje."""
        return self._personality
    
    def process(self, state: ConversationState) -> Dict[str, Any]:
        """Genera una respuesta basada en el historial visible.
        
        Args:
            state: Estado actual de la conversación
            
        Returns:
            Diccionario con 'message' (contenido del mensaje) o 'error'
        """
        try:
            # Construir historial de mensajes para el LLM
            messages = []
            
            # Mensaje del sistema con personalidad
            system_prompt = f"""Eres {self.name}, un personaje en una conversación grupal.
Tu personalidad: {self.personality}

Responde de manera natural y coherente con tu personalidad. 
Mantén tus respuestas concisas (1-3 frases típicamente).
Solo responde con el contenido del mensaje, sin prefijos ni explicaciones."""
            
            messages.append(SystemMessage(content=system_prompt))
            
            # Añadir historial visible
            for msg in state["messages"]:
                messages.append(
                    HumanMessage(content=f"[{msg['author']}] {msg['content']}")
                )
            
            # Generar respuesta
            response = self._llm.invoke(messages)
            content = response.content.strip()
            
            return {
                "message": content,
                "author": self.name
            }
            
        except Exception as e:
            return {
                "error": str(e),
                "author": self.name
            }
