"""GuionistaAgent - Agente que genera la ambientación y el setup de la partida."""

import json
import logging
from typing import Dict, Any, List
from langchain_deepseek import ChatDeepSeek
from langchain_core.messages import HumanMessage, SystemMessage
from ..state import ConversationState
from .base import Agent


logger = logging.getLogger(__name__)


def _default_setup(num_actors: int) -> Dict[str, Any]:
    """Setup por defecto si el LLM falla o devuelve JSON inválido."""
    actors = []
    for i in range(num_actors):
        name = "Alice" if i == 0 else f"Personaje{i + 1}"
        actors.append({
            "name": name,
            "personality": "Eres amigable y conversador.",
            "mission": "Mantener una conversación interesante.",
            "background": "Personaje de una historia generada por defecto.",
        })
    return {
        "ambientacion": "Una conversación en un lugar neutro.",
        "player_mission": "Participar en la conversación y lograr conectar con los personajes.",
        "actors": actors,
    }


class GuionistaAgent(Agent):
    """Agente que define al inicio la ambientación, objetivo del jugador y actores (personalidad, misión, background).
    No es actor: no escribe en el chat; solo se invoca una vez al arranque para generar el setup.
    """

    def __init__(self, name: str = "Guionista", model: str = "deepseek-chat"):
        super().__init__(name)
        self._llm = ChatDeepSeek(model=model, temperature=0.7)

    @property
    def is_actor(self) -> bool:
        return False

    def process(self, state: ConversationState) -> Dict[str, Any]:
        """No se usa en el flujo del grafo; el Guionista solo expone generate_setup."""
        return {"update_metadata": False}

    def generate_setup(
        self,
        theme: str | None = None,
        num_actors: int = 1,
    ) -> Dict[str, Any]:
        """Genera el setup de la partida: ambientación, player_mission y actores (name, personality, mission, background).

        Args:
            theme: Tema o semilla opcional (ej. "historia romántica en Alemania siglo XVII"). Si es None, el Guionista inventa.
            num_actors: Número de actores a generar (por defecto 1).

        Returns:
            Diccionario con keys: ambientacion, player_mission, actors (lista de dicts con name, personality, mission, background).
        """
        theme_part = f"El tema o semilla es: «{theme}». " if theme else "Inventa una ambientación atractiva. "
        system_prompt = """Eres un guionista experto. Tu tarea es definir el setup de una partida de juego conversacional.

Debes generar un JSON válido con esta estructura exacta (sin comentarios, sin campos extra):
{
  "ambientacion": "Descripción del escenario: época, lugar, tono de la historia (2-4 frases).",
  "player_mission": "Objetivo principal que el jugador debe intentar alcanzar durante la conversación (privado, 1-2 frases).",
  "actors": [
    {
      "name": "Nombre del personaje",
      "personality": "Descripción en segunda persona para el LLM del personaje: cómo es, cómo habla (ej. Eres reservada, te gusta el chocolate...).",
      "mission": "Objetivo privado que este personaje intenta alcanzar durante la conversación (1-2 frases).",
      "background": "Breve contexto del personaje: gustos, origen, profesión, rasgos relevantes, coherente con la ambientación (ej. Le gusta el chocolate y salir de fiesta, desconfía de los hombres, nació en Alemania en 1660, trabaja como pastelera)."
    }
  ]
}

Reglas:
- ambientacion, player_mission y cada actor deben ser coherentes entre sí.
- actors debe tener exactamente el número de personajes que se te indique.
- Responde SOLO con el JSON, sin texto antes ni después. Si usas markdown, envuelve el JSON en ```json ... ```."""

        user_prompt = f"""Genera el setup de la partida. {theme_part}Debes crear exactamente {num_actors} actor(es).
Responde únicamente con el JSON especificado."""

        try:
            response = self._llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ])
            content = response.content.strip()

            # Extraer JSON si viene en bloque markdown
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            data = json.loads(content)

            # Validar estructura mínima
            if not isinstance(data, dict):
                raise ValueError("La respuesta no es un objeto JSON")
            if "ambientacion" not in data or "player_mission" not in data or "actors" not in data:
                raise ValueError("Faltan campos obligatorios: ambientacion, player_mission, actors")
            actors_list = data["actors"]
            if not isinstance(actors_list, list) or len(actors_list) < num_actors:
                raise ValueError("actors debe ser una lista con al menos num_actors elementos")

            # Normalizar cada actor: name, personality, mission, background
            normalized_actors: List[Dict[str, str]] = []
            for i, a in enumerate(actors_list[:num_actors]):
                if not isinstance(a, dict):
                    raise ValueError(f"Actor {i} no es un objeto")
                normalized_actors.append({
                    "name": str(a.get("name", f"Personaje{i + 1}")).strip(),
                    "personality": str(a.get("personality", "Eres amigable.")).strip(),
                    "mission": str(a.get("mission", "Mantener la conversación.")).strip(),
                    "background": str(a.get("background", "Sin background.")).strip(),
                })

            return {
                "ambientacion": str(data.get("ambientacion", "")).strip(),
                "player_mission": str(data.get("player_mission", "")).strip(),
                "actors": normalized_actors,
            }
        except Exception as e:
            logger.warning("Error al generar setup con el Guionista: %s. Usando setup por defecto.", e)
            return _default_setup(num_actors)
