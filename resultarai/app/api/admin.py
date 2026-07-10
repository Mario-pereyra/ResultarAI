"""FastAPI router para endpoints administrativos /api/admin (d11, secciones 4 y 5)."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from resultarai.adapters.persistence_postgres.models import User, Group, GroupMember
from resultarai.app.identity import (
    get_db,
    require_admin,
)
from resultarai.app.use_cases.identity import (
    admin_add_group_member,
    admin_change_role,
    admin_create_group,
    admin_create_user,
    admin_publish_agreement,
    admin_remove_group_member,
    admin_require_totp,
    admin_reset_password,
    admin_revoke_user_sessions,
    admin_suspend_user,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=1)
    display_name: str = Field(..., min_length=1)
    email: str | None = None
    role: str = Field(..., min_length=1)
    group_id: UUID | None = None


class UserRoleRequest(BaseModel):
    role: str = Field(..., min_length=1)


class UserRequireTotpRequest(BaseModel):
    require: bool


class UserSessionsRevokeRequest(BaseModel):
    session_id: str | None = None


class CreateGroupRequest(BaseModel):
    name: str = Field(..., min_length=1)
    description: str | None = None


class AddGroupMemberRequest(BaseModel):
    user_id: UUID


class PublishAgreementRequest(BaseModel):
    text: str = Field(..., min_length=1)


@router.get("/users")
def list_users(
    db: Annotated[DbSession, Depends(get_db)],
    current_admin: Annotated[User, Depends(require_admin)],
) -> list[dict[str, Any]]:
    """Devuelve la lista funcional mínima de todas las cuentas."""
    stmt = select(User).order_by(User.username.asc())
    users = db.execute(stmt).scalars().all()
    return [
        {
            "id": str(u.id),
            "username": u.username,
            "display_name": u.display_name,
            "email": u.email,
            "role": u.role,
            "status": u.status,
            "totp_required": u.totp_required,
        }
        for u in users
    ]


@router.post("/users")
def create_user(
    payload: CreateUserRequest,
    db: Annotated[DbSession, Depends(get_db)],
    current_admin: Annotated[User, Depends(require_admin)],
) -> dict[str, Any]:
    """Crea una nueva cuenta de usuario y devuelve la contraseña temporal una única vez."""
    res = admin_create_user(
        db=db,
        admin_user=current_admin,
        username=payload.username,
        display_name=payload.display_name,
        email=payload.email,
        role=payload.role,
        group_id=payload.group_id,
    )
    if res["status"] == "error":
        raise HTTPException(status_code=400, detail=res["error"])
    return {
        "status": "success",
        "user_id": res["user_id"],
        "temp_password": res["temp_password"],
    }


@router.post("/users/{user_id}/suspend")
def suspend_user(
    user_id: UUID,
    db: Annotated[DbSession, Depends(get_db)],
    current_admin: Annotated[User, Depends(require_admin)],
) -> dict[str, Any]:
    """Suspende una cuenta de usuario y revoca todas sus sesiones activas de inmediato."""
    res = admin_suspend_user(db=db, admin_user=current_admin, user_id=user_id)
    if res["status"] == "error":
        raise HTTPException(status_code=400, detail=res["error"])
    return {"status": "success"}


@router.post("/users/{user_id}/role")
def change_user_role(
    user_id: UUID,
    payload: UserRoleRequest,
    db: Annotated[DbSession, Depends(get_db)],
    current_admin: Annotated[User, Depends(require_admin)],
) -> dict[str, Any]:
    """Actualiza el rol de una cuenta (prohibido a sí mismo)."""
    res = admin_change_role(
        db=db,
        admin_user=current_admin,
        user_id=user_id,
        role=payload.role,
    )
    if res["status"] == "error":
        raise HTTPException(status_code=400, detail=res["error"])
    return {"status": "success"}


@router.post("/users/{user_id}/reset-password")
def reset_user_password(
    user_id: UUID,
    db: Annotated[DbSession, Depends(get_db)],
    current_admin: Annotated[User, Depends(require_admin)],
) -> dict[str, Any]:
    """Resetea la contraseña de un usuario, revoca sesiones y fuerza el wizard."""
    res = admin_reset_password(db=db, admin_user=current_admin, user_id=user_id)
    if res["status"] == "error":
        raise HTTPException(status_code=400, detail=res["error"])
    return {
        "status": "success",
        "temp_password": res["temp_password"],
    }


@router.post("/users/{user_id}/sessions/revoke")
def revoke_user_sessions(
    user_id: UUID,
    payload: UserSessionsRevokeRequest,
    db: Annotated[DbSession, Depends(get_db)],
    current_admin: Annotated[User, Depends(require_admin)],
) -> dict[str, Any]:
    """Revoca una sesión individual o todas las sesiones de una cuenta."""
    res = admin_revoke_user_sessions(
        db=db,
        admin_user=current_admin,
        user_id=user_id,
        session_id=payload.session_id,
    )
    if res["status"] == "error":
        raise HTTPException(status_code=400, detail=res["error"])
    return {"status": "success"}


@router.post("/users/{user_id}/require-totp")
def require_user_totp(
    user_id: UUID,
    payload: UserRequireTotpRequest,
    db: Annotated[DbSession, Depends(get_db)],
    current_admin: Annotated[User, Depends(require_admin)],
) -> dict[str, Any]:
    """Enfuerza o deshabilita la obligatoriedad de TOTP para una cuenta Técnico/Funcional."""
    res = admin_require_totp(
        db=db,
        admin_user=current_admin,
        user_id=user_id,
        require=payload.require,
    )
    if res["status"] == "error":
        raise HTTPException(status_code=400, detail=res["error"])
    return {"status": "success"}


@router.get("/groups")
def list_groups(
    db: Annotated[DbSession, Depends(get_db)],
    current_admin: Annotated[User, Depends(require_admin)],
) -> list[dict[str, Any]]:
    """Devuelve la lista de grupos con sus miembros."""
    stmt = select(Group).order_by(Group.name.asc())
    groups = db.execute(stmt).scalars().all()
    
    result = []
    for g in groups:
        member_stmt = select(GroupMember).where(GroupMember.group_id == g.id)
        members = db.execute(member_stmt).scalars().all()
        result.append({
            "id": str(g.id),
            "name": g.name,
            "description": g.description,
            "member_ids": [str(m.user_id) for m in members]
        })
    return result


@router.post("/groups")
def create_group(
    payload: CreateGroupRequest,
    db: Annotated[DbSession, Depends(get_db)],
    current_admin: Annotated[User, Depends(require_admin)],
) -> dict[str, Any]:
    """Crea un grupo de usuarios."""
    res = admin_create_group(
        db=db,
        admin_user=current_admin,
        name=payload.name,
        description=payload.description,
    )
    if res["status"] == "error":
        raise HTTPException(status_code=400, detail=res["error"])
    return {
        "status": "success",
        "group_id": res["group_id"],
    }


@router.post("/groups/{group_id}/members")
def add_group_member(
    group_id: UUID,
    payload: AddGroupMemberRequest,
    db: Annotated[DbSession, Depends(get_db)],
    current_admin: Annotated[User, Depends(require_admin)],
) -> dict[str, Any]:
    """Agrega un usuario a un grupo."""
    res = admin_add_group_member(
        db=db,
        admin_user=current_admin,
        group_id=group_id,
        user_id=payload.user_id,
    )
    if res["status"] == "error":
        raise HTTPException(status_code=400, detail=res["error"])
    return {"status": "success"}


@router.delete("/groups/{group_id}/members/{user_id}")
def remove_group_member(
    group_id: UUID,
    user_id: UUID,
    db: Annotated[DbSession, Depends(get_db)],
    current_admin: Annotated[User, Depends(require_admin)],
) -> dict[str, Any]:
    """Quita a un usuario de un grupo."""
    res = admin_remove_group_member(
        db=db,
        admin_user=current_admin,
        group_id=group_id,
        user_id=user_id,
    )
    if res["status"] == "error":
        raise HTTPException(status_code=400, detail=res["error"])
    return {"status": "success"}


@router.post("/agreement/publish")
def publish_agreement_version(
    payload: PublishAgreementRequest,
    db: Annotated[DbSession, Depends(get_db)],
    current_admin: Annotated[User, Depends(require_admin)],
) -> dict[str, Any]:
    """Publica una nueva versión del acuerdo de uso del sistema."""
    res = admin_publish_agreement(
        db=db,
        admin_user=current_admin,
        text=payload.text,
    )
    if res["status"] == "error":
        raise HTTPException(status_code=400, detail=res["error"])
    return {
        "status": "success",
        "version_id": res["version_id"],
        "version_number": res["version_number"],
    }
