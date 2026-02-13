"""Logging centralizado por sesión: terminal (con colores) + archivo por session_id."""

from __future__ import annotations

import logging
import os
import sys
from contextvars import ContextVar
from pathlib import Path

try:
    import colorama
    colorama.init()
except ImportError:
    colorama = None

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOGGER_NAME = "agora"
_session_id_var: ContextVar[str | None] = ContextVar("session_id", default=None)

# Logger base; se le añaden handlers en setup_session_logging
_logger: logging.Logger | None = None
_handlers_attached = False


def set_session_id(session_id: str) -> None:
    """Establece el session_id para la partida actual (contextvar)."""
    _session_id_var.set(session_id)


def get_session_id() -> str | None:
    """Obtiene el session_id actual o None."""
    return _session_id_var.get()


class PlainFormatter(logging.Formatter):
    """Formato sin códigos de color (para archivo)."""

    def __init__(self) -> None:
        super().__init__(
            fmt="%(asctime)s | %(levelname)s | session=%(session_id)s | %(component)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    def format(self, record: logging.LogRecord) -> str:
        record.session_id = getattr(record, "session_id", "-")
        record.component = getattr(record, "component", "-")
        return super().format(record)


class ColoredFormatter(logging.Formatter):
    """Formato con códigos ANSI por nivel (para terminal)."""

    COLORS = {
        logging.DEBUG: "\033[36m",    # cian
        logging.INFO: "\033[32m",     # verde
        logging.WARNING: "\033[33m",  # amarillo
        logging.ERROR: "\033[31m",    # rojo
    }
    RESET = "\033[0m"

    def __init__(self) -> None:
        super().__init__(
            fmt="%(asctime)s | %(levelname)s | session=%(session_id)s | %(component)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    def format(self, record: logging.LogRecord) -> str:
        record.session_id = getattr(record, "session_id", "-")
        record.component = getattr(record, "component", "-")
        base = super().format(record)
        if colorama is None:
            return base
        color = self.COLORS.get(record.levelno, self.RESET)
        return f"{color}{base}{self.RESET}"


def setup_session_logging(session_id: str) -> logging.Logger:
    """Configura el logging para esta sesión: archivo logs/session_<id>.log y terminal con colores."""
    global _logger, _handlers_attached
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_level_name = os.getenv("AGORA_LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    _logger = logging.getLogger(LOGGER_NAME)
    _logger.setLevel(log_level)
    _logger.handlers.clear()

    # Archivo: texto plano
    log_file = LOG_DIR / f"session_{session_id}.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(log_level)
    file_handler.setFormatter(PlainFormatter())
    _logger.addHandler(file_handler)

    # Terminal: colores
    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setLevel(log_level)
    stream_handler.setFormatter(ColoredFormatter())
    _logger.addHandler(stream_handler)

    # Silenciar loggers de librerías
    for name in ("httpx", "httpcore", "openai"):
        logging.getLogger(name).setLevel(logging.WARNING)

    _handlers_attached = True
    set_session_id(session_id)
    return _logger


def setup_api_logging() -> None:
    """Configura logging mínimo para modo API: solo stderr, nivel WARNING. Sin archivo por sesión.
    Los logger.info del Director, Session y LLM no se muestran; solo WARNING/ERROR."""
    global _logger, _handlers_attached
    log_level_name = os.getenv("AGORA_LOG_LEVEL", "WARNING").upper()
    log_level = getattr(logging, log_level_name, logging.WARNING)

    _logger = logging.getLogger(LOGGER_NAME)
    _logger.setLevel(log_level)
    _logger.handlers.clear()

    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setLevel(log_level)
    stream_handler.setFormatter(PlainFormatter())
    _logger.addHandler(stream_handler)

    for name in ("httpx", "httpcore", "openai"):
        logging.getLogger(name).setLevel(logging.WARNING)

    _handlers_attached = True


def get_logger(component: str, session_id: str | None = None) -> logging.LoggerAdapter:
    """Devuelve un LoggerAdapter con session_id y component para esta sesión."""
    sid = session_id if session_id is not None else (get_session_id() or "-")
    if _logger is None:
        # Sin setup previo (p. ej. tests): usar logger estándar sin handlers de sesión
        base = logging.getLogger(f"{LOGGER_NAME}.{component}")
        if not base.handlers and not logging.getLogger(LOGGER_NAME).handlers:
            base.setLevel(logging.DEBUG)
            h = logging.StreamHandler(sys.stderr)
            h.setFormatter(PlainFormatter())
            base.addHandler(h)
        return logging.LoggerAdapter(base, {"session_id": sid, "component": component})
    return logging.LoggerAdapter(_logger, {"session_id": sid, "component": component})
