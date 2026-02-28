"""Roles CrewAI: Director (orquestador), Guionista, Character, Observer."""

from .director import run_game_loop, run_one_step, route_continuation, route_should_continue
from .guionista import create_guionista_agent, run_setup_task
from .character import create_character_agent, run_character_response
from .observer import create_observer_agent, run_observer_tasks  # noqa: F401

__all__ = [
    "run_game_loop",
    "run_one_step",
    "route_continuation",
    "route_should_continue",
    "create_guionista_agent",
    "run_setup_task",
    "create_character_agent",
    "run_character_response",
    "create_observer_agent",
    "run_observer_tasks",
]
