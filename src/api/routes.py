"""Endpoints HTTP para el motor de partida."""

import json
import os
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Response
from fastapi.responses import StreamingResponse

from .auth import (
    authenticate_user,
    auth_cookie_name,
    create_user,
    create_access_token,
    ensure_seed_user,
    UserAlreadyExistsError,
)
from .schemas import (
    NewGameRequest,
    NewGameResponse,
    CharacterInfo,
    StatusResponse,
    MessageOut,
    GameResultOut,
    TurnRequest,
    ContextResponse,
    GameListItem,
    GameListResponse,
    ResumeGameRequest,
    ResumeGameResponse,
    LoginRequest,
    RegisterRequest,
    LoginResponse,
    AuthUserResponse,
)
from .dependencies import get_engine, get_current_user


def _serialize_message(m: dict) -> dict:
    """Convierte mensaje a dict con timestamp serializable."""
    ts = m.get("timestamp")
    if isinstance(ts, datetime):
        ts = ts.isoformat()
    elif ts is not None:
        ts = str(ts)
    return {
        "author": m.get("author", ""),
        "content": m.get("content", ""),
        "timestamp": ts,
        "turn": m.get("turn", 0),
    }


def _format_sse(event: str, data: str) -> str:
    """Formato Server-Sent Events: event + data + double newline."""
    return f"event: {event}\ndata: {data}\n\n"


router = APIRouter(prefix="/game", tags=["game"])
auth_router = APIRouter(prefix="/auth", tags=["auth"])


def _ensure_game_ownership(engine, game_id: str, username: str) -> None:
    try:
        is_owner = engine.game_belongs_to_user(game_id, username)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")
    if not is_owner:
        raise HTTPException(status_code=404, detail="Session not found")


@auth_router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, response: Response):
    ensure_seed_user()
    user = authenticate_user(body.username, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(str(user.get("username", "")))
    response.set_cookie(
        key=auth_cookie_name(),
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )
    return LoginResponse(
        user=AuthUserResponse(
            id=str(user.get("id", "")),
            username=str(user.get("username", "")),
            is_active=bool(user.get("is_active", True)),
        ),
        authenticated=True,
    )


@auth_router.post("/register", response_model=LoginResponse, status_code=201)
def register(body: RegisterRequest, response: Response):
    try:
        user = create_user(body.username, body.password)
    except UserAlreadyExistsError:
        raise HTTPException(status_code=409, detail="Username already exists")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    token = create_access_token(str(user.get("username", "")))
    response.set_cookie(
        key=auth_cookie_name(),
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )
    return LoginResponse(
        user=AuthUserResponse(
            id=str(user.get("id", "")),
            username=str(user.get("username", "")),
            is_active=bool(user.get("is_active", True)),
        ),
        authenticated=True,
    )


@auth_router.get("/me", response_model=AuthUserResponse)
def me(current_user: AuthUserResponse = Depends(get_current_user)):
    return current_user


@auth_router.post("/logout")
def logout(response: Response):
    response.delete_cookie(key=auth_cookie_name(), path="/")
    return {"ok": True}


@router.post("/new", response_model=NewGameResponse)
def new_game(
    body: NewGameRequest | None = None,
    engine=Depends(get_engine),
    current_user: AuthUserResponse = Depends(get_current_user),
):
    """Crea una partida. Devuelve session_id, estado inicial y contexto."""
    body = body or NewGameRequest()
    raw_theme = (body.theme or "").strip()
    # Solo usar GAME_THEME cuando no hay seed y tampoco num_actors personalizado.
    use_env_theme = raw_theme == "" and body.num_actors is None
    theme = os.getenv("GAME_THEME") if use_env_theme else (raw_theme or None)
    num_actors = body.num_actors if body.num_actors is not None else 3
    try:
        session_id, setup = engine.create_game(
            theme=theme or None,
            num_actors=num_actors,
            max_turns=body.max_turns,
            username=current_user.username,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    status = engine.get_status(session_id)
    actors = setup.get("actors", [])
    characters = [
        CharacterInfo(
            name=a.get("name", ""),
            personality=a.get("personality"),
            mission=a.get("mission"),
            background=a.get("background"),
            presencia_escena=a.get("presencia_escena"),
        )
        for a in actors
    ]
    return NewGameResponse(
        session_id=session_id,
        turn_current=status["turn_current"],
        turn_max=status["turn_max"],
        player_can_write=status["player_can_write"],
        player_mission=setup.get("player_mission", ""),
        characters=characters,
        narrativa_inicial=setup.get("narrativa_inicial", ""),
    )


@router.get("/status", response_model=StatusResponse)
def get_status(
    session_id: str,
    engine=Depends(get_engine),
    current_user: AuthUserResponse = Depends(get_current_user),
):
    """Devuelve estado actual: turn_current, turn_max, current_speaker, player_can_write, game_finished, result, messages."""
    try:
        _ensure_game_ownership(engine, session_id, current_user.username)
        status = engine.get_status(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")
    messages_out = [MessageOut(**_serialize_message(m)) for m in status.get("messages", [])]
    result = status.get("result")
    result_out = GameResultOut(**result) if result else None
    return StatusResponse(
        turn_current=status["turn_current"],
        turn_max=status["turn_max"],
        current_speaker=status.get("current_speaker", ""),
        player_can_write=status["player_can_write"],
        game_finished=status["game_finished"],
        result=result_out,
        messages=messages_out,
    )


@router.post("/turn")
def turn(
    body: TurnRequest,
    engine=Depends(get_engine),
    current_user: AuthUserResponse = Depends(get_current_user),
):
    """Ejecuta el turno con el texto del jugador. Respuesta en streaming (SSE)."""
    try:
        _ensure_game_ownership(engine, body.session_id, current_user.username)
        status = engine.get_status(body.session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")
    if not status.get("player_can_write", False):
        raise HTTPException(
            status_code=400,
            detail="Player cannot write now; wait for current_speaker or game_finished",
        )

    def event_stream():
        for ev in engine.execute_turn_stream(
            body.session_id,
            body.text,
            user_exit=body.user_exit,
        ):
            ev_type = ev.get("type", "event")
            if ev_type == "message_delta":
                data = json.dumps({"type": "message_delta", "delta": ev.get("delta", "")})
            elif ev_type == "message":
                msg = ev.get("message", {})
                data = json.dumps({"type": "message", "message": _serialize_message(msg)})
            elif ev_type == "game_ended":
                data = json.dumps({
                    "type": "game_ended",
                    "reason": ev.get("reason", ""),
                    "mission_evaluation": ev.get("mission_evaluation"),
                })
            elif ev_type == "error":
                data = json.dumps({"type": "error", "message": ev.get("message", "")})
            else:
                data = json.dumps(ev)
            yield _format_sse(ev_type, data)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/context", response_model=ContextResponse)
def get_context(
    session_id: str,
    engine=Depends(get_engine),
    current_user: AuthUserResponse = Depends(get_current_user),
):
    """Devuelve contexto estable: player_mission, personajes, metadata inicial."""
    try:
        _ensure_game_ownership(engine, session_id, current_user.username)
        ctx = engine.get_context(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")
    characters = [
        CharacterInfo(
            name=c.get("name", ""),
            personality=c.get("personality"),
            mission=c.get("mission"),
            background=c.get("background"),
            presencia_escena=c.get("presencia_escena"),
        )
        for c in ctx.get("characters", [])
    ]
    return ContextResponse(
        player_mission=ctx.get("player_mission", ""),
        characters=characters,
        ambientacion=ctx.get("ambientacion", ""),
        contexto_problema=ctx.get("contexto_problema", ""),
        relevancia_jugador=ctx.get("relevancia_jugador", ""),
        narrativa_inicial=ctx.get("narrativa_inicial", ""),
    )


@router.get("/list", response_model=GameListResponse)
def list_games(
    engine=Depends(get_engine),
    current_user: AuthUserResponse = Depends(get_current_user),
):
    """Lista partidas del usuario actual."""
    games = engine.list_games(username=current_user.username)
    return GameListResponse(games=[GameListItem(**g) for g in games])


@router.post("/resume", response_model=ResumeGameResponse)
def resume_game(
    body: ResumeGameRequest,
    engine=Depends(get_engine),
    current_user: AuthUserResponse = Depends(get_current_user),
):
    """Reanuda una partida existente por session_id."""
    try:
        _ensure_game_ownership(engine, body.session_id, current_user.username)
        result = engine.resume_game(body.session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")
    except ValueError:
        raise HTTPException(status_code=400, detail="Session cannot be resumed")
    return ResumeGameResponse(
        session_id=result.get("session_id", body.session_id),
        loaded_from_memory=bool(result.get("loaded_from_memory", False)),
    )
