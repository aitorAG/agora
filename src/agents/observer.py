"""ObserverAgent - Agente observador que analiza la conversaci?n."""

import logging
import json
import os
from typing import Dict, Any, List
from collections import Counter
from ..state import ConversationState
from .base import Agent
from .deepseek_adapter import send_message


logger = logging.getLogger(__name__)


def parse_mission_evaluation_response(content: str) -> Dict[str, Any]:
    """Parsea la respuesta JSON del LLM de evaluación de misiones.
    
    Args:
        content: String de respuesta (puede incluir bloques ```json).
    Returns:
        Dict con player_mission_achieved (bool) y reasoning (str).
    
    Raises:
        json.JSONDecodeError: Si el contenido no es JSON válido.
    """
    content = content.strip()
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        content = content.split("```")[1].split("```")[0].strip()
    data = json.loads(content)
    player_ok = bool(data.get("player_mission_achieved", False))
    return {
        "player_mission_achieved": player_ok,
        "reasoning": str(data.get("reasoning", "")).strip() or "Sin razonamiento.",
    }


def normalize_who_should_respond(decision: dict, actor_names: list[str]) -> str:
    """Normaliza who_should_respond de la decisión del LLM: 1 actor -> "character", varios -> nombre concreto.
    
    Args:
        decision: Dict con clave who_should_respond (valor crudo del LLM).
        actor_names: Lista de nombres de personajes.
    
    Returns:
        "user", "none", "character" (si hay un solo actor) o el nombre del actor (si hay varios).
    """
    who_raw = decision.get("who_should_respond", "none")
    who_str = (who_raw if isinstance(who_raw, str) else str(who_raw)).strip()
    who_lower = who_str.lower()
    if who_lower == "user":
        return "user"
    if who_lower == "none":
        return "none"
    if actor_names:
        matched = next((n for n in actor_names if n.lower() == who_lower), None)
        if matched:
            return "character" if len(actor_names) == 1 else matched
        return "none"
    if not actor_names and who_lower == "character":
        return "character"
    return "none"


class ObserverAgent(Agent):
    """Agente pasivo que analiza la conversaci?n sin escribir mensajes."""
    
    def __init__(
        self,
        name: str = "Observer",
        model: str = "deepseek-chat",
        actor_names: List[str] | None = None,
        player_mission: str | None = None,
    ):
        """Inicializa el ObserverAgent.

        Args:
            name: Nombre del observador
            model: Modelo de DeepSeek a usar para evaluación
            actor_names: Lista de nombres de personajes disponibles (para incluir en el prompt al decidir quién responde)
            player_mission: Misión privada del jugador (para evaluar si la ha alcanzado al final del turno)
        """
        super().__init__(name)
        self._model = model
        self._temperature = 0.3
        self._actor_names = actor_names or []
        self._player_mission = (player_mission or "").strip()
    
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
            authors_in_messages = {m["author"] for m in messages if m["author"] in self._actor_names}
            actors_who_spoke = [n for n in self._actor_names if n in authors_in_messages]
            actors_not_yet_spoken = [n for n in self._actor_names if n not in authors_in_messages]
            spoken_str = ", ".join(actors_who_spoke) if actors_who_spoke else "ninguno"
            not_spoken_str = ", ".join(actors_not_yet_spoken) if actors_not_yet_spoken else "ninguno"
            names_str = ", ".join(f'"{n}"' for n in self._actor_names)
            who_options = f'uno de los personajes ({names_str}), "user" o "none"'
            system_prompt = f"""Eres un observador experto que analiza conversaciones. Tu tarea es determinar si alguien debe responder antes de pasar al siguiente turno.

Personajes en la escena: {", ".join(self._actor_names)}.
Han intervenido ya en esta conversación: {spoken_str}.
Aún no han hablado: {not_spoken_str}.

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
- Los personajes pueden hablar entre sí; no es obligatorio que después de un personaje hable el jugador. Si el contexto lo pide (p. ej. una pregunta dirigida a otro personaje, o dar entrada a quien aún no ha intervenido), quien debe responder puede ser otro personaje.
- El siguiente en hablar puede ser cualquier otro participante (otro personaje o el jugador), según el contexto.
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
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
            content = send_message(
                llm_messages, model=self._model, temperature=self._temperature, stream=False
            )
            assert isinstance(content, str)
            content = content.strip()

            # Intentar parsear JSON (puede venir con markdown code blocks)
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            decision = json.loads(content)
            
            # Validar estructura
            if "needs_response" not in decision or "who_should_respond" not in decision:
                raise ValueError("Respuesta del LLM no tiene la estructura esperada")

            who = normalize_who_should_respond(decision, self._actor_names)
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

    def evaluate_missions(self, state: ConversationState) -> Dict[str, Any]:
        """Evalúa si el jugador ha alcanzado su misión personal según la conversación.

        Args:
            state: Estado actual de la conversación (messages, turn).

        Returns:
            Diccionario con player_mission_achieved (bool) y reasoning (str).
        """
        has_player = bool(self._player_mission)
        if not has_player:
            return {
                "player_mission_achieved": False,
                "reasoning": "No hay misión del jugador configurada.",
            }
        messages = state.get("messages", [])
        if not messages:
            return {
                "player_mission_achieved": False,
                "reasoning": "Sin mensajes en la conversación.",
            }
        # Contexto reciente (últimos N mensajes para tener suficiente historia)
        max_history = int(os.getenv("OBSERVER_CONTEXT_MESSAGES", "15"))
        recent = messages[-max_history:]
        context_lines = [f"[{m['author']}] {m['content']}" for m in recent]
        context_text = "\n".join(context_lines)
        mission_block = 'Misión del jugador (participante "Usuario"): ' + self._player_mission
        system_prompt = """Eres un evaluador objetivo. Te dan una conversación y la misión privada del jugador.
Tu tarea es determinar, solo con lo que se ha dicho y hecho en la conversación hasta ahora, si el jugador ha alcanzado su objetivo.
Responde SOLO con un JSON válido en este formato exacto (sin comentarios):
{
  "player_mission_achieved": true o false,
  "reasoning": "Breve explicación de por qué consideras que la misión del jugador se ha alcanzado o no (1-3 frases)."
}
Reglas: Sé estricto: solo true si la conversación muestra claramente que el objetivo se ha cumplido. Si no hay evidencia suficiente, false.
Responde SOLO con el JSON. Si usas markdown, envuelve en ```json ... ```."""
        user_prompt = f"""Conversación reciente:\n{context_text}\n\n{mission_block}\n\n¿El jugador (Usuario) ha alcanzado ya su misión? Responde con el JSON especificado."""
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
            content = send_message(
                messages, model=self._model, temperature=self._temperature, stream=False
            )
            assert isinstance(content, str)
            return parse_mission_evaluation_response(content.strip())
        except Exception as e:
            logger.warning("Error al evaluar misiones: %s. Usando valores por defecto.", e)
            return {
                "player_mission_achieved": False,
                "reasoning": f"Error en evaluación: {str(e)}",
            }

    def _compute_game_ended(self, mission_evaluation: Dict[str, Any]) -> tuple[bool, str]:
        """Determina si la partida debe cerrarse por misión cumplida del jugador + evidencia narrativa."""
        if not mission_evaluation:
            return False, ""
        player_ok = bool(mission_evaluation.get("player_mission_achieved", False))
        reasoning = (mission_evaluation.get("reasoning") or "").strip()
        if not player_ok or not reasoning:
            return False, ""
        reason = "El jugador ha cumplido su misión. " + reasoning
        return True, reason.strip()

    def process(self, state: ConversationState) -> Dict[str, Any]:
        """Analiza el estado completo de la conversaci?n.
        
        Args:
            state: Estado actual de la conversaci?n
            
        Returns:
            Diccionario con an?lisis y m?tricas
        """
        messages = state["messages"]
        
        if not messages:
            mission_eval = self.evaluate_missions(state)
            game_ended, game_ended_reason = self._compute_game_ended(mission_eval)
            return {
                "analysis": "No hay mensajes para analizar",
                "continuation_decision": {"needs_response": False, "who_should_respond": "none", "reason": "Sin mensajes"},
                "mission_evaluation": mission_eval,
                "game_ended": game_ended,
                "game_ended_reason": game_ended_reason,
                "update_metadata": True,
            }
        
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
        # Evaluar si el jugador o los actores han alcanzado su misión:
        # solo reevaluar cuando el último mensaje es del Usuario (fin de turno),
        # para evitar llamadas redundantes al LLM en pasos intermedios.
        last_author = messages[-1]["author"]
        if last_author == "Usuario":
            mission_evaluation = self.evaluate_missions(state)
        else:
            meta = state.get("metadata", {})
            mission_evaluation = meta.get("last_mission_evaluation")
            if not isinstance(mission_evaluation, dict):
                mission_evaluation = {
                    "player_mission_achieved": False,
                    "reasoning": "Sin nueva evaluación de misiones en este paso.",
                }
        # Decisión de cierre: si al menos una misión lograda y hay evidencia narrativa (reasoning), partida terminada
        game_ended, game_ended_reason = self._compute_game_ended(mission_evaluation)
        
        return {
            "analysis": analysis,
            "continuation_decision": continuation_decision,
            "mission_evaluation": mission_evaluation,
            "game_ended": game_ended,
            "game_ended_reason": game_ended_reason,
            "update_metadata": True
        }
