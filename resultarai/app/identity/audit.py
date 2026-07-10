"""Auditoría de identidad append-only (d11, sección 6)."""

from __future__ import annotations

import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session as DbSession

from resultarai.adapters.persistence_postgres.models import IdentityAuditEvent, get_utc_now

__all__ = ["log_identity_audit_event"]


def log_identity_audit_event(
    db: DbSession,
    event_type: str,
    actor_user_id: UUID | None,
    target_ref: str | None,
    details: dict[str, Any] | None = None,
    *,
    now: datetime.datetime | None = None,
) -> IdentityAuditEvent:
    """Registra exactamente un evento en la tabla append-only `identity_audit_events`.

    No contiene secretos (como contraseñas, secretos TOTP, o tokens).
    """
    event = IdentityAuditEvent(
        event_type=event_type,
        actor_user_id=actor_user_id,
        target_ref=target_ref,
        timestamp=now or get_utc_now(),
        details=details or {},
    )
    db.add(event)
    db.flush()
    return event
