"""Flujo de conversación por terminal: create_session + runner con I/O en stdin/stdout."""

import json
import os
import time
import uuid
from pathlib import Path

from src.logging_config import setup_session_logging, get_logger
from src.session import create_session
from src.io_adapters import TerminalInputProvider, TerminalOutputHandler

GAME_SETUP_PATH = Path(__file__).resolve().parent.parent.parent / "game_setup.json"


def run_terminal() -> None:
    """Ejecuta el loop de conversación por terminal: setup, narrativa, turnos con streaming."""
    session_id = str(uuid.uuid4())
    setup_session_logging(session_id)
    logger = get_logger("CLI")

    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print("Error: DEEPSEEK_API_KEY no encontrada en variables de entorno")
        print("Por favor, crea un archivo .env con tu API key de DeepSeek")
        return

    logger.info("Session started")
    print("=== Conversation Engine ===")
    print("Inicializando sistema conversacional...\n")

    theme = os.getenv("GAME_THEME")
    num_actors = int(os.getenv("NUM_ACTORS", "3"))
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

    logger.info("create_session started")
    t0_session = time.perf_counter()
    runner, initial_state, setup = create_session(
        theme=theme,
        num_actors=num_actors,
        max_turns=max_turns,
        input_provider=input_provider,
        output_handler=output_handler,
    )
    elapsed_session = time.perf_counter() - t0_session
    logger.info("create_session finished in %.2f s", elapsed_session)

    with open(GAME_SETUP_PATH, "w", encoding="utf-8") as f:
        json.dump(setup, f, indent=2, ensure_ascii=False)

    output_handler.on_setup_ready(setup)

    print(f"Agentes: {', '.join(a['name'] for a in setup['actors'])}")
    print(f"Máximo de turnos: {max_turns}")
    print("Iniciando conversación...\n")
    print("-" * 50)

    logger.info("runner started")
    t0_runner = time.perf_counter()
    try:
        final_state = runner()
        elapsed_runner = time.perf_counter() - t0_runner
        logger.info(
            "runner finished in %.2f s (turnos=%d, mensajes=%d)",
            elapsed_runner,
            final_state["turn"],
            len(final_state.get("messages", [])),
        )
        print("-" * 50)
        print(f"\nConversación finalizada después de {final_state['turn']} turnos.")
        print(f"Total de mensajes: {len(final_state['messages'])}")
    except Exception as e:
        logger.error("Error durante la ejecución: %s", e, exc_info=True)
        output_handler.on_error(f"\nError: {e}")
    finally:
        logger.info("Session ended")
