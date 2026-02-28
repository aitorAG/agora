"""
Cliente Langfuse para observabilidad de Agora.

Solo inicializa Langfuse si LANGFUSE_PUBLIC_KEY y LANGFUSE_SECRET_KEY están definidos.
Proporciona helpers para crear traces y spans sin bloquear el flujo principal.
No se llama flush() en ningún path crítico.

Usa la API v2 de Langfuse (trace/span con user_id y session_id directos).
"""

from __future__ import annotations

import atexit
import os
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Generator

_langfuse_instance: Any = None
_current_trace: ContextVar[Any] = ContextVar("_current_trace", default=None)
_current_observation: ContextVar[Any] = ContextVar("_current_observation", default=None)
_current_observation_metadata: ContextVar[dict[str, str]] = ContextVar(
    "_current_observation_metadata",
    default={},
)


def get_langfuse() -> Any | None:
    """Devuelve la instancia de Langfuse si está configurada, None en caso contrario."""
    global _langfuse_instance
    if _langfuse_instance is not None:
        return _langfuse_instance
    if not os.getenv("LANGFUSE_PUBLIC_KEY") or not os.getenv("LANGFUSE_SECRET_KEY"):
        return None
    try:
        from langfuse import Langfuse

        host = os.getenv("LANGFUSE_HOST") or os.getenv("LANGFUSE_BASE_URL")
        _langfuse_instance = Langfuse(host=host) if host else Langfuse()
        # En SDK v2 tracing_enabled puede existir con valor None.
        # Solo deshabilitamos explícitamente si el cliente lo marca en False.
        if getattr(_langfuse_instance, "tracing_enabled", True) is False:
            return None
        return _langfuse_instance
    except Exception:
        return None


def flush_langfuse() -> None:
    """Fuerza envío de eventos pendientes; no lanza errores al caller."""
    lf = get_langfuse()
    if lf is None:
        return
    try:
        flush = getattr(lf, "flush", None)
        if callable(flush):
            flush()
    except Exception:
        return


def start_generation(
    *,
    name: str,
    model: str | None = None,
    model_parameters: dict[str, Any] | None = None,
    input_data: Any = None,
    metadata: dict[str, Any] | None = None,
) -> Any | None:
    """Crea una generation anidada en la observación activa (span/trace)."""
    langfuse = get_langfuse()
    if langfuse is None:
        return None
    inherited_meta = dict(_current_observation_metadata.get() or {})
    provided_meta = metadata or {}
    merged_meta = {
        **inherited_meta,
        **{str(k): str(v)[:200] for k, v in provided_meta.items() if v is not None},
    }
    payload = {
        "name": name,
        "model": model,
        "model_parameters": model_parameters,
        "input": input_data,
        "metadata": merged_meta or None,
    }
    payload = {k: v for k, v in payload.items() if v is not None}
    try:
        parent = _current_observation.get()
        if parent is not None and hasattr(parent, "generation"):
            return parent.generation(**payload)
        trace = _current_trace.get()
        if trace is not None and hasattr(trace, "generation"):
            return trace.generation(**payload)
        return langfuse.generation(**payload)
    except Exception:
        return None


def end_generation(
    generation: Any | None,
    *,
    output: Any = None,
    usage_details: dict[str, int] | None = None,
    cost_details: dict[str, float] | None = None,
    level: str | None = None,
    status_message: str | None = None,
) -> None:
    """Cierra una generation existente actualizando output/usage/cost."""
    if generation is None:
        return
    update_payload: dict[str, Any] = {}
    if output is not None:
        update_payload["output"] = output
    if usage_details:
        update_payload["usage_details"] = usage_details
    if cost_details:
        update_payload["cost_details"] = cost_details
    if level:
        update_payload["level"] = level
    if status_message:
        update_payload["status_message"] = status_message
    try:
        if hasattr(generation, "end"):
            generation.end(**update_payload)
    except Exception:
        return


@contextmanager
def trace_interaction(
    game_id: str,
    user_id: str,
    interaction_id: str,
    name: str = "interaction",
) -> Generator[Any, None, None]:
    """
    Crea un trace para una interacción (turno) con session_id=game_id y user_id.
    Usa la API v2 de Langfuse (trace con user_id/session_id directos).
    """
    langfuse = get_langfuse()
    if langfuse is None:
        yield None
        return

    trace = langfuse.trace(
        name=name,
        user_id=user_id[:200] if user_id else None,
        session_id=game_id[:200] if game_id else None,
        metadata={
            "game_id": game_id[:200] if game_id else "",
            "interaction_id": interaction_id[:200] if interaction_id else "",
        },
    )
    token = _current_trace.set(trace)
    obs_token = _current_observation.set(trace)
    meta_token = _current_observation_metadata.set(
        {
            "flow": name,
            "trace_name": name,
            "game_id": game_id[:200] if game_id else "",
            "interaction_id": interaction_id[:200] if interaction_id else "",
        }
    )
    try:
        yield trace
    finally:
        _current_observation_metadata.reset(meta_token)
        _current_observation.reset(obs_token)
        _current_trace.reset(token)


@contextmanager
def trace_setup(user_id: str, name: str = "setup") -> Generator[Any, None, None]:
    """
    Crea un trace para la fase de setup (Guionista) cuando aún no existe game_id.
    """
    langfuse = get_langfuse()
    if langfuse is None:
        yield None
        return

    trace = langfuse.trace(
        name=name,
        user_id=user_id[:200] if user_id else None,
        metadata={"phase": "setup"},
    )
    token = _current_trace.set(trace)
    obs_token = _current_observation.set(trace)
    meta_token = _current_observation_metadata.set(
        {
            "flow": name,
            "trace_name": name,
            "phase": "setup",
        }
    )
    try:
        yield trace
    finally:
        _current_observation_metadata.reset(meta_token)
        _current_observation.reset(obs_token)
        _current_trace.reset(token)


@contextmanager
def span_agent(
    name: str,
    metadata: dict[str, Any] | None = None,
) -> Generator[Any, None, None]:
    """
    Crea un span hijo para una acción de agente.
    Si hay un trace activo (trace_interaction/trace_setup), el span se anida en él.
    """
    langfuse = get_langfuse()
    if langfuse is None:
        yield None
        return

    meta = metadata or {}
    meta_str = {k: str(v)[:200] for k, v in meta.items() if v is not None}

    trace = _current_trace.get()
    if trace is not None:
        span = trace.span(name=name, metadata=meta_str)
    else:
        span = langfuse.span(name=name, metadata=meta_str)

    obs_token = _current_observation.set(span)
    inherited_meta = dict(_current_observation_metadata.get() or {})
    merged_meta = {**inherited_meta, **meta_str, "span_name": name}
    meta_token = _current_observation_metadata.set(merged_meta)
    try:
        yield span
    finally:
        _current_observation_metadata.reset(meta_token)
        _current_observation.reset(obs_token)
        if hasattr(span, "end"):
            span.end()


atexit.register(flush_langfuse)
