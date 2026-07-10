"""Dependencies FastAPI de identidad: usuario actual y rol (d11, tarea 2.3).

``get_current_user`` resuelve el usuario **exclusivamente** desde la cookie de
sesión validada. No mira el body, la query ni los path params: cualquier
``userId`` que llegue por ahí se ignora por construcción, no por una comprobación
que pueda olvidarse (spec: "userId siempre derivado de la sesión"). Este es el
patrón que el resto de la plataforma (d12-d21) debe replicar.

``get_db`` y ``get_session_config`` son *proveedores* inyectables que la
composición real (sección 3) o los tests sobreescriben con
``app.dependency_overrides``. Así estos dependencies no dependen de globals ni de
cómo se obtiene la sesión de base en cada deployable.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session as DbSession

from resultarai.adapters.persistence_postgres.models import User
from resultarai.app.identity.sessions import (
    SESSION_COOKIE,
    SessionConfig,
    validate_session,
)

__all__ = [
    "get_current_user",
    "get_db",
    "get_session_config",
    "require_admin",
    "require_completed_wizard",
]


def get_db() -> Iterator[DbSession]:
    """Proveedor de sesión de base; la composición real lo sobreescribe.

    Sin override falla explícitamente en vez de devolver ``None``: obliga a la
    sección 3 (o al test) a inyectar cómo se obtiene la sesión de Postgres.
    """
    raise NotImplementedError(
        "get_db debe sobreescribirse vía app.dependency_overrides con la sesión "
        "de base concreta del deployable."
    )


def get_session_config() -> SessionConfig:
    """Proveedor de configuración de sesión (por defecto, desde entorno)."""
    return SessionConfig.from_env()


def get_current_user(
    request: Request,
    db: Annotated[DbSession, Depends(get_db)],
    config: Annotated[SessionConfig, Depends(get_session_config)],
) -> User:
    """Devuelve el ``User`` de la sesión validada, o lanza 401.

    Lee **solo** la cookie de sesión. Rechaza (401) si falta, si no valida (firma
    corrupta, revocada, expirada) o si la cuenta ya no está activa.
    """
    cookie_value = request.cookies.get(SESSION_COOKIE)
    if not cookie_value:
        raise HTTPException(status_code=401, detail="No autenticado.")

    auth = validate_session(db, cookie_value, config)
    if auth is None:
        raise HTTPException(status_code=401, detail="Sesión inválida o expirada.")

    user = db.get(User, auth.user_id)
    if user is None or user.status != "active":
        raise HTTPException(status_code=401, detail="Sesión inválida o expirada.")
    return user


def require_completed_wizard(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[DbSession, Depends(get_db)],
) -> User:
    """Exige que el usuario haya completado el wizard de primer acceso y acuerdo.

    Lanza 403 con 'AGREEMENT_PENDING' si falta firmar el acuerdo de uso,
    o 'WIZARD_PENDING' si falta cambiar contraseña o enrolar TOTP.
    """
    from resultarai.app.use_cases.identity import get_wizard_status

    status = get_wizard_status(db, user)
    if status["pending_steps"]:
        if status["agreement_acceptance_pending"]:
            raise HTTPException(status_code=403, detail="AGREEMENT_PENDING")
        raise HTTPException(status_code=403, detail="WIZARD_PENDING")
    return user


def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    """Exige rol Admin; lanza 403 en cualquier otro rol."""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Se requiere rol Admin.")
    return user
