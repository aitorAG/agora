"""Endpoints HTTP para el motor de partida."""

from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends

from .schemas import (
    CreateGameRequest,
    CreateGameResponse,
    ActorInfo,
    GameStateResponse,
    MessageOut,
    PlayerInputRequest,
    PlayerInputResponse,
    TickResponse,
)
from .dependencies import get_engine


def _state_to_response(state: dict, who_should_speak: str | None = None) -> GameStateResponse:
    """Convierte ConversationState a GameStateResponse (timestamp -> ISO string)."""
    messages_raw = state.get("messages", [])
    messages_out = [
        MessageOut(
            author=m.get("author", ""),
            content=m.get("content", ""),
            timestamp=m["timestamp"].isoformat() if isinstance(m.get("timestamp"), datetime) else str(m.get("timestamp")) if m.get("timestamp") else None,
            turn=m.get("turn", 0),
        )
        for m in messages_raw
    ]
    metadata = state.get("metadata", {})
    who = who_should_speak or metadata.get("continuation_decision", {}).get("who_should_respond")
    if who == "user":
        who = "user"
    return GameStateResponse(
        turn=state.get("turn", 0),
        messages=messages_out,
        who_should_speak=who,
        game_ended=bool(metadata.get("game_ended", False)),
        metadata=metadata,
    )


def _serialize_events(events: list) -> list[dict]:
    """Asegura que eventos tengan timestamps serializables en 'message'."""
    out = []
    for ev in events:
        if ev.get("type") == "message" and "message" in ev:
            m = ev["message"]
            msg = dict(m)
            if isinstance(msg.get("timestamp"), datetime):
                msg["timestamp"] = msg["timestamp"].isoformat()
            out.append({"type": "message", "message": msg})
        else:
            out.append(dict(ev))
    return out


router = APIRouter(prefix="/game", tags=["game"])


@router.post("/create", response_model=CreateGameResponse)
def create_game(
    body: CreateGameRequest | None = None,
    engine=Depends(get_engine),
):
    body = body or CreateGameRequest()
    game_id, setup = engine.create_game(
        theme=body.theme,
        num_actors=body.num_actors,
        max_turns=body.max_turns,
    )
    actors = [ActorInfo(name=a["name"], personality=a.get("personality"), mission=a.get("mission"), background=a.get("background")) for a in setup.get("actors", [])]
    return CreateGameResponse(
        game_id=game_id,
        narrativa_inicial=setup.get("narrativa_inicial", ""),
        player_mission=setup.get("player_mission", ""),
        actors=actors,
    )


@router.get("/{game_id}/state", response_model=GameStateResponse)
def get_state(game_id: str, engine=Depends(get_engine)):
    try:
        state = engine.get_state(game_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Game not found")
    return _state_to_response(state)


@router.post("/{game_id}/player_input", response_model=PlayerInputResponse)
def player_input(game_id: str, body: PlayerInputRequest, engine=Depends(get_engine)):
    try:
        events, state, game_ended = engine.player_input(game_id, body.text, body.user_exit)
    except KeyError:
        raise HTTPException(status_code=404, detail="Game not found")
    mission_evaluation = state.get("metadata", {}).get("last_mission_evaluation") if game_ended else None
    return PlayerInputResponse(
        events=_serialize_events(events),
        mission_evaluation=mission_evaluation,
        game_ended=game_ended,
        state=_state_to_response(state),
    )


@router.post("/{game_id}/tick", response_model=TickResponse)
def tick(game_id: str, engine=Depends(get_engine)):
    try:
        events, state, game_ended, waiting_for_player = engine.tick(game_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Game not found")
    return TickResponse(
        events=_serialize_events(events),
        state=_state_to_response(state),
        game_ended=game_ended,
        waiting_for_player=waiting_for_player,
    )


