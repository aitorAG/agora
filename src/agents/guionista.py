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
            "presencia_escena": "Presente en la escena.",
        })
    return {
        "ambientacion": "Una conversación en un lugar neutro.",
        "contexto_problema": "Hay una situación que requiere la participación del jugador.",
        "relevancia_jugador": "Tu intervención puede cambiar el curso de los acontecimientos.",
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
        num_actors: int = 3,
    ) -> Dict[str, Any]:
        """Genera el setup de la partida: ambientación, contexto del problema, relevancia, player_mission y actores (name, personality, mission, background, presencia_escena).

        Args:
            theme: Tema o semilla opcional (ej. "historia romántica en Alemania siglo XVII"). Si es None, el Guionista inventa.
            num_actors: Número de actores a generar (por defecto 3).

        Returns:
            Diccionario con keys: ambientacion, contexto_problema, relevancia_jugador, player_mission, actors (lista con name, personality, mission, background, presencia_escena).
        """
        theme_part = f"El tema o semilla es: «{theme}». " if theme else "Inventa una ambientación atractiva. "
        system_prompt = """Eres un guionista experto. Tu tarea es definir el setup de una partida de juego conversacional.

Debes generar un JSON válido con esta estructura exacta (sin comentarios, sin campos extra):
{
  "ambientacion": "Descripción del escenario: época, lugar, tono de la historia (2-4 frases).",
  "contexto_problema": "Explicación de la situación o el problema en el que se encuentra la escena (2-4 frases). Qué está en juego, qué conflicto o tensión existe.",
  "relevancia_jugador": "Por qué esta situación es relevante o importante para el jugador (1-2 frases). Qué puede ganar o perder, por qué su participación importa.",
  "player_mission": "Objetivo principal que el jugador debe intentar alcanzar durante la conversación (privado, 1-2 frases).",
  "actors": [
    {
      "name": "Nombre del personaje",
      "personality": "Descripción en segunda persona para el LLM del personaje: cómo es, cómo habla (ej. Eres reservada, te gusta el chocolate...).",
      "mission": "Objetivo privado que este personaje intenta alcanzar durante la conversación (1-2 frases).",
      "background": "Breve contexto del personaje: gustos, origen, profesión, rasgos relevantes, coherente con la ambientación.",
      "presencia_escena": "Una sola frase que describa su presencia en la escena (ej. sentada junto a la ventana, observando la calle; de pie junto a la puerta; acurrucada en el sofá con una taza de té)."
    }
  ]
}

Reglas:
- ambientacion, contexto_problema, relevancia_jugador, player_mission y cada actor deben ser coherentes entre sí.
- actors debe tener exactamente el número de personajes que se te indique (normalmente 3).
- presencia_escena debe ser muy breve: una frase por personaje para la descripción inicial.
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
            if "contexto_problema" not in data or "relevancia_jugador" not in data:
                raise ValueError("Faltan campos obligatorios: contexto_problema, relevancia_jugador")
            actors_list = data["actors"]
            if not isinstance(actors_list, list) or len(actors_list) < num_actors:
                raise ValueError("actors debe ser una lista con al menos num_actors elementos")

            # Normalizar cada actor: name, personality, mission, background, presencia_escena
            normalized_actors: List[Dict[str, str]] = []
            for i, a in enumerate(actors_list[:num_actors]):
                if not isinstance(a, dict):
                    raise ValueError(f"Actor {i} no es un objeto")
                normalized_actors.append({
                    "name": str(a.get("name", f"Personaje{i + 1}")).strip(),
                    "personality": str(a.get("personality", "Eres amigable.")).strip(),
                    "mission": str(a.get("mission", "Mantener la conversación.")).strip(),
                    "background": str(a.get("background", "Sin background.")).strip(),
                    "presencia_escena": str(a.get("presencia_escena", "Presente en la escena.")).strip(),
                })

            return {
                "ambientacion": str(data.get("ambientacion", "")).strip(),
                "contexto_problema": str(data.get("contexto_problema", "")).strip(),
                "relevancia_jugador": str(data.get("relevancia_jugador", "")).strip(),
                "player_mission": str(data.get("player_mission", "")).strip(),
                "actors": normalized_actors,
            }
        except Exception as e:
            logger.warning("Error al generar setup con el Guionista: %s. Usando setup por defecto.", e)
            return _default_setup(num_actors)
