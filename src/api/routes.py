"""Endpoints HTTP para el motor de partida."""

import json
import os
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse

from .schemas import (
    NewGameRequest,
    NewGameResponse,
    CharacterInfo,
    StatusResponse,
    MessageOut,
    GameResultOut,
    TurnRequest,
    ContextResponse,
)
from .dependencies import get_engine


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


@router.post("/new", response_model=NewGameResponse)
def new_game(
    body: NewGameRequest | None = None,
    engine=Depends(get_engine),
):
    """Crea una partida. Devuelve session_id, estado inicial y contexto."""
    body = body or NewGameRequest()
    theme = (body.theme or "").strip() or os.getenv("GAME_THEME")
    try:
        session_id, setup = engine.create_game(
            theme=theme or None,
            num_actors=body.num_actors,
            max_turns=body.max_turns,
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
def get_status(session_id: str, engine=Depends(get_engine)):
    """Devuelve estado actual: turn_current, turn_max, current_speaker, player_can_write, game_finished, result, messages."""
    try:
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
def turn(body: TurnRequest, engine=Depends(get_engine)):
    """Ejecuta el turno con el texto del jugador. Respuesta en streaming (SSE)."""
    try:
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
def get_context(session_id: str, engine=Depends(get_engine)):
    """Devuelve contexto estable: player_mission, personajes, metadata inicial."""
    try:
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
