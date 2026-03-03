"""Backward-compatible shim kept temporarily for older imports."""

from .runtime import (
    GenerationHandle,
    end_generation,
    flush_observability,
    span_agent,
    start_generation,
    trace_interaction,
    trace_setup,
)


def get_langfuse() -> None:
    return None


def flush_langfuse() -> None:
    flush_observability()


__all__ = [
    "GenerationHandle",
    "get_langfuse",
    "flush_langfuse",
    "flush_observability",
    "trace_interaction",
    "trace_setup",
    "span_agent",
    "start_generation",
    "end_generation",
]
