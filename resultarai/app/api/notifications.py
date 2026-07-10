"""FastAPI router para endpoints de notificaciones /api/notifications (d12, sección 4)."""

from __future__ import annotations

from datetime import timedelta
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from resultarai.adapters.persistence_postgres.models import User
from resultarai.adapters.persistence_postgres.notifications import PostgresNotificationRepository
from resultarai.app.identity import (
    get_db,
    require_completed_wizard,
)

router = APIRouter(prefix="/api/notifications", tags=["notifications"])

# Default retention window (90 days). In production this would come from instance config.
_DEFAULT_RETENTION = timedelta(days=90)

_repo = PostgresNotificationRepository()


class NotificationResponse(BaseModel):
    id: str
    type: str
    payload: dict[str, Any]
    deep_link: str | None
    read: bool
    created_at: str


class PaginatedNotificationsResponse(BaseModel):
    items: list[NotificationResponse]
    total: int
    page: int
    has_next: bool


class UnreadCountResponse(BaseModel):
    count: int


def _to_response(n: Any) -> NotificationResponse:
    return NotificationResponse(
        id=str(n.id),
        type=n.type,
        payload=n.payload,
        deep_link=n.deep_link,
        read=n.read_at is not None,
        created_at=n.created_at.isoformat(),
    )


@router.get("")
def list_notifications(
    db: Annotated[DbSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_completed_wizard)],
    status: str = "all",
    page: int = 1,
    page_size: int = 20,
) -> PaginatedNotificationsResponse:
    """Lista paginada de notificaciones propias, filtrada por estado."""
    if status not in ("all", "unread", "read"):
        raise HTTPException(status_code=400, detail="Estado inválido. Usar: all, unread, read")
    if page < 1:
        page = 1
    if page_size < 1 or page_size > 100:
        page_size = 20

    offset = (page - 1) * page_size

    # Get one extra to determine has_next
    items = _repo.list_notifications(
        db=db,
        recipient_id=current_user.id,
        status=status if status != "all" else None,
        limit=page_size + 1,
        offset=offset,
        retention_window=_DEFAULT_RETENTION,
    )

    has_next = len(items) > page_size
    if has_next:
        items = items[:page_size]

    # Count total for this status
    if status == "unread":
        total = _repo.count_unread(db, recipient_id=current_user.id, retention_window=_DEFAULT_RETENTION)
    elif status == "read":
        all_items = _repo.list_notifications(
            db=db, recipient_id=current_user.id, status="read",
            limit=10000, offset=0, retention_window=_DEFAULT_RETENTION,
        )
        total = len(all_items)
    else:
        all_items = _repo.list_notifications(
            db=db, recipient_id=current_user.id, status=None,
            limit=10000, offset=0, retention_window=_DEFAULT_RETENTION,
        )
        total = len(all_items)

    return PaginatedNotificationsResponse(
        items=[_to_response(n) for n in items],
        total=total,
        page=page,
        has_next=has_next,
    )


@router.get("/unread-count")
def unread_count(
    db: Annotated[DbSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_completed_wizard)],
) -> UnreadCountResponse:
    """Devuelve la cantidad de notificaciones no leídas del usuario autenticado."""
    count = _repo.count_unread(
        db=db,
        recipient_id=current_user.id,
        retention_window=_DEFAULT_RETENTION,
    )
    return UnreadCountResponse(count=count)


@router.post("/{notification_id}/read")
def mark_notification_read(
    notification_id: UUID,
    db: Annotated[DbSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_completed_wizard)],
) -> dict[str, str]:
    """Marca una notificación como leída si pertenece al usuario autenticado."""
    success = _repo.mark_read(
        db=db,
        notification_id=notification_id,
        recipient_id=current_user.id,
    )
    if not success:
        raise HTTPException(status_code=404, detail="Notificación no encontrada.")
    return {"status": "success"}


@router.post("/read-all")
def mark_all_read(
    db: Annotated[DbSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_completed_wizard)],
) -> dict[str, Any]:
    """Marca todas las notificaciones del usuario como leídas."""
    count = _repo.mark_all_read(db=db, recipient_id=current_user.id)
    return {"status": "success", "count": count}
