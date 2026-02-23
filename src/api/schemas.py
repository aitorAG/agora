"""Modelos Pydantic para requests/responses de la API."""

from typing import Any, Optional
from pydantic import BaseModel, Field


# --- POST /game/new ---
class NewGameRequest(BaseModel):
    theme: Optional[str] = Field(default=None, max_length=600)
    num_actors: Optional[int] = Field(default=None, ge=1, le=5)
    max_turns: int = 10


class CharacterInfo(BaseModel):
    name: str
    personality: Optional[str] = None
    mission: Optional[str] = None
    background: Optional[str] = None
    presencia_escena: Optional[str] = None


class NewGameResponse(BaseModel):
    session_id: str
    turn_current: int = 0
    turn_max: int = 10
    player_can_write: bool = False
    player_mission: str = ""
    characters: list[CharacterInfo] = Field(default_factory=list)
    narrativa_inicial: str = ""


# --- GET /game/status ---
class MessageOut(BaseModel):
    author: str
    content: str
    timestamp: Optional[str] = None
    turn: int = 0


class GameResultOut(BaseModel):
    reason: Optional[str] = None
    mission_evaluation: Optional[dict[str, Any]] = None


class StatusResponse(BaseModel):
    turn_current: int
    turn_max: int
    current_speaker: str = ""
    player_can_write: bool
    game_finished: bool = False
    result: Optional[GameResultOut] = None
    messages: list[MessageOut] = Field(default_factory=list)


# --- POST /game/turn ---
class TurnRequest(BaseModel):
    session_id: str
    text: str = ""
    user_exit: bool = False


# --- GET /game/context ---
class ContextResponse(BaseModel):
    player_mission: str = ""
    characters: list[CharacterInfo] = Field(default_factory=list)
    ambientacion: str = ""
    contexto_problema: str = ""
    relevancia_jugador: str = ""
    narrativa_inicial: str = ""


# --- GET /game/list ---
class GameListItem(BaseModel):
    id: str
    title: str = ""
    status: str = "active"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class GameListResponse(BaseModel):
    games: list[GameListItem] = Field(default_factory=list)


# --- POST /game/resume ---
class ResumeGameRequest(BaseModel):
    session_id: str


class ResumeGameResponse(BaseModel):
    session_id: str
    loaded_from_memory: bool = False


# --- Auth ---
class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class RegisterRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=6, max_length=200)


class AuthUserResponse(BaseModel):
    id: str
    username: str
    is_active: bool = True


class LoginResponse(BaseModel):
    user: AuthUserResponse
    authenticated: bool = True


# --- Health ---
class HealthResponse(BaseModel):
    status: str = "ok"
