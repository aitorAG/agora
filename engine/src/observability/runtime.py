"""Engine observability runtime built on the internal telemetry service."""

from __future__ import annotations

import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Generator

from .telemetry_client import emit_telemetry_event, flush_telemetry

_current_trace: ContextVar[dict[str, Any] | None] = ContextVar("_current_trace", default=None)
_current_observation_metadata: ContextVar[dict[str, str]] = ContextVar(
    "_current_observation_metadata",
    default={},
)


@dataclass(slots=True)
class GenerationHandle:
    name: str
    model: str | None
    model_parameters: dict[str, Any] | None
    input_data: Any
    metadata: dict[str, str]
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_monotonic: float = field(default_factory=time.perf_counter)


def _safe_int(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _string_field(value: Any, *, default: str = "", limit: int = 200) -> str:
    if value is None:
        return default
    return str(value)[:limit]


def _base_event(event_type: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    trace = _current_trace.get() or {}
    inherited_meta = dict(_current_observation_metadata.get() or {})
    provided = metadata or {}
    merged_meta = {**inherited_meta, **provided}
    return {
        "event_type": _string_field(event_type, default="custom_event", limit=80),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "flow": _string_field(trace.get("flow") or merged_meta.get("flow"), limit=120),
        "interaction_id": _string_field(
            trace.get("interaction_id") or merged_meta.get("interaction_id"),
            limit=150,
        ),
        "user_id": _string_field(trace.get("user_id") or merged_meta.get("user_id"), limit=150),
        "game_id": _string_field(trace.get("game_id") or merged_meta.get("game_id"), limit=150),
        "turn": _safe_int(merged_meta.get("turn") or trace.get("turn")),
        "agent_name": _string_field(merged_meta.get("agent_name"), limit=120),
        "agent_type": _string_field(merged_meta.get("agent_type"), limit=80),
        "agent_step": _string_field(merged_meta.get("agent_step"), limit=120),
        "username": _string_field(merged_meta.get("username"), limit=120),
        "game_mode": _string_field(merged_meta.get("game_mode"), limit=40),
        "phase_name": _string_field(merged_meta.get("phase_name"), limit=80),
        "status": _string_field(merged_meta.get("status"), default="ok", limit=40),
        "status_message": _string_field(merged_meta.get("status_message"), limit=500),
        "duration_ms": _safe_int(merged_meta.get("duration_ms")),
    }


def flush_observability() -> None:
    flush_telemetry()


def emit_event(event_type: str, metadata: dict[str, Any] | None = None) -> None:
    emit_telemetry_event(_base_event(event_type, metadata))


def record_user_login(user_id: str, username: str) -> None:
    emit_event(
        "user_login",
        metadata={
            "user_id": user_id,
            "username": username,
            "status": "ok",
        },
    )


def start_generation(
    *,
    name: str,
    model: str | None = None,
    model_parameters: dict[str, Any] | None = None,
    input_data: Any = None,
    metadata: dict[str, Any] | None = None,
) -> GenerationHandle:
    inherited_meta = dict(_current_observation_metadata.get() or {})
    provided = metadata or {}
    merged_meta = {str(k): str(v) for k, v in {**inherited_meta, **provided}.items() if v is not None}
    return GenerationHandle(
        name=name,
        model=model,
        model_parameters=model_parameters or {},
        input_data=input_data,
        metadata=merged_meta,
    )


def end_generation(
    generation: GenerationHandle | None,
    *,
    output: Any = None,
    usage_details: dict[str, int] | None = None,
    cost_details: dict[str, float] | None = None,
    level: str | None = None,
    status_message: str | None = None,
) -> None:
    if generation is None:
        return
    elapsed_ms = int(max(0.0, (time.perf_counter() - generation.started_monotonic) * 1000.0))
    usage = usage_details or {}
    cost = cost_details or {}
    model_parameters = generation.model_parameters or {}
    stream_value = str(model_parameters.get("stream", generation.metadata.get("stream", "false"))).lower()
    event = _base_event(
        "llm_call",
        metadata={
            **generation.metadata,
            "status": "error" if (level or "").upper() == "ERROR" else "ok",
            "status_message": status_message or "",
        },
    )
    event.update(
        {
            "provider": str(model_parameters.get("provider") or generation.metadata.get("provider") or "unknown"),
            "model": str(generation.model or ""),
            "generation_name": generation.name,
            "duration_ms": elapsed_ms,
            "stream": stream_value in {"1", "true", "yes"},
            "usage_input_tokens": _safe_int(usage.get("input")),
            "usage_output_tokens": _safe_int(usage.get("output")),
            "usage_total_tokens": _safe_int(usage.get("total")),
            "cost_input": _safe_float(cost.get("input")),
            "cost_output": _safe_float(cost.get("output")),
            "cost_total": _safe_float(cost.get("total")),
            "output_chars": len(str(output)) if output is not None else 0,
        }
    )
    emit_telemetry_event(event)


@contextmanager
def trace_interaction(
    game_id: str,
    user_id: str,
    interaction_id: str,
    name: str = "interaction",
) -> Generator[dict[str, Any], None, None]:
    trace = {
        "flow": name,
        "game_id": (game_id or "")[:200],
        "user_id": (user_id or "")[:200],
        "interaction_id": (interaction_id or "")[:200],
    }
    token = _current_trace.set(trace)
    meta_token = _current_observation_metadata.set(
        {
            "flow": trace["flow"],
            "game_id": trace["game_id"],
            "interaction_id": trace["interaction_id"],
            "user_id": trace["user_id"],
        }
    )
    try:
        yield trace
    finally:
        _current_observation_metadata.reset(meta_token)
        _current_trace.reset(token)


@contextmanager
def trace_setup(
    user_id: str,
    interaction_id: str,
    name: str = "setup",
) -> Generator[dict[str, Any], None, None]:
    trace = {
        "flow": name,
        "game_id": "",
        "user_id": (user_id or "")[:200],
        "interaction_id": (interaction_id or "")[:200],
    }
    token = _current_trace.set(trace)
    meta_token = _current_observation_metadata.set(
        {
            "flow": trace["flow"],
            "game_id": "",
            "interaction_id": trace["interaction_id"],
            "user_id": trace["user_id"],
        }
    )
    try:
        yield trace
    finally:
        _current_observation_metadata.reset(meta_token)
        _current_trace.reset(token)


@contextmanager
def span_agent(
    name: str,
    metadata: dict[str, Any] | None = None,
) -> Generator[dict[str, str], None, None]:
    inherited_meta = dict(_current_observation_metadata.get() or {})
    meta = {str(k): str(v) for k, v in (metadata or {}).items() if v is not None}
    merged = {**inherited_meta, **meta, "span_name": name}
    token = _current_observation_metadata.set(merged)
    try:
        yield merged
    finally:
        _current_observation_metadata.reset(token)
