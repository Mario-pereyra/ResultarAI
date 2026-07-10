"""Test triggers for quota release notifications (d12, Section 3).

These are test-only use cases that simulate the emission that d16-cuotas-liberaciones
will perform in production. They exercise the full emit_notification path end-to-end.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from resultarai.adapters.persistence_postgres.models import User
from resultarai.app.use_cases.notifications.emit import emit_notification


def request_quota_release_test_trigger(
    db: DbSession,
    requestor_id: UUID,
    quota_name: str,
    current_consumption: float,
) -> list[Any]:
    """Simula una solicitud de liberación de cuota y notifica a todos los Admin.

    Returns the list of created notifications.
    """
    requestor = db.get(User, requestor_id)
    if requestor is None:
        raise ValueError(f"Usuario solicitante no encontrado: {requestor_id}")

    # Find all active admins
    admins = db.execute(
        select(User).where(User.role == "admin", User.status == "active")
    ).scalars().all()

    notifications = []
    for admin in admins:
        notif = emit_notification(
            db=db,
            notification_type="quota_release_requested",
            recipient_id=admin.id,
            payload={
                "requestor_username": requestor.username,
                "quota_name": quota_name,
                "current_consumption": current_consumption,
            },
            deep_link="/administracion/cuotas",
        )
        notifications.append(notif)

    return notifications


def resolve_quota_release_test_trigger(
    db: DbSession,
    requestor_id: UUID,
    decision: str,
    quota_name: str,
    reason: str | None = None,
) -> Any:
    """Simula la resolución de una solicitud de liberación y notifica al solicitante.

    Returns the created notification.
    """
    return emit_notification(
        db=db,
        notification_type="quota_release_resolved",
        recipient_id=requestor_id,
        payload={
            "decision": decision,
            "quota_name": quota_name,
            "reason": reason,
        },
        deep_link="/mi-espacio/consumo",
    )
