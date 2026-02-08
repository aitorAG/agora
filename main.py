"""Punto de entrada del Conversation Engine.

Cliente de terminal: usa el motor vía bootstrap con InputProvider y OutputHandler
que enlazan con stdin/stdout. El motor no conoce la terminal.
"""

import json
import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from src.session import create_session
from src.io_adapters import TerminalInputProvider, TerminalOutputHandler

# Archivo JSON de setup (raíz del proyecto). Lo escribe el cliente tras crear la sesión.
GAME_SETUP_PATH = Path(__file__).resolve().parent / "game_setup.json"

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("langchain").setLevel(logging.WARNING)
logging.getLogger("langgraph").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def main():
    """Función principal: cliente de terminal que orquesta motor + I/O."""
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print("Error: DEEPSEEK_API_KEY no encontrada en variables de entorno")
        print("Por favor, crea un archivo .env con tu API key de DeepSeek")
        return

    print("=== Conversation Engine ===")
    print("Inicializando sistema conversacional...\n")

    theme = os.getenv("GAME_THEME")
    num_actors = 3
    max_turns_str = os.getenv("MAX_TURNS", "10")
    try:
        max_turns = int(max_turns_str)
        if max_turns <= 0:
            raise ValueError("MAX_TURNS debe ser un número positivo")
    except ValueError:
        logger.warning("Valor inválido para MAX_TURNS: %s. Usando 10.", max_turns_str)
        max_turns = 10

    input_provider = TerminalInputProvider()
    output_handler = TerminalOutputHandler()

    graph, initial_state, setup = create_session(
        theme=theme,
        num_actors=num_actors,
        max_turns=max_turns,
        input_provider=input_provider,
        output_handler=output_handler,
    )

    # Persistir setup (responsabilidad del cliente)
    with open(GAME_SETUP_PATH, "w", encoding="utf-8") as f:
        json.dump(setup, f, indent=2, ensure_ascii=False)

    # Mostrar narrativa y misión vía handler
    output_handler.on_setup_ready(setup)

    print(f"Agentes: {', '.join(a['name'] for a in setup['actors'])}")
    print(f"Máximo de turnos: {max_turns}")
    print("Iniciando conversación...\n")
    print("-" * 50)

    try:
        recursion_limit = max(100, 50 + max_turns * 15)
        final_state = graph.invoke(
            initial_state,
            config={"recursion_limit": recursion_limit},
        )
        print("-" * 50)
        print(f"\nConversación finalizada después de {final_state['turn']} turnos.")
        print(f"Total de mensajes: {len(final_state['messages'])}")
    except Exception as e:
        logger.error("Error durante la ejecución: %s", e, exc_info=True)
        output_handler.on_error(f"\nError: {e}")


if __name__ == "__main__":
    main()
