"""Endpoints HTTP para el motor de partida."""

import json
import os
import time
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Response
from fastapi.responses import StreamingResponse, FileResponse, RedirectResponse

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
    InitMetricRequest,
    FeedbackRequest,
    FeedbackResponse,
    AdminFeedbackItem,
    AdminFeedbackListResponse,
    ContextResponse,
    GameListItem,
    GameListResponse,
    ResumeGameRequest,
    ResumeGameResponse,
    StandardTemplateItem,
    StandardTemplateListResponse,
    StandardStartRequest,
    StandardStartResponse,
    LoginRequest,
    RegisterRequest,
    LoginResponse,
    AuthUserResponse,
)
from .dependencies import get_engine, get_current_user, require_admin, get_persistence_provider
from ..core.standard_games import (
    StandardTemplateError,
    list_standard_templates,
    load_standard_template,
)
from ..observability import record_user_login


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


def _emit_game_init_metrics(
    *,
    game_id: str,
    user_id: str,
    username: str,
    mode: str,
    status: str,
    total_ms: int,
    phases: dict[str, int],
    status_message: str = "",
) -> None:
    from ..observability import emit_event

    safe_mode = "standard" if str(mode).strip().lower() == "standard" else "custom"
    safe_status = "error" if str(status).strip().lower() == "error" else "ok"
    emit_event(
        "game_init_summary",
        {
            "game_id": game_id,
            "user_id": user_id,
            "username": username,
            "game_mode": safe_mode,
            "status": safe_status,
            "status_message": status_message,
            "duration_ms": max(0, int(total_ms)),
        },
    )
    for phase_name, phase_ms in phases.items():
        emit_event(
            "game_init_phase",
            {
                "game_id": game_id,
                "user_id": user_id,
                "username": username,
                "game_mode": safe_mode,
                "phase_name": str(phase_name),
                "status": safe_status,
                "status_message": status_message,
                "duration_ms": max(0, int(phase_ms)),
            },
        )


router = APIRouter(prefix="/game", tags=["game"])
auth_router = APIRouter(prefix="/auth", tags=["auth"])
authz_router = APIRouter(prefix="/authz", tags=["authz"])
admin_router = APIRouter(prefix="/admin", tags=["admin"])

_repo_root = Path(__file__).resolve().parents[3]
_admin_feedback_page = _repo_root / "frontend" / "static" / "admin-feedback.html"


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

    record_user_login(
        user_id=str(user.get("id", "")),
        username=str(user.get("username", "")),
    )
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
            role=str(user.get("role", "user")),
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
            role=str(user.get("role", "user")),
        ),
        authenticated=True,
    )


@auth_router.get("/me", response_model=AuthUserResponse)
def me(current_user: AuthUserResponse = Depends(get_current_user)):
    return current_user


@authz_router.get("/admin")
def authz_admin(_current_user: AuthUserResponse = Depends(require_admin)):
    return {"authorized": True}


@admin_router.get("/feedback/")
def admin_feedback_page(_current_user: AuthUserResponse = Depends(require_admin)):
    if not _admin_feedback_page.is_file():
        raise HTTPException(status_code=404, detail="Admin feedback page not found")
    return FileResponse(_admin_feedback_page)


@admin_router.get("/observability/")
def admin_observability_redirect(_current_user: AuthUserResponse = Depends(require_admin)):
    target = (os.getenv("AGORA_OBSERVABILITY_URL") or "http://localhost:8081").strip()
    return RedirectResponse(url=target, status_code=307)


@admin_router.get("/feedback/list", response_model=AdminFeedbackListResponse)
def admin_feedback_list(
    limit: int = 500,
    _current_user: AuthUserResponse = Depends(require_admin),
    engine=Depends(get_engine),
):
    items = engine.list_feedback(limit=limit)
    return AdminFeedbackListResponse(items=[AdminFeedbackItem(**item) for item in items])


@auth_router.post("/logout")
def logout(response: Response):
    response.delete_cookie(key=auth_cookie_name(), path="/")
    return {"ok": True}


@router.post("/new", response_model=NewGameResponse)
def new_game(
    body: NewGameRequest | None = None,
    current_user: AuthUserResponse = Depends(get_current_user),
    engine=Depends(get_engine),
):
    """Crea una partida custom generada desde la explicación del usuario."""
    body = body or NewGameRequest()
    raw_theme = (body.theme or "").strip()
    use_env_theme = raw_theme == "" and body.num_actors is None
    theme = os.getenv("GAME_THEME") if use_env_theme else (raw_theme or None)
    num_actors = body.num_actors if body.num_actors is not None else 3

    route_t0 = time.perf_counter()
    phases: dict[str, int] = {}
    session_id = ""
    phase_t0 = time.perf_counter()
    try:
        session_id, setup = engine.create_game(
            theme=theme or None,
            num_actors=num_actors,
            max_turns=body.max_turns,
            username=current_user.username,
        )
        phases["create_game_and_warmup"] = int((time.perf_counter() - phase_t0) * 1000)
    except Exception as exc:
        _emit_game_init_metrics(
            game_id=session_id,
            user_id=current_user.id,
            username=current_user.username,
            mode="custom",
            status="error",
            total_ms=int((time.perf_counter() - route_t0) * 1000),
            phases=phases,
            status_message=str(exc),
        )
        raise HTTPException(status_code=500, detail=str(exc))

    phase_t0 = time.perf_counter()
    try:
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
        phases["serialize_response"] = int((time.perf_counter() - phase_t0) * 1000)
    except Exception as exc:
        phases["serialize_response"] = int((time.perf_counter() - phase_t0) * 1000)
        _emit_game_init_metrics(
            game_id=session_id,
            user_id=current_user.id,
            username=current_user.username,
            mode="custom",
            status="error",
            total_ms=int((time.perf_counter() - route_t0) * 1000),
            phases=phases,
            status_message=str(exc),
        )
        raise HTTPException(status_code=500, detail=str(exc))

    _emit_game_init_metrics(
        game_id=session_id,
        user_id=current_user.id,
        username=current_user.username,
        mode="custom",
        status="ok",
        total_ms=int((time.perf_counter() - route_t0) * 1000),
        phases=phases,
    )
    return NewGameResponse(
        session_id=session_id,
        turn_current=status["turn_current"],
        turn_max=status["turn_max"],
        player_can_write=status["player_can_write"],
        player_mission=setup.get("player_mission", ""),
        characters=characters,
        narrativa_inicial=setup.get("narrativa_inicial", ""),
    )


@router.get("/standard/list", response_model=StandardTemplateListResponse)
def list_standard_templates_endpoint(
    current_user: AuthUserResponse = Depends(get_current_user),
):
    """Lista templates estándar disponibles para creación rápida."""
    _ = current_user  # asegurar autenticación sin alterar lógica adicional.
    templates = list_standard_templates()
    return StandardTemplateListResponse(
        templates=[StandardTemplateItem(**item) for item in templates]
    )


@router.post("/standard/start", response_model=StandardStartResponse)
def start_standard_game(
    body: StandardStartRequest,
    current_user: AuthUserResponse = Depends(get_current_user),
    engine=Depends(get_engine),
):
    """Crea partida copiando un template standard ya preconstruido."""
    route_t0 = time.perf_counter()
    phases: dict[str, int] = {}
    session_id = ""
    phase_t0 = time.perf_counter()
    try:
        loaded = load_standard_template(body.template_id)
        phases["template_load_validate"] = int((time.perf_counter() - phase_t0) * 1000)
    except KeyError:
        _emit_game_init_metrics(
            game_id="",
            user_id=current_user.id,
            username=current_user.username,
            mode="standard",
            status="error",
            total_ms=int((time.perf_counter() - route_t0) * 1000),
            phases=phases,
            status_message="Standard template not found",
        )
        raise HTTPException(status_code=404, detail="Standard template not found")
    except StandardTemplateError as exc:
        _emit_game_init_metrics(
            game_id="",
            user_id=current_user.id,
            username=current_user.username,
            mode="standard",
            status="error",
            total_ms=int((time.perf_counter() - route_t0) * 1000),
            phases=phases,
            status_message=f"Invalid standard template: {exc}",
        )
        raise HTTPException(status_code=400, detail=f"Invalid standard template: {exc}")

    setup = loaded.get("setup", {})
    template_id = str(loaded.get("template_id") or body.template_id)
    template_version = str(loaded.get("template_version") or "1.0.0")
    phase_t0 = time.perf_counter()
    try:
        session_id, final_setup = engine.create_game_from_setup(
            setup=setup,
            username=current_user.username,
            standard_template_id=template_id,
            template_version=template_version,
        )
        phases["create_game_and_warmup"] = int((time.perf_counter() - phase_t0) * 1000)
    except ValueError as exc:
        _emit_game_init_metrics(
            game_id=session_id,
            user_id=current_user.id,
            username=current_user.username,
            mode="standard",
            status="error",
            total_ms=int((time.perf_counter() - route_t0) * 1000),
            phases=phases,
            status_message=str(exc),
        )
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        _emit_game_init_metrics(
            game_id=session_id,
            user_id=current_user.id,
            username=current_user.username,
            mode="standard",
            status="error",
            total_ms=int((time.perf_counter() - route_t0) * 1000),
            phases=phases,
            status_message=str(exc),
        )
        raise HTTPException(status_code=500, detail=str(exc))

    phase_t0 = time.perf_counter()
    try:
        status = engine.get_status(session_id)
        actors = final_setup.get("actors", [])
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
        phases["serialize_response"] = int((time.perf_counter() - phase_t0) * 1000)
    except Exception as exc:
        phases["serialize_response"] = int((time.perf_counter() - phase_t0) * 1000)
        _emit_game_init_metrics(
            game_id=session_id,
            user_id=current_user.id,
            username=current_user.username,
            mode="standard",
            status="error",
            total_ms=int((time.perf_counter() - route_t0) * 1000),
            phases=phases,
            status_message=str(exc),
        )
        raise HTTPException(status_code=500, detail=str(exc))

    _emit_game_init_metrics(
        game_id=session_id,
        user_id=current_user.id,
        username=current_user.username,
        mode="standard",
        status="ok",
        total_ms=int((time.perf_counter() - route_t0) * 1000),
        phases=phases,
    )
    return StandardStartResponse(
        session_id=session_id,
        turn_current=status["turn_current"],
        turn_max=status["turn_max"],
        player_can_write=status["player_can_write"],
        player_mission=final_setup.get("player_mission", ""),
        characters=characters,
        narrativa_inicial=final_setup.get("narrativa_inicial", ""),
        game_mode="standard",
        standard_template_id=template_id,
        template_version=template_version,
    )


@router.get("/status", response_model=StatusResponse)
def get_status(
    session_id: str,
    current_user: AuthUserResponse = Depends(get_current_user),
    engine=Depends(get_engine),
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


@router.post("/init-metric")
def init_metric(
    body: InitMetricRequest,
    current_user: AuthUserResponse = Depends(get_current_user),
    engine=Depends(get_engine),
):
    """Recibe TTFA cliente (click -> primer mensaje actor renderizado)."""
    _ensure_game_ownership(engine, body.session_id, current_user.username)
    provider = get_persistence_provider()
    try:
        game = provider.get_game(body.session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")
    from ..observability import emit_event

    mode = str(game.get("game_mode") or "custom")
    emit_event(
        "game_init_client",
        {
            "game_id": body.session_id,
            "user_id": str(game.get("user_id") or current_user.id),
            "username": current_user.username,
            "game_mode": mode,
            "duration_ms": int(body.ttfa_client_ms),
            "status": "ok",
        },
    )
    return {"ok": True}


@router.post("/turn")
def turn(
    body: TurnRequest,
    current_user: AuthUserResponse = Depends(get_current_user),
    engine=Depends(get_engine),
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
            elif ev_type == "observer_thinking":
                data = json.dumps({"type": "observer_thinking"})
            elif ev_type == "message_start":
                data = json.dumps({"type": "message_start", "author": ev.get("author", "")})
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


@router.post("/feedback", response_model=FeedbackResponse, status_code=201)
def submit_feedback(
    body: FeedbackRequest,
    current_user: AuthUserResponse = Depends(get_current_user),
    engine=Depends(get_engine),
):
    """Guarda feedback libre de usuario asociado a una partida."""
    _ensure_game_ownership(engine, body.session_id, current_user.username)
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="Feedback text is required")
    try:
        feedback_id = engine.submit_feedback(
            game_id=body.session_id,
            user_id=current_user.id,
            feedback_text=text,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return FeedbackResponse(
        feedback_id=feedback_id,
        session_id=body.session_id,
        user_id=current_user.id,
        stored=True,
    )


@router.get("/context", response_model=ContextResponse)
def get_context(
    session_id: str,
    current_user: AuthUserResponse = Depends(get_current_user),
    engine=Depends(get_engine),
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
    current_user: AuthUserResponse = Depends(get_current_user),
    engine=Depends(get_engine),
):
    """Lista partidas del usuario actual."""
    games = engine.list_games(username=current_user.username)
    return GameListResponse(games=[GameListItem(**g) for g in games])


@router.post("/resume", response_model=ResumeGameResponse)
def resume_game(
    body: ResumeGameRequest,
    current_user: AuthUserResponse = Depends(get_current_user),
    engine=Depends(get_engine),
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
