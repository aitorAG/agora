"""Modelos Pydantic para requests/responses de la API."""

from typing import Any, Optional
from pydantic import BaseModel, Field


# --- Create game ---
class CreateGameRequest(BaseModel):
    theme: Optional[str] = None
    num_actors: int = 3
    max_turns: int = 10


class ActorInfo(BaseModel):
    name: str
    personality: Optional[str] = None
    mission: Optional[str] = None
    background: Optional[str] = None


class CreateGameResponse(BaseModel):
    game_id: str
    narrativa_inicial: str = ""
    player_mission: str = ""
    actors: list[ActorInfo] = Field(default_factory=list)


# --- Game state ---
class MessageOut(BaseModel):
    author: str
    content: str
    timestamp: Optional[str] = None  # ISO string
    turn: int


class GameStateResponse(BaseModel):
    turn: int
    messages: list[MessageOut] = Field(default_factory=list)
    who_should_speak: Optional[str] = None
    game_ended: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


# --- Player input ---
class PlayerInputRequest(BaseModel):
    text: str = ""
    user_exit: bool = False


class EventMessage(BaseModel):
    type: str = "message"
    message: Optional[MessageOut] = None


class EventGameEnded(BaseModel):
    type: str = "game_ended"
    game_ended_reason: Optional[str] = None
    mission_evaluation: Optional[dict[str, Any]] = None


class PlayerInputResponse(BaseModel):
    events: list[dict[str, Any]] = Field(default_factory=list)
    mission_evaluation: Optional[dict[str, Any]] = None
    game_ended: bool = False
    state: Optional[GameStateResponse] = None


# --- Tick ---
class TickResponse(BaseModel):
    events: list[dict[str, Any]] = Field(default_factory=list)
    state: Optional[GameStateResponse] = None
    game_ended: bool = False
    waiting_for_player: bool = False


# --- Health ---
class HealthResponse(BaseModel):
    status: str = "ok"
