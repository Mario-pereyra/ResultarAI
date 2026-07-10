"""Inicialización de la API FastAPI y factory create_app (d11, sección 3)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from sqlalchemy.orm import Session as DbSession

from resultarai.adapters.persistence_postgres.connection import get_db_session
from resultarai.adapters.persistence_postgres.models import User
from resultarai.app.api.admin import router as admin_router
from resultarai.app.api.auth import router as auth_router
from resultarai.app.api.me import router as me_router
from resultarai.app.identity import (
    SESSION_COOKIE,
    SessionConfig,
    get_db,
    get_session_config,
    require_csrf,
    validate_session,
)

__all__ = ["create_app"]


def csrf_guard(request: Request) -> None:
    """Enfuerza CSRF doble envío en todas las mutaciones excepto login y totp/verify."""
    if request.method in ("POST", "PUT", "DELETE", "PATCH"):
        path = request.url.path.rstrip("/")
        if path not in ("/api/auth/login", "/api/auth/totp/verify"):
            require_csrf(request)


def wizard_guard(
    request: Request,
    db: Annotated[DbSession, Depends(get_db)],
    session_config: Annotated[SessionConfig, Depends(get_session_config)],
) -> None:
    """Bloquea cualquier ruta fuera de auth/wizard/agreement si el usuario
    tiene pasos pendientes.
    """
    path = request.url.path.rstrip("/")
    if path in (
        "/api/auth/login",
        "/api/auth/totp/verify",
        "/api/auth/logout",
        "/api/auth/password",
        "/api/me/totp/enroll",
        "/api/me/totp/enable",
        "/api/me/wizard/status",
        "/api/me/wizard/preferences",
        "/api/me/agreement/status",
        "/api/me/agreement/accept",
    ):
        return

    cookie_value = request.cookies.get(SESSION_COOKIE)
    if not cookie_value:
        return

    auth = validate_session(db, cookie_value, session_config)
    if not auth:
        return

    user = db.get(User, auth.user_id)
    if not user or user.status != "active":
        return

    from resultarai.app.use_cases.identity import get_wizard_status

    status = get_wizard_status(db, user)
    if status["pending_steps"]:
        if status["agreement_acceptance_pending"]:
            raise HTTPException(status_code=403, detail="AGREEMENT_PENDING")
        raise HTTPException(status_code=403, detail="WIZARD_PENDING")


def get_db_override() -> Iterator[DbSession]:
    """Generador inyectable para obtener la sesión de base de datos de Postgres."""
    with get_db_session() as session:
        yield session


def create_app() -> FastAPI:
    """Factory que construye e inicializa la aplicación FastAPI de la plataforma."""
    app = FastAPI(
        title="ResultarAI API",
        version="0.1.0",
        dependencies=[Depends(csrf_guard), Depends(wizard_guard)],
    )

    # Registro de routers
    app.include_router(auth_router)
    app.include_router(me_router)
    app.include_router(admin_router)

    # Inyección de dependencias
    app.dependency_overrides[get_db] = get_db_override

    return app
