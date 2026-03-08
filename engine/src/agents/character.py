import os
import re
import sys
from typing import Dict, Any, Iterator

from ..state import ConversationState
from ..text_limits import truncate_agent_output
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
            self._temperature = float(os.getenv("DEEPSEEK_TEMP_CHARACTER", "2.0"))
        except ValueError:
            self._temperature = 2.0
        try:
            self._max_output_tokens = int(os.getenv("CHARACTER_MAX_OUTPUT_TOKENS", "120"))
        except ValueError:
            self._max_output_tokens = 120

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

    def process(
        self,
        state: ConversationState,
        stream: bool = False,
        stream_sink: Any = None,
        extra_system_instruction: str | None = None,
    ) -> Dict[str, Any]:
        """Genera una respuesta basada en el historial visible.

        Args:
            state: Estado actual de la conversación
            stream: Si True, emite la respuesta token a token (stdout o stream_sink).
            stream_sink: Si se pasa y stream=True, cada chunk se envía a stream_sink(str); si no, se usa stdout.

        Returns:
            Diccionario con 'message', 'author' y opcionalmente 'displayed' o 'error'.
        """
        try:
            messages = self._build_messages(
                state,
                extra_system_instruction=extra_system_instruction,
            )
            if not stream:
                content = send_message(
                    messages,
                    model=self._model,
                    temperature=self._temperature,
                    stream=False,
                    max_tokens=self._max_output_tokens,
                )
                assert isinstance(content, str)
                return {
                    "message": self._sanitize_response_content(content),
                    "author": self.name,
                }
            full_content = self._stream_response_to_stdout(messages, stream_sink=stream_sink)
            return {
                "message": self._sanitize_response_content(full_content),
                "author": self.name,
                "displayed": True,
            }
        except Exception as e:
            return {
                "error": str(e),
                "author": self.name,
            }

    def _build_messages(
        self,
        state: ConversationState,
        extra_system_instruction: str | None = None,
    ) -> list[dict[str, str]]:
        """Construye la lista de mensajes para el LLM (lógica de dominio)."""
        system_prompt = f"""Eres {self.name}, un personaje en una conversación grupal.
Tu personalidad: {self.personality}

Estas presente en la conversacion y responderas de manera natural y coherente con tu personalidad adressing un personaje presente en la escena, siguiendo la conversacion de los personajes y queriendo avanzar en tu objetivo
Mantén tus respuestas concisas y no superes nunca 3 frases.
Solo responde con el contenido del mensaje, sin prefijos ni explicaciones."""
        if self._background:
            system_prompt += f"""

Tu background (contexto de tu personaje): {self._background}
Actúa de forma coherente con este contexto."""
        if self._mission:
            system_prompt += f"""

Tienes una misión secreta que debes intentar cumplir durante la conversación. No la reveles explícitamente, aunque puedes dar pistas sobre ella.
Tu misión: {self._mission}"""
        if extra_system_instruction:
            system_prompt += f"""

{extra_system_instruction.strip()}"""

        max_history = int(os.getenv("CHAR_CONTEXT_MESSAGES", "12"))
        history = state["messages"][-max_history:]
        messages = [{"role": "system", "content": system_prompt}]
        for msg in history:
            messages.append(
                {"role": "user", "content": f"[{msg['author']}] {msg['content']}"}
            )
        return messages

    def _stream_response_to_stdout(
        self,
        messages: list[dict[str, str]],
        stream_sink: Any = None,
    ) -> str:
        """Consume el stream del modelo; escribe en stdout o en stream_sink(str). Devuelve el texto completo."""
        if stream_sink is None:
            out = sys.stdout
        else:
            class SinkWriter:
                def __init__(self, sink):
                    self._sink = sink

                def write(self, s: str):
                    self._sink(s)

                def flush(self):
                    pass

            out = SinkWriter(stream_sink)

        response = send_message(
            messages,
            model=self._model,
            temperature=self._temperature,
            stream=True,
            max_tokens=self._max_output_tokens,
        )
        assert isinstance(response, Iterator)
        raw_content: list[str] = []
        emitted_content = ""
        for chunk in response:
            raw_content.append(chunk)
            cleaned_content = self._sanitize_response_content("".join(raw_content))
            if len(cleaned_content) > len(emitted_content):
                delta = cleaned_content[len(emitted_content):]
                out.write(delta)
                out.flush()
                emitted_content = cleaned_content
        out.write("\n")
        out.flush()
        return emitted_content

    def _sanitize_response_content(self, content: str) -> str:
        cleaned = str(content or "").strip()
        if not cleaned:
            return ""

        thinking_markers = (
            "[Personaje pensando...]",
            "[personaje pensando...]",
        )
        changed = True
        while changed and cleaned:
            changed = False
            for marker in thinking_markers:
                if cleaned.startswith(marker):
                    cleaned = cleaned[len(marker):].lstrip()
                    changed = True
            bracket_prefix = f"[{self.name}]"
            if cleaned.startswith(bracket_prefix):
                cleaned = cleaned[len(bracket_prefix):].lstrip(" \t:-—\n\r")
                changed = True
            name_prefix = re.compile(rf"^{re.escape(self.name)}\s*[:\-—]\s*")
            updated = name_prefix.sub("", cleaned, count=1)
            if updated != cleaned:
                cleaned = updated.lstrip()
                changed = True

        return truncate_agent_output(cleaned)
