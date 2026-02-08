"""Capacidad Turno de palabra: decide quién debe hablar a continuación, priorizando la participación del jugador."""

import json
import logging
from typing import Dict, Any, List

from langchain_deepseek import ChatDeepSeek
from langchain_core.messages import HumanMessage, SystemMessage

from ...state import ConversationState


logger = logging.getLogger(__name__)


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


class TurnoDePalabraAgent:
    """Capacidad que decide quién debe hablar a continuación. Prioriza que el jugador pueda participar."""

    def __init__(
        self,
        actor_names: List[str] | None = None,
        model: str = "deepseek-chat",
    ):
        """Inicializa la capacidad Turno de palabra.

        Args:
            actor_names: Lista de nombres de personajes en escena.
            model: Modelo LLM para la decisión.
        """
        self._actor_names = actor_names or []
        self._llm = ChatDeepSeek(model=model, temperature=0.3)

    def process(self, state: ConversationState) -> Dict[str, Any]:
        """Evalúa quién debe responder a continuación. Prioriza dar turno al jugador cuando el contexto lo permita.

        Returns:
            Dict con needs_response, who_should_respond ("user" | nombre personaje | "none"), reason.
        """
        messages = state["messages"]

        if not messages:
            return {
                "needs_response": False,
                "who_should_respond": "none",
                "reason": "No hay mensajes en la conversación",
            }

        if state.get("metadata", {}).get("user_exit", False):
            return {
                "needs_response": False,
                "who_should_respond": "none",
                "reason": "El usuario ha solicitado salir",
            }

        conversation_context = []
        for msg in messages[-5:]:
            conversation_context.append(f"[{msg['author']}] {msg['content']}")
        context_text = "\n".join(conversation_context)
        last_message = messages[-1]

        if self._actor_names:
            authors_in_messages = {m["author"] for m in messages if m["author"] in self._actor_names}
            actors_who_spoke = [n for n in self._actor_names if n in authors_in_messages]
            actors_not_yet_spoken = [n for n in self._actor_names if n not in authors_in_messages]
            spoken_str = ", ".join(actors_who_spoke) if actors_who_spoke else "ninguno"
            not_spoken_str = ", ".join(actors_not_yet_spoken) if actors_not_yet_spoken else "ninguno"
            names_str = ", ".join(f'"{n}"' for n in self._actor_names)
            who_options = f'uno de los personajes ({names_str}), "user" o "none"'
            system_prompt = f"""Eres un moderador que asigna el turno de palabra. Tu tarea es decidir quién debe hablar a continuación.

**Prioridad importante:** Cuando el contexto lo permita, prioriza que hable el jugador ("user") para que pueda participar. Solo asigna a un personaje cuando sea más natural (por ejemplo: réplica entre personajes, pregunta dirigida explícitamente a un personaje, o momento dramático donde debe hablar un personaje que aún no ha intervenido).

Personajes en la escena: {", ".join(self._actor_names)}.
Han intervenido ya: {spoken_str}.
Aún no han hablado: {not_spoken_str}.

Responde SOLO con un JSON válido en este formato exacto:
{{
    "needs_response": true/false,
    "who_should_respond": {who_options},
    "reason": "breve explicación"
}}

Reglas:
- Si es razonable que responda el jugador, elige "user".
- Si debe hablar un personaje, usa su nombre exacto (ej. {names_str}). Si nadie debe responder, "none".
- Los personajes pueden hablar entre sí cuando el contexto lo pida (pregunta a otro personaje, réplica).
- Si la conversación está completa o naturalmente pausada, usa "none"."""
        else:
            system_prompt = """Eres un moderador que asigna el turno de palabra. Prioriza que el jugador ("user") pueda participar cuando el contexto lo permita.

Responde SOLO con un JSON válido:
{
    "needs_response": true/false,
    "who_should_respond": "character" o "user" o "none",
    "reason": "breve explicación"
}
- Si el último mensaje es una pregunta, quien debe responder es el otro participante; cuando sea posible, prioriza "user".
- Si la conversación está completa o pausada, "none"."""

        user_prompt = f"""Conversación:\n{context_text}\n\nÚltimo mensaje: [{last_message['author']}] {last_message['content']}\n\n¿Quién debe hablar a continuación? Responde con el JSON especificado."""

        try:
            response = self._llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ])
            content = response.content.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            decision = json.loads(content)
            if "needs_response" not in decision or "who_should_respond" not in decision:
                raise ValueError("Respuesta del LLM sin estructura esperada")
            who = normalize_who_should_respond(decision, self._actor_names)
            return {
                "needs_response": bool(decision.get("needs_response", False)),
                "who_should_respond": who,
                "reason": decision.get("reason", "Sin razón especificada"),
            }
        except Exception as e:
            logger.warning("Error en turno de palabra: %s. Usando decisión por defecto.", e)
            return {
                "needs_response": False,
                "who_should_respond": "none",
                "reason": f"Error en evaluación: {str(e)}",
            }
