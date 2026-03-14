"""Punto de entrada único.

Lee INTERFACE_MODE para elegir modo:
- terminal (default): loop de conversación por CLI con streaming; no levanta servidor.
- api: configura logging mínimo y levanta el servidor HTTP (FastAPI/uvicorn).
- outbox_dispatcher: publica eventos outbox persistidos hacia Redis Streams.
- notary_worker: consume checkpoints y materializa snapshots del notario.

Valores inválidos provocan error claro y salida con código 1.
"""

import os
import sys

from src.api.auth import ensure_seed_user
from src.config import bootstrap_runtime_config
from src.persistence import create_persistence_provider

bootstrap_runtime_config()

VALID_MODES = ("terminal", "api", "outbox_dispatcher", "notary_worker")


def main() -> None:
    mode = os.getenv("INTERFACE_MODE", "terminal").strip().lower()
    if mode not in VALID_MODES:
        print(
            "INTERFACE_MODE must be one of "
            f"{', '.join(repr(value) for value in VALID_MODES)} (got: {repr(mode)}).",
            file=sys.stderr,
        )
        sys.exit(1)

    # Inicializa persistencia al arranque para fallar rápido en modo db.
    persistence = create_persistence_provider()
    ensure_seed_user()

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
        return

    if mode == "outbox_dispatcher":
        from src.logging_config import setup_api_logging
        from src.queueing import OutboxDispatcher, RedisStreamQueue
        setup_api_logging()
        dispatcher = OutboxDispatcher(
            persistence=persistence,
            queue_client=RedisStreamQueue(),
        )
        dispatcher.run_forever()
        return

    if mode == "notary_worker":
        from src.logging_config import setup_api_logging
        from src.notary import HeuristicNotaryProcessor, LLMNotaryProcessor, NotaryWorker
        from src.queueing import RedisStreamQueue
        setup_api_logging()
        worker = NotaryWorker(
            persistence=persistence,
            queue_client=RedisStreamQueue(),
            processor=LLMNotaryProcessor(fallback_processor=HeuristicNotaryProcessor()),
        )
        while True:
            worker.run_once()


if __name__ == "__main__":
    main()
