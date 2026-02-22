"""Punto de entrada único.

Lee INTERFACE_MODE para elegir modo:
- terminal (default): loop de conversación por CLI con streaming; no levanta servidor.
- api: configura logging mínimo y levanta el servidor HTTP (FastAPI/uvicorn).

Valores inválidos provocan error claro y salida con código 1.
"""

import os
import sys

from dotenv import load_dotenv
from src.persistence import create_persistence_provider

load_dotenv()

VALID_MODES = ("terminal", "api")


def main() -> None:
    mode = os.getenv("INTERFACE_MODE", "terminal").strip().lower()
    if mode not in VALID_MODES:
        print(f"INTERFACE_MODE must be 'terminal' or 'api' (got: {repr(mode)}).", file=sys.stderr)
        sys.exit(1)

    # Inicializa persistencia al arranque para fallar rápido en modo db.
    create_persistence_provider()

    if mode == "terminal":
        from src.cli.run import run_terminal
        run_terminal()
        return

    if mode == "api":
        from src.logging_config import setup_api_logging
        import uvicorn
        setup_api_logging()
        host = os.getenv("AGORA_API_HOST", "0.0.0.0")
        port = int(os.getenv("AGORA_API_PORT", "8000"))
        uvicorn.run(
            "src.api.app:app",
            host=host,
            port=port,
            log_level="info",
        )


if __name__ == "__main__":
    main()
