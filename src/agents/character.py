"""CharacterAgent - Agente actor que participa en la conversación."""

from typing import Dict, Any
import os

from ..state import ConversationState
from .base import Agent
from .deepseek_adapter import send_message


class CharacterAgent(Agent):
    """Agente que representa un personaje en la conversación."""

    def __init__(
        self,
        name: str,
        personality: str,
        mission: str | None = None,
        background: str | None = None,
        model: str = "deepseek-chat",
    ):
        """Inicializa el CharacterAgent.

        Args:
            name: Nombre del personaje
            personality: Descripción de la personalidad
            mission: Misión privada que el actor debe intentar alcanzar (opcional)
            background: Contexto del personaje (origen, gustos, profesión, etc.) coherente con la ambientación (opcional)
            model: Modelo de DeepSeek a usar
        """
        super().__init__(name)
        self._personality = personality
        self._mission = mission
        self._background = background
        # Permitir sobreescribir modelo/temperatura vía entorno
        self._model = os.getenv("DEEPSEEK_MODEL_CHARACTER", model)
        try:
            self._temperature = float(os.getenv("DEEPSEEK_TEMP_CHARACTER", "0.8"))
        except ValueError:
            self._temperature = 0.8

    @property
    def is_actor(self) -> bool:
        """CharacterAgent es un actor."""
        return True

    @property
    def personality(self) -> str:
        """Personalidad del personaje."""
        return self._personality

    @property
    def mission(self) -> str | None:
        """Misión privada del personaje (opcional)."""
        return self._mission

    @property
    def background(self) -> str | None:
        """Background del personaje (opcional)."""
        return self._background

    def process(self, state: ConversationState) -> Dict[str, Any]:
        """Genera una respuesta basada en el historial visible.

        Args:
            state: Estado actual de la conversación

        Returns:
            Diccionario con 'message' (contenido del mensaje) o 'error'
        """
        try:
            system_prompt = f"""Eres {self.name}, un personaje en una conversación grupal.
Tu personalidad: {self.personality}

Responde de manera natural y coherente con tu personalidad.
Mantén tus respuestas concisas (1-3 frases típicamente).
Solo responde con el contenido del mensaje, sin prefijos ni explicaciones."""
            if self._background:
                system_prompt += f"""

Tu background (contexto de tu personaje): {self._background}
Actúa de forma coherente con este contexto."""
            if self._mission:
                system_prompt += f"""

Tienes una misión secreta que debes intentar cumplir durante la conversación. No la reveles explícitamente.
Tu misión: {self._mission}"""

            # Limitar historial a los últimos N mensajes para reducir tokens
            max_history = int(os.getenv("CHAR_CONTEXT_MESSAGES", "20"))
            history = state["messages"][-max_history:]
            messages = [{"role": "system", "content": system_prompt}]
            for msg in history:
                messages.append({"role": "user", "content": f"[{msg['author']}] {msg['content']}"})

            content = send_message(
                messages, model=self._model, temperature=self._temperature, stream=False
            )
            assert isinstance(content, str)
            return {
                "message": content.strip(),
                "author": self.name,
            }
        except Exception as e:
            return {
                "error": str(e),
                "author": self.name,
            }
