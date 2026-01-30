"""ObserverAgent - Agente observador que analiza la conversaci?n."""

import logging
import json
from typing import Dict, Any, List, Counter
from collections import Counter
from langchain_deepseek import ChatDeepSeek
from langchain_core.messages import HumanMessage, SystemMessage
from ..state import ConversationState
from .base import Agent


logger = logging.getLogger(__name__)


class ObserverAgent(Agent):
    """Agente pasivo que analiza la conversaci?n sin escribir mensajes."""
    
    def __init__(
        self,
        name: str = "Observer",
        model: str = "deepseek-chat",
        actor_names: List[str] | None = None,
    ):
        """Inicializa el ObserverAgent.

        Args:
            name: Nombre del observador
            model: Modelo de DeepSeek a usar para evaluación
            actor_names: Lista de nombres de personajes disponibles (para incluir en el prompt al decidir quién responde)
        """
        super().__init__(name)
        self._llm = ChatDeepSeek(model=model, temperature=0.3)
        self._actor_names = actor_names or []
    
    @property
    def is_actor(self) -> bool:
        """ObserverAgent no es un actor."""
        return False
    
    def evaluate_continuation(self, state: ConversationState) -> Dict[str, Any]:
        """Eval?a si alguien debe continuar la conversaci?n antes de ceder la palabra.
        
        Args:
            state: Estado actual de la conversaci?n
            
        Returns:
            Diccionario con needs_response, who_should_respond, y reason
        """
        messages = state["messages"]
        
        if not messages:
            return {
                "needs_response": False,
                "who_should_respond": "none",
                "reason": "No hay mensajes en la conversaci?n"
            }
        
        # Verificar si el usuario quiere salir
        if state.get("metadata", {}).get("user_exit", False):
            return {
                "needs_response": False,
                "who_should_respond": "none",
                "reason": "El usuario ha solicitado salir"
            }
        
        # Construir contexto de la conversaci?n
        conversation_context = []
        for msg in messages[-5:]:  # ?ltimos 5 mensajes para contexto
            conversation_context.append(f"[{msg['author']}] {msg['content']}")
        
        context_text = "\n".join(conversation_context)
        last_message = messages[-1]

        # Construir prompt según si tenemos lista de personajes o no
        if self._actor_names:
            names_str = ", ".join(f'"{n}"' for n in self._actor_names)
            who_options = f'uno de los personajes ({names_str}), "user" o "none"'
            system_prompt = f"""Eres un observador experto que analiza conversaciones. Tu tarea es determinar si alguien debe responder antes de pasar al siguiente turno.

Personajes disponibles en la conversación: {", ".join(self._actor_names)}. Algunos pueden no haber hablado aún.

Analiza el contexto de la conversación y decide:
1. ¿Hay preguntas sin responder?
2. ¿El último mensaje requiere una respuesta?
3. ¿El flujo natural sugiere que alguien debe continuar (incluyendo un personaje que aún no ha hablado)?

Responde SOLO con un JSON válido en este formato exacto:
{{
    "needs_response": true/false,
    "who_should_respond": {who_options},
    "reason": "breve explicación de tu decisión"
}}

Reglas:
- Si debe hablar un personaje, usa su nombre exacto (ej. {names_str}). Si es el jugador, usa "user". Si nadie debe responder, "none".
- Si el último mensaje es una pregunta, quien debe responder es otro participante (personaje o user).
- Si la conversación está completa o naturalmente pausada, usa "none".
- Considera dar turno a personajes que todavía no han hablado si el contexto lo pide."""
        else:
            system_prompt = """Eres un observador experto que analiza conversaciones. Tu tarea es determinar si alguien debe responder antes de pasar al siguiente turno.

Responde SOLO con un JSON válido en este formato exacto:
{
    "needs_response": true/false,
    "who_should_respond": "character" o "user" o "none",
    "reason": "breve explicación de tu decisión"
}

Reglas:
- Si el último mensaje es una pregunta, quien debe responder es el otro participante
- Si la conversación está completa o naturalmente pausada, usa "none"
- Considera el flujo natural: después de un mensaje del character, normalmente responde el user, y viceversa"""

        user_prompt = f"""Analiza esta conversación:

{context_text}

Último mensaje: [{last_message['author']}] {last_message['content']}

¿Alguien debe responder antes de pasar al siguiente turno? Responde con el JSON especificado."""
        
        try:
            llm_messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            response = self._llm.invoke(llm_messages)
            content = response.content.strip()
            
            # Intentar parsear JSON (puede venir con markdown code blocks)
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            decision = json.loads(content)
            
            # Validar estructura
            if "needs_response" not in decision or "who_should_respond" not in decision:
                raise ValueError("Respuesta del LLM no tiene la estructura esperada")

            # Normalizar who_should_respond: con un solo actor -> "character"; con varios -> nombre concreto
            who_raw = decision.get("who_should_respond", "none")
            who_str = (who_raw if isinstance(who_raw, str) else str(who_raw)).strip()
            who_lower = who_str.lower()
            if who_lower == "user":
                who = "user"
            elif who_lower == "none":
                who = "none"
            elif self._actor_names:
                matched = next((n for n in self._actor_names if n.lower() == who_lower), None)
                if matched:
                    who = "character" if len(self._actor_names) == 1 else matched
                else:
                    who = "none"
            elif not self._actor_names and who_lower == "character":
                who = "character"
            else:
                who = "none"

            return {
                "needs_response": bool(decision.get("needs_response", False)),
                "who_should_respond": who,
                "reason": decision.get("reason", "Sin razón especificada"),
            }
            
        except Exception as e:
            logger.warning(f"Error al evaluar continuaci?n: {e}. Usando decisi?n por defecto.")
            # Decisi?n por defecto: no continuar
            return {
                "needs_response": False,
                "who_should_respond": "none",
                "reason": f"Error en evaluaci?n: {str(e)}"
            }
    
    def process(self, state: ConversationState) -> Dict[str, Any]:
        """Analiza el estado completo de la conversaci?n.
        
        Args:
            state: Estado actual de la conversaci?n
            
        Returns:
            Diccionario con an?lisis y m?tricas
        """
        messages = state["messages"]
        
        if not messages:
            return {"analysis": "No hay mensajes para analizar"}
        
        # An?lisis de participaci?n
        authors = [msg["author"] for msg in messages]
        participation = dict(Counter(authors))
        
        # Longitud promedio de mensajes
        lengths = [len(msg["content"]) for msg in messages]
        avg_length = sum(lengths) / len(lengths) if lengths else 0
        
        # Detecci?n de repeticiones simples (palabras m?s comunes)
        all_words = []
        for msg in messages:
            words = msg["content"].lower().split()
            all_words.extend(words)
        
        word_freq = Counter(all_words)
        common_words = dict(word_freq.most_common(5))
        
        # An?lisis b?sico de tono (longitud de mensajes como proxy)
        recent_lengths = lengths[-5:] if len(lengths) >= 5 else lengths
        tone_change = "estable"
        if len(recent_lengths) >= 2:
            if recent_lengths[-1] > recent_lengths[-2] * 1.5:
                tone_change = "aumentando"
            elif recent_lengths[-1] < recent_lengths[-2] * 0.5:
                tone_change = "disminuyendo"
        
        analysis = {
            "participation": participation,
            "avg_message_length": round(avg_length, 2),
            "total_messages": len(messages),
            "common_words": common_words,
            "tone_change": tone_change,
            "turn": state["turn"]
        }
        
        # Evaluar si alguien debe continuar la conversación
        continuation_decision = self.evaluate_continuation(state)
        
        return {
            "analysis": analysis,
            "continuation_decision": continuation_decision,
            "update_metadata": True
        }
