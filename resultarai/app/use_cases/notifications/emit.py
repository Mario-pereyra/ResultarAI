"""Notification emission use case (d12, task 2.2)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session as DbSession
from resultarai.adapters.persistence_postgres.notifications import PostgresNotificationRepository
from resultarai.app.use_cases.notifications.types import NOTIFICATION_TYPES


def emit_notification(
    db: DbSession,
    notification_type: str,
    recipient_id: UUID | str,
    payload: dict[str, Any],
    deep_link: str | None = None,
) -> Any:
    """Valida y emite una notificación a un destinatario, persistiendo su estado."""
    # Convert recipient_id to UUID
    if isinstance(recipient_id, str):
        try:
            r_id = UUID(recipient_id)
        except ValueError as e:
            raise ValueError(f"ID de destinatario inválido: {recipient_id}") from e
    else:
        r_id = recipient_id

    # 1. Validar que el tipo esté registrado
    if notification_type not in NOTIFICATION_TYPES:
        raise ValueError(f"Tipo de notificación no registrado: {notification_type}")

    type_info = NOTIFICATION_TYPES[notification_type]

    # 2. Validar payload contra el schema
    try:
        validated_payload = type_info.payload_schema(**payload).model_dump()
    except Exception as e:
        raise ValueError(f"Payload inválido para el tipo {notification_type}: {e}") from e

    # 3. Validar rol/destinatario mediante el recipient_resolver
    if not type_info.recipient_resolver(db, r_id):
        raise ValueError(
            f"El destinatario {recipient_id} no cumple con los requisitos del rol para {notification_type}"
        )

    # 4. Persistir la notificación
    repo = PostgresNotificationRepository()
    return repo.create(
        db=db,
        recipient_id=r_id,
        notification_type=notification_type,
        payload=validated_payload,
        deep_link=deep_link,
    )
