"""Dependencias FastAPI: motor de partida singleton."""

from fastapi import HTTPException, Request, status

from .auth import auth_required, get_user_by_username, username_from_token, auth_cookie_name
from .schemas import AuthUserResponse
from src.core import create_engine
from src.persistence import create_persistence_provider

_engine = None
_persistence = None


def get_persistence_provider():
    global _persistence
    if _persistence is None:
        _persistence = create_persistence_provider()
    return _persistence


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(persistence_provider=get_persistence_provider())
    return _engine


def get_current_user(request: Request) -> AuthUserResponse:
    """Devuelve usuario autenticado desde cookie JWT."""
    token = request.cookies.get(auth_cookie_name(), "")
    username = username_from_token(token)
    if username:
        user = get_user_by_username(username)
        if user and user.get("is_active", True):
            return AuthUserResponse(
                id=str(user.get("id", "")),
                username=str(user.get("username", "")),
                is_active=bool(user.get("is_active", True)),
            )

    if not auth_required():
        fallback = get_user_by_username("usuario") or {"id": "fallback", "username": "usuario", "is_active": True}
        return AuthUserResponse(
            id=str(fallback.get("id", "fallback")),
            username=str(fallback.get("username", "usuario")),
            is_active=bool(fallback.get("is_active", True)),
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
    )
