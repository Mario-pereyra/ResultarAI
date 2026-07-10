"""FastAPI router para endpoints de autenticación (d11, sección 3)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DbSession

from resultarai.adapters.persistence_postgres.models import User
from resultarai.app.identity import (
    RateLimitConfig,
    SessionConfig,
    TotpConfig,
    clear_session_cookie,
    get_current_user,
    get_db,
    get_session_config,
    revoke_session,
    set_csrf_cookie,
    set_session_cookie,
    validate_session,
)
from resultarai.app.use_cases.identity import (
    change_password,
    login_user,
    verify_totp_code,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class TotpVerifyRequest(BaseModel):
    pending_token: str
    code: str = Field(..., min_length=1)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=1)


@router.post("/login")
def login(
    request: Request,
    response: Response,
    payload: LoginRequest,
    db: Annotated[DbSession, Depends(get_db)],
    session_config: Annotated[SessionConfig, Depends(get_session_config)],
) -> dict[str, Any]:
    """Inicia sesión con usuario y contraseña, derivando el segundo factor si corresponde."""
    rate_limit_config = RateLimitConfig.from_env()
    totp_config = TotpConfig.from_env()

    origin = request.client.host if request.client else "unknown"

    res = login_user(
        db=db,
        username=payload.username,
        password=payload.password,
        origin=origin,
        session_config=session_config,
        rate_limit_config=rate_limit_config,
        totp_config=totp_config,
    )

    if res["status"] == "locked":
        raise HTTPException(status_code=400, detail="ACCOUNT_LOCKED")
    elif res["status"] == "invalid_credentials":
        raise HTTPException(status_code=400, detail="Credenciales inválidas.")
    elif res["status"] == "pending_totp":
        return {
            "status": "pending_totp",
            "pending_token": res["pending_token"],
        }

    # Success: set cookies
    set_session_cookie(response, res["created_session"].cookie_value, session_config)
    set_csrf_cookie(response, res["csrf_token"], secure=session_config.cookie_secure)
    return {"status": "success"}


@router.post("/totp/verify")
def totp_verify(
    request: Request,
    response: Response,
    payload: TotpVerifyRequest,
    db: Annotated[DbSession, Depends(get_db)],
    session_config: Annotated[SessionConfig, Depends(get_session_config)],
) -> dict[str, Any]:
    """Verifica el segundo paso TOTP y genera la sesión completa si es exitoso."""
    rate_limit_config = RateLimitConfig.from_env()
    totp_config = TotpConfig.from_env()

    origin = request.client.host if request.client else "unknown"

    res = verify_totp_code(
        db=db,
        pending_token=payload.pending_token,
        code=payload.code,
        origin=origin,
        session_config=session_config,
        rate_limit_config=rate_limit_config,
        totp_config=totp_config,
    )

    if res["status"] == "locked":
        raise HTTPException(status_code=400, detail="ACCOUNT_LOCKED")
    elif res["status"] == "invalid_token":
        raise HTTPException(status_code=400, detail="Token de verificación inválido o expirado.")
    elif res["status"] == "invalid_code":
        raise HTTPException(status_code=400, detail="Código inválido.")

    # Success: set cookies
    set_session_cookie(response, res["created_session"].cookie_value, session_config)
    set_csrf_cookie(response, res["csrf_token"], secure=session_config.cookie_secure)
    return {"status": "success"}


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    db: Annotated[DbSession, Depends(get_db)],
    session_config: Annotated[SessionConfig, Depends(get_session_config)],
    current_user: Annotated[User, Depends(get_current_user)],  # exige estar logueado
) -> dict[str, Any]:
    """Revoca la sesión del lado del servidor e invalida la cookie del cliente."""
    cookie_value = request.cookies.get("resultarai_session")
    if cookie_value:
        auth = validate_session(db, cookie_value, session_config)
        if auth:
            revoke_session(db, auth.id)

    clear_session_cookie(response)
    return {"status": "success"}


@router.post("/password")
def change_own_password(
    request: Request,
    payload: PasswordChangeRequest,
    db: Annotated[DbSession, Depends(get_db)],
    session_config: Annotated[SessionConfig, Depends(get_session_config)],
    current_user: Annotated[User, Depends(get_current_user)],  # permite cambiarlo dentro del wizard
) -> dict[str, Any]:
    """Cambia la propia contraseña, validando la actual y la política de complejidad."""
    cookie_value = request.cookies.get("resultarai_session")

    res = change_password(
        db=db,
        user=current_user,
        current_password=payload.current_password,
        new_password=payload.new_password,
        current_cookie_value=cookie_value,
        session_config=session_config,
    )

    if res["status"] == "error":
        raise HTTPException(status_code=400, detail=res["error"])
    elif res["status"] == "policy_error":
        raise HTTPException(
            status_code=400,
            detail={
                "message": "La contraseña no cumple la política.",
                "violations": res["violations"],
            },
        )

    return {"status": "success"}
