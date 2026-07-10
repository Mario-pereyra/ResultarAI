"""FastAPI router para endpoints personales /me (d11, secciones 3 y 5)."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DbSession

from resultarai.adapters.persistence_postgres.models import User
from resultarai.app.identity import (
    TotpConfig,
    get_current_user,
    get_db,
)
from resultarai.app.use_cases.identity import (
    accept_agreement,
    disable_totp_secret,
    enable_totp_secret,
    enroll_totp_secret,
    get_agreement_status,
    get_wizard_status,
    set_wizard_preferences,
)

router = APIRouter(prefix="/api/me", tags=["me"])


class PreferencesRequest(BaseModel):
    preferred_language: str = Field(..., min_length=2, max_length=10)
    preferred_theme: str = Field(..., min_length=2, max_length=20)


class TotpEnableRequest(BaseModel):
    code: str = Field(..., min_length=1)


class AgreementAcceptRequest(BaseModel):
    version_id: UUID


@router.get("/wizard/status")
def wizard_status(
    db: Annotated[DbSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Devuelve los pasos del wizard pendientes para el usuario actual."""
    return get_wizard_status(db, current_user)


@router.post("/wizard/preferences")
def wizard_preferences(
    payload: PreferencesRequest,
    db: Annotated[DbSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Guarda el idioma y el tema elegidos en el wizard."""
    return set_wizard_preferences(
        db=db,
        user=current_user,
        preferred_language=payload.preferred_language,
        preferred_theme=payload.preferred_theme,
    )


@router.post("/totp/enroll")
def totp_enroll(
    db: Annotated[DbSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Genera e ingresa un secreto TOTP cifrado temporal y devuelve los códigos de respaldo."""
    totp_config = TotpConfig.from_env()
    return enroll_totp_secret(db, current_user, totp_config)


@router.post("/totp/enable")
def totp_enable(
    payload: TotpEnableRequest,
    db: Annotated[DbSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Confirma el secreto TOTP generado anteriormente e introduce la obligatoriedad voluntaria."""
    totp_config = TotpConfig.from_env()
    res = enable_totp_secret(db, current_user, payload.code, totp_config)
    if res["status"] == "error":
        raise HTTPException(status_code=400, detail=res["error"])
    return {"status": "success"}


@router.post("/totp/disable")
def totp_disable(
    db: Annotated[DbSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Desactiva TOTP de la cuenta personal, siempre que no haya sido forzado por el Admin."""
    res = disable_totp_secret(db, current_user)
    if res["status"] == "error":
        raise HTTPException(status_code=400, detail=res["error"])
    return {"status": "success"}


@router.get("/agreement/status")
def agreement_status(
    db: Annotated[DbSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Devuelve el estado de la firma del acuerdo de uso del usuario actual."""
    return get_agreement_status(db, current_user)


@router.post("/agreement/accept")
def agreement_accept(
    payload: AgreementAcceptRequest,
    db: Annotated[DbSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Registra la aceptación del acuerdo de uso vigente para el usuario actual."""
    res = accept_agreement(db, current_user, payload.version_id)
    if res["status"] == "error":
        raise HTTPException(status_code=400, detail=res["error"])
    return {"status": "success"}
