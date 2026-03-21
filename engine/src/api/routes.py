"""Endpoints HTTP para el motor de partida."""

import json
import logging
import os
import re
import time
import unicodedata
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Response
from fastapi.responses import StreamingResponse, FileResponse, HTMLResponse

from .auth import (
    authenticate_user,
    auth_cookie_name,
    auth_cookie_samesite,
    auth_cookie_secure,
    create_user,
    create_access_token,
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
    AdminActorPromptField,
    AdminActorPromptResponse,
    AdminActorPromptUpdateRequest,
    AdminActorPromptUpdateResponse,
    AdminActorPromptValidation,
    AdminStandardTemplateListItem,
    AdminStandardTemplateListResponse,
    AdminStandardTemplateResponse,
    AdminStandardTemplateCreateRequest,
    AdminStandardTemplateGenerateRequest,
    AdminStandardTemplateUpdateRequest,
    AdminStandardTemplateDeleteResponse,
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
from ..agents.actor_prompt_template import (
    actor_prompt_required_fields,
    default_actor_prompt_template,
    validate_actor_prompt_template,
)
from ..core.standard_games import (
    StandardTemplateError,
    list_standard_templates,
    load_standard_template,
)
from ..core.game_setup_contract import validate_game_setup
from ..crew_roles.guionista import create_guionista_agent
from ..observability import record_user_login
from ..player_identity import display_author
from ..text_limits import validate_custom_seed, validate_user_message


def _serialize_message(m: dict, player_name: str | None = None) -> dict:
    """Convierte mensaje a dict con timestamp serializable."""
    ts = m.get("timestamp")
    if isinstance(ts, datetime):
        ts = ts.isoformat()
    elif ts is not None:
        ts = str(ts)
    return {
        "author": display_author(m.get("author", ""), player_name=player_name),
        "content": m.get("content", ""),
        "timestamp": ts,
        "turn": m.get("turn", 0),
    }


def _serialize_character_info(actor: dict | None) -> CharacterInfo:
    payload = actor if isinstance(actor, dict) else {}
    return CharacterInfo(
        name=payload.get("name", ""),
        personality=payload.get("personality"),
        mission=payload.get("mission"),
        public_mission=payload.get("public_mission"),
        background=payload.get("background"),
        presencia_escena=payload.get("presencia_escena"),
    )


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
_observability_static_dir = _repo_root / "observability_static"
if not _observability_static_dir.is_dir():
    _observability_static_dir = _repo_root / "observability-platform" / "telemetry-service" / "static"
_admin_observability_page = _observability_static_dir / "index.html"
_TEMPLATE_ID_CHUNK_RE = re.compile(r"[^a-z0-9]+")
logger = logging.getLogger(__name__)


def _ensure_game_ownership(engine, game_id: str, username: str) -> None:
    try:
        is_owner = engine.game_belongs_to_user(game_id, username)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")
    if not is_owner:
        raise HTTPException(status_code=404, detail="Session not found")


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=auth_cookie_name(),
        value=token,
        httponly=True,
        samesite=auth_cookie_samesite(),
        secure=auth_cookie_secure(),
        path="/",
    )


def _slugify_template_id(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii").lower()
    collapsed = _TEMPLATE_ID_CHUNK_RE.sub("_", ascii_text).strip("_")
    if not collapsed:
        return "historia_generada"
    return collapsed[:120].strip("_") or "historia_generada"


def _suggest_unique_template_id(base_id: str, provider) -> str:
    candidate = _slugify_template_id(base_id)
    try:
        existing_items = provider.list_standard_templates_admin()
    except NotImplementedError:
        return candidate
    existing = {
        str(item.get("id") or "").strip().lower()
        for item in existing_items
        if isinstance(item, dict)
    }
    if candidate.lower() not in existing:
        return candidate
    suffix = 2
    while True:
        numbered = f"{candidate}_{suffix}"
        trimmed = numbered[:120].strip("_")
        if trimmed.lower() not in existing:
            return trimmed
        suffix += 1


def _template_generation_timeout_seconds() -> float:
    raw = str(os.getenv("AGORA_TEMPLATE_GENERATION_TIMEOUT_SECONDS", "90")).strip()
    try:
        return max(10.0, min(float(raw), 300.0))
    except ValueError:
        return 90.0


@auth_router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, response: Response):
    user = authenticate_user(body.username, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    record_user_login(
        user_id=str(user.get("id", "")),
        username=str(user.get("username", "")),
    )
    token = create_access_token(str(user.get("username", "")))
    _set_auth_cookie(response, token)
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
    _set_auth_cookie(response, token)
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


def _render_admin_control_panel() -> HTMLResponse:
    if not _admin_observability_page.is_file():
        raise HTTPException(status_code=404, detail="Admin control panel page not found")
    html = _admin_observability_page.read_text(encoding="utf-8")
    html = html.replace(
        'href="static/styles.css',
        'href="/ui/observability-static/styles.css',
    ).replace(
        'src="static/app.js',
        'src="/ui/observability-static/app.js',
    )
    return HTMLResponse(content=html)


@admin_router.get("/observability/")
def admin_observability_redirect(_current_user: AuthUserResponse = Depends(require_admin)):
    return _render_admin_control_panel()


@admin_router.get("/panel-control/")
def admin_panel_control_page(_current_user: AuthUserResponse = Depends(require_admin)):
    return _render_admin_control_panel()


@admin_router.get("/feedback/list", response_model=AdminFeedbackListResponse)
def admin_feedback_list(
    limit: int = 500,
    _current_user: AuthUserResponse = Depends(require_admin),
    engine=Depends(get_engine),
):
    items = engine.list_feedback(limit=limit)
    return AdminFeedbackListResponse(items=[AdminFeedbackItem(**item) for item in items])


@admin_router.get("/actor-prompt", response_model=AdminActorPromptResponse)
def admin_get_actor_prompt(
    _current_user: AuthUserResponse = Depends(require_admin),
    provider=Depends(get_persistence_provider),
):
    _ = _current_user
    stored_template = provider.get_actor_prompt_template()
    template = str(stored_template or default_actor_prompt_template())
    validation = validate_actor_prompt_template(template)
    return AdminActorPromptResponse(
        template=template,
        source="custom" if stored_template else "default",
        required_fields=[AdminActorPromptField(**item) for item in actor_prompt_required_fields()],
        validation=AdminActorPromptValidation(**validation),
    )


@admin_router.post("/actor-prompt", response_model=AdminActorPromptUpdateResponse)
def admin_update_actor_prompt(
    body: AdminActorPromptUpdateRequest,
    _current_user: AuthUserResponse = Depends(require_admin),
    provider=Depends(get_persistence_provider),
):
    _ = _current_user
    template = str(body.template or "").strip()
    validation = validate_actor_prompt_template(template)
    if not validation["valid"]:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "El prompt no es válido.",
                "validation": validation,
            },
        )
    provider.set_actor_prompt_template(template)
    return AdminActorPromptUpdateResponse(
        stored=True,
        template=template,
        source="custom",
        required_fields=[AdminActorPromptField(**item) for item in actor_prompt_required_fields()],
        validation=AdminActorPromptValidation(**validation),
    )


@admin_router.get(
    "/standard-templates",
    response_model=AdminStandardTemplateListResponse,
)
def admin_list_standard_templates(
    _current_user: AuthUserResponse = Depends(require_admin),
    provider=Depends(get_persistence_provider),
):
    _ = _current_user
    try:
        items = provider.list_standard_templates_admin()
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc))
    return AdminStandardTemplateListResponse(
        items=[AdminStandardTemplateListItem(**item) for item in items]
    )


@admin_router.post(
    "/standard-templates",
    response_model=AdminStandardTemplateResponse,
)
def admin_create_standard_template(
    body: AdminStandardTemplateCreateRequest,
    _current_user: AuthUserResponse = Depends(require_admin),
    provider=Depends(get_persistence_provider),
):
    _ = _current_user
    config_json = dict(body.config_json or {})
    payload_id = str(config_json.get("id") or body.id).strip()
    if payload_id != str(body.id).strip():
        raise HTTPException(status_code=422, detail="Template id must match config_json.id")
    try:
        item = provider.create_standard_template(
            body.id,
            version=body.version,
            active=body.active,
            config_json=config_json,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc))
    return AdminStandardTemplateResponse(**item)


@admin_router.post(
    "/standard-templates/generate",
    response_model=AdminStandardTemplateResponse,
)
def admin_generate_standard_template(
    body: AdminStandardTemplateGenerateRequest,
    _current_user: AuthUserResponse = Depends(require_admin),
    provider=Depends(get_persistence_provider),
):
    _ = _current_user
    seed_text = str(body.seed_text or "").strip()
    timeout_seconds = _template_generation_timeout_seconds()
    started_at = time.perf_counter()
    logger.info(
        "admin template generation started seed_chars=%s num_actors=%s timeout_seconds=%.1f",
        len(seed_text),
        body.num_actors,
        timeout_seconds,
    )
    try:
        generated_setup = create_guionista_agent().generate_setup(
            theme=seed_text,
            num_actors=body.num_actors,
            stream=False,
            timeout_seconds=timeout_seconds,
        )
        normalized_setup = validate_game_setup(
            generated_setup,
            source_name="generated_setup",
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except TimeoutError as exc:
        logger.warning(
            "admin template generation timed out after %.2f s",
            time.perf_counter() - started_at,
        )
        raise HTTPException(
            status_code=504,
            detail=(
                "La generacion de la historia supero el tiempo maximo permitido. "
                "Prueba con una semilla mas concreta o vuelve a intentarlo."
            ),
        ) from exc
    except Exception as exc:
        logger.exception("admin template generation failed")
        raise HTTPException(status_code=500, detail=str(exc))

    template_id = _suggest_unique_template_id(
        str(normalized_setup.get("titulo") or "historia_generada"),
        provider,
    )
    normalized_setup["id"] = template_id
    normalized_setup["version"] = str(body.version or "1.0.0").strip() or "1.0.0"
    normalized_setup["active"] = bool(body.active)
    logger.info(
        "admin template generation completed template_id=%s actors=%s duration_ms=%s",
        template_id,
        len(normalized_setup.get("actors") or []),
        int((time.perf_counter() - started_at) * 1000),
    )
    return AdminStandardTemplateResponse(
        id=template_id,
        version=normalized_setup["version"],
        active=bool(body.active),
        num_personajes=len(normalized_setup.get("actors") or []),
        config_json=normalized_setup,
    )


@admin_router.get(
    "/standard-templates/{template_id}",
    response_model=AdminStandardTemplateResponse,
)
def admin_get_standard_template(
    template_id: str,
    _current_user: AuthUserResponse = Depends(require_admin),
    provider=Depends(get_persistence_provider),
):
    _ = _current_user
    try:
        item = provider.get_standard_template(template_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Standard template not found")
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc))
    return AdminStandardTemplateResponse(**item)


@admin_router.put(
    "/standard-templates/{template_id}",
    response_model=AdminStandardTemplateResponse,
)
def admin_update_standard_template(
    template_id: str,
    body: AdminStandardTemplateUpdateRequest,
    _current_user: AuthUserResponse = Depends(require_admin),
    provider=Depends(get_persistence_provider),
):
    _ = _current_user
    config_json = dict(body.config_json or {})
    payload_id = str(config_json.get("id") or template_id).strip()
    if payload_id != str(template_id).strip():
        raise HTTPException(status_code=422, detail="Template id is immutable")
    try:
        item = provider.upsert_standard_template(
            template_id,
            version=body.version,
            active=body.active,
            config_json=config_json,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc))
    return AdminStandardTemplateResponse(**item)


@admin_router.delete(
    "/standard-templates/{template_id}",
    response_model=AdminStandardTemplateDeleteResponse,
)
def admin_delete_standard_template(
    template_id: str,
    _current_user: AuthUserResponse = Depends(require_admin),
    provider=Depends(get_persistence_provider),
):
    _ = _current_user
    try:
        provider.delete_standard_template(template_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Standard template not found")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc))
    return AdminStandardTemplateDeleteResponse(id=str(template_id).strip(), deleted=True)


@auth_router.post("/logout")
def logout(response: Response):
    response.delete_cookie(
        key=auth_cookie_name(),
        path="/",
        secure=auth_cookie_secure(),
        samesite=auth_cookie_samesite(),
    )
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
    era = (body.era or "").strip()
    topic = (body.topic or "").strip()
    style = (body.style or "").strip()
    has_structured_seed = bool(era or topic or style)
    use_env_theme = raw_theme == "" and not has_structured_seed and body.num_actors is None
    theme = os.getenv("GAME_THEME") if use_env_theme else (raw_theme or None)
    num_actors = body.num_actors if body.num_actors is not None else 3
    try:
        validated_seed = validate_custom_seed(
            theme=theme or None,
            era=era or None,
            topic=topic or None,
            style=style or None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    structured_theme = bool(
        validated_seed["era"] or validated_seed["topic"] or validated_seed["style"]
    )

    route_t0 = time.perf_counter()
    phases: dict[str, int] = {}
    session_id = ""
    phase_t0 = time.perf_counter()
    try:
        session_id, setup = engine.create_game(
            theme=None if structured_theme else (validated_seed["theme"] or None),
            era=validated_seed["era"] or None,
            topic=validated_seed["topic"] or None,
            style=validated_seed["style"] or None,
            num_actors=num_actors,
            max_turns=body.max_turns,
            username=current_user.username,
        )
        phases["create_game_and_warmup"] = int((time.perf_counter() - phase_t0) * 1000)
    except ValueError as exc:
        phases["create_game_and_warmup"] = int((time.perf_counter() - phase_t0) * 1000)
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
        raise HTTPException(status_code=422, detail=str(exc))
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
        characters = [_serialize_character_info(a) for a in actors]
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
        player_public_mission=setup.get("player_public_mission", ""),
        characters=characters,
        narrativa_inicial=setup.get("narrativa_inicial", ""),
    )


@router.get("/standard/list", response_model=StandardTemplateListResponse)
def list_standard_templates_endpoint(
    current_user: AuthUserResponse = Depends(get_current_user),
    provider=Depends(get_persistence_provider),
):
    """Lista templates estándar disponibles para creación rápida."""
    _ = current_user
    templates = [
        item for item in list_standard_templates(provider=provider) if bool(item.get("active", True))
    ]
    return StandardTemplateListResponse(
        templates=[StandardTemplateItem(**item) for item in templates]
    )


@router.post("/standard/start", response_model=StandardStartResponse)
def start_standard_game(
    body: StandardStartRequest,
    current_user: AuthUserResponse = Depends(get_current_user),
    engine=Depends(get_engine),
    provider=Depends(get_persistence_provider),
):
    """Crea partida copiando un template standard ya preconstruido."""
    route_t0 = time.perf_counter()
    phases: dict[str, int] = {}
    session_id = ""
    phase_t0 = time.perf_counter()
    try:
        loaded = load_standard_template(body.template_id, provider=provider)
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
    if not bool(loaded.get("active", True)):
        _emit_game_init_metrics(
            game_id="",
            user_id=current_user.id,
            username=current_user.username,
            mode="standard",
            status="error",
            total_ms=int((time.perf_counter() - route_t0) * 1000),
            phases=phases,
            status_message="Standard template inactive",
        )
        raise HTTPException(status_code=404, detail="Standard template not available")
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
        characters = [_serialize_character_info(a) for a in actors]
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
        player_public_mission=final_setup.get("player_public_mission", ""),
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
    messages_out = [
        MessageOut(**_serialize_message(m, player_name=current_user.username))
        for m in status.get("messages", [])
    ]
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
    try:
        validated_text = validate_user_message(body.text)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    def event_stream():
        for ev in engine.execute_turn_stream(
            body.session_id,
            validated_text,
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
                data = json.dumps(
                    {
                        "type": "message",
                        "message": _serialize_message(msg, player_name=current_user.username),
                    }
                )
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
    characters = [_serialize_character_info(c) for c in ctx.get("characters", [])]
    return ContextResponse(
        player_mission=ctx.get("player_mission", ""),
        player_public_mission=ctx.get("player_public_mission", ""),
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
