"""GuionistaAgent - Agente que genera la ambientación y el setup de la partida."""

import json
import logging
import sys
from typing import Dict, Any, List, Iterator
from ..state import ConversationState
from .base import Agent
from .deepseek_adapter import send_message


logger = logging.getLogger(__name__)


def _fallback_titulo(ambientacion: str, contexto_problema: str, player_mission: str) -> str:
    """Genera un título breve (4-5 palabras aprox.) si el LLM no lo devuelve."""
    source = f"{ambientacion} {contexto_problema} {player_mission}".strip()
    words = [w.strip(".,;:!?()[]{}\"'") for w in source.split() if w.strip(".,;:!?()[]{}\"'")]
    if not words:
        return "Sombras sobre el conflicto"
    selected = words[:5]
    if len(selected) < 4:
        selected = (selected + ["en", "la", "noche", "eterna"])[:4]
    return " ".join(selected)


def _fallback_descripcion_breve(contexto_problema: str, player_mission: str) -> str:
    """Genera una descripción breve en 2 líneas si el LLM no la devuelve."""
    linea_1 = (contexto_problema or "Una historia repleta de intrigas y tensión.").strip()
    linea_2 = (player_mission or "Completa tu objetivo para resolver el conflicto.").strip()
    return f"{linea_1}\n{linea_2}"


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
    narrativa_default = "Una conversación en un lugar neutro. Hay una situación que requiere tu participación; tu intervención puede cambiar el curso de los acontecimientos. " + " ".join(f"{a['name']} está presente." for a in actors)
    return {
        "titulo": "Sombras sobre Baviera rota",
        "descripcion_breve": (
            "Una historia de tensión y sospechas tras la guerra.\n"
            "Descubre la causa del conflicto y cumple tu misión."
        ),
        "ambientacion": "Una conversación en un lugar neutro.",
        "contexto_problema": "Hay una situación que requiere la participación del jugador.",
        "relevancia_jugador": "Tu intervención puede cambiar el curso de los acontecimientos.",
        "player_mission": "Participar en la conversación y lograr conectar con los personajes.",
        "narrativa_inicial": narrativa_default,
        "actors": actors,
    }


class GuionistaAgent(Agent):
    """Agente que define al inicio la ambientación, objetivo del jugador y actores (personalidad, misión, background).
    No es actor: no escribe en el chat; solo se invoca una vez al arranque para generar el setup.
    """

    def __init__(self, name: str = "Guionista", model: str = "deepseek-chat"):
        super().__init__(name)
        self._model = model
        self._temperature = 2.0

    @property
    def is_actor(self) -> bool:
        return False

    def process(self, state: ConversationState) -> Dict[str, Any]:
        """No se usa en el flujo del grafo; el Guionista solo expone generate_setup."""
        return {"update_metadata": False}

    def _build_setup_messages(
        self, theme: str | None, num_actors: int
    ) -> List[Dict[str, str]]:
        """Construye la lista de mensajes para el LLM (lógica de dominio)."""
        theme_part = f"El tema o semilla es: «{theme}». " if theme else "Inventa una ambientación atractiva. "
        system_prompt = """Eres un guionista experto. Tu tarea es definir el setup de una partida de juego conversacional.

Debes generar un JSON válido con esta estructura exacta (sin comentarios, sin campos extra):
{
  "titulo": "Título de 4-5 palabras, llamativo y tipo película.",
  "descripcion_breve": "Dos líneas: la primera resume el contexto de alto nivel y la segunda expresa claramente la misión del jugador.",
  "ambientacion": "Descripción del escenario: época, lugar, tono de la historia (2-4 frases).",
  "contexto_problema": "Explicación de la situación o el problema en el que se encuentra la escena (2-4 frases). Qué está en juego, qué conflicto o tensión existe.",
  "relevancia_jugador": "Por qué esta situación es relevante o importante para el jugador (1-2 frases). Qué puede ganar o perder, por qué su participación importa.",
  "player_mission": "Objetivo principal que el jugador debe intentar alcanzar durante la conversación (privado, 1-2 frases). es un objetivo concreto que un director puede evaluar que ha ocurrido, no una actitud o disposición a algo.",
  "narrativa_inicial": "Prosa continua de 1 a 3 párrafos que integre todo: el escenario y la atmósfera, la situación o el problema en juego, por qué le importa al jugador, y la presencia en escena de los tres personajes (nombres y breve descripción de dónde o cómo están). Sin apartados ni títulos dentro del texto pero con parrafos legibles; tono dinámico y excitante, como el arranque de una novela o una partida de rol.",
  "actors": [
    {
      "name": "Nombre del personaje",
      "personality": "Descripción en tercera persona para el LLM del personaje: cómo es, cómo habla (ej. Es reservada, le gusta el chocolate...).",
      "mission": "Objetivo privado que este personaje intenta alcanzar durante la conversación (1-2 frases).",
      "background": "Breve contexto del personaje: gustos, origen, profesión, rasgos relevantes, coherente con la ambientación.",
      "presencia_escena": "Una sola frase que describa su presencia en la escena (ej. sentada junto a la ventana, observando la calle; de pie junto a la puerta; acurrucada en el sofá con una taza de té)."
    }
  ]
}

Reglas:
- titulo, descripcion_breve, ambientacion, contexto_problema, relevancia_jugador, player_mission, narrativa_inicial y cada actor deben ser coherentes entre sí.
- titulo debe tener entre 4 y 5 palabras y sonar atractivo.
- descripcion_breve debe tener exactamente dos líneas (usa un salto de línea).
- narrativa_inicial debe ser prosa continua: sin secciones tituladas (no uses "Ambientación:", "Personajes:", etc.). Integra de forma natural escenario, situación, relevancia y los personajes con su presencia en la escena.
- actors debe tener exactamente el número de personajes que se te indique.
- presencia_escena debe ser muy breve: una frase por personaje para la descripción inicial.
- Responde SOLO con el JSON, sin texto antes ni después. Si usas markdown, envuelve el JSON en ```json ... ```."""

        user_prompt = f"""Genera el setup de la partida. {theme_part}Debes crear exactamente {num_actors} actor(es).
Responde únicamente con el JSON especificado."""

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def _stream_setup_to_stdout(
        self,
        messages: List[Dict[str, str]],
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
        thinking = "[Guionista escribiendo...]"
        out.write("\r" + thinking)
        out.flush()

        response = send_message(
            messages,
            model=self._model,
            temperature=self._temperature,
            stream=True,
        )
        assert isinstance(response, Iterator)
        full_content: List[str] = []
        first = True
        for chunk in response:
            if first:
                out.write("\r" + " " * len(thinking) + "\r")
                out.flush()
                first = False
            out.write(chunk)
            out.flush()
            full_content.append(chunk)
        if first:
            out.write("\r" + " " * len(thinking) + "\r")
        out.write("\n")
        out.flush()
        return "".join(full_content)

    def generate_setup(
        self,
        theme: str | None = None,
        num_actors: int = 3,
        stream: bool = False,
        stream_sink: Any = None,
    ) -> Dict[str, Any]:
        """Genera el setup de la partida: ambientación, contexto del problema, relevancia, player_mission y actores (name, personality, mission, background, presencia_escena).

        Args:
            theme: Tema o semilla opcional (ej. "historia romántica en Alemania siglo XVII, trama de detectives en un mundo de fantasia o aventuras de humor en ciberpunk magico"). Si es None, el Guionista inventa.
            num_actors: Número de actores a generar.
            stream: Si True, emite la salida del modelo (JSON) token a token (stdout o stream_sink).
            stream_sink: Si se pasa y stream=True, cada chunk se envía a stream_sink(str); si no, se usa stdout.

        Returns:
            Diccionario con keys: ambientacion, contexto_problema, relevancia_jugador, player_mission, actors (lista con name, personality, mission, background, presencia_escena).
        """
        messages = self._build_setup_messages(theme, num_actors)
        try:
            if stream:
                content = self._stream_setup_to_stdout(messages, stream_sink=stream_sink)
            else:
                content = send_message(
                    messages,
                    model=self._model,
                    temperature=self._temperature,
                    stream=False,
                )
                assert isinstance(content, str)
            content = content.strip()

            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            data = json.loads(content)

            if not isinstance(data, dict):
                raise ValueError("La respuesta no es un objeto JSON")
            if "titulo" not in data or "descripcion_breve" not in data:
                raise ValueError("Faltan campos obligatorios: titulo, descripcion_breve")
            if "ambientacion" not in data or "player_mission" not in data or "actors" not in data:
                raise ValueError("Faltan campos obligatorios: ambientacion, player_mission, actors")
            if "contexto_problema" not in data or "relevancia_jugador" not in data:
                raise ValueError("Faltan campos obligatorios: contexto_problema, relevancia_jugador")
            actors_list = data["actors"]
            if not isinstance(actors_list, list) or len(actors_list) < num_actors:
                raise ValueError("actors debe ser una lista con al menos num_actors elementos")

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
            ambientacion = str(data.get("ambientacion", "")).strip()
            contexto_problema = str(data.get("contexto_problema", "")).strip()
            relevancia_jugador = str(data.get("relevancia_jugador", "")).strip()
            player_mission = str(data.get("player_mission", "")).strip()
            titulo = str(data.get("titulo", "")).strip()
            descripcion_breve = str(data.get("descripcion_breve", "")).strip()
            narrativa_inicial = str(data.get("narrativa_inicial", "")).strip()
            if not titulo:
                titulo = _fallback_titulo(ambientacion, contexto_problema, player_mission)
            if not descripcion_breve:
                descripcion_breve = _fallback_descripcion_breve(contexto_problema, player_mission)
            if not narrativa_inicial:
                parts = [ambientacion, contexto_problema, relevancia_jugador]
                for a in normalized_actors:
                    parts.append(f"{a['name']}: {a['presencia_escena']}.")
                narrativa_inicial = " ".join(parts)
            return {
                "titulo": titulo,
                "descripcion_breve": descripcion_breve,
                "ambientacion": ambientacion,
                "contexto_problema": contexto_problema,
                "relevancia_jugador": relevancia_jugador,
                "player_mission": player_mission,
                "narrativa_inicial": narrativa_inicial,
                "actors": normalized_actors,
            }
        except Exception as e:
            logger.warning("Error al generar setup con el Guionista: %s. Usando setup por defecto.", e)
            return _default_setup(num_actors)
