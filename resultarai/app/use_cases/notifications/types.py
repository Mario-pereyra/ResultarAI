"""Notification types registry (d12, task 2.1)."""

from __future__ import annotations

from typing import Callable
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session as DbSession


class QuotaReleaseRequestedPayload(BaseModel):
    requestor_username: str
    quota_name: str
    current_consumption: float


class QuotaReleaseResolvedPayload(BaseModel):
    decision: str = Field(..., description="approved or denied")
    quota_name: str
    reason: str | None = None


class HitlApprovalPendingPayload(BaseModel):
    approval_request_id: str
    risk_level: str


class HitlCardExpiredPayload(BaseModel):
    approval_request_id: str


class WorkflowFinishedPayload(BaseModel):
    workflow_run_id: str
    status: str


class CatalogNewsPayload(BaseModel):
    agent_name: str
    description: str


def resolve_admin_recipient(db: DbSession, recipient_id: UUID) -> bool:
    """Verifica que el destinatario sea un Administrador activo."""
    from resultarai.adapters.persistence_postgres.models import User
    user = db.get(User, recipient_id)
    return user is not None and user.role == "admin" and user.status == "active"


def resolve_any_recipient(db: DbSession, recipient_id: UUID) -> bool:
    """Verifica que el destinatario sea cualquier usuario activo."""
    from resultarai.adapters.persistence_postgres.models import User
    user = db.get(User, recipient_id)
    return user is not None and user.status == "active"


class NotificationTypeInfo(BaseModel):
    type_name: str
    payload_schema: type[BaseModel]
    recipient_resolver: Callable[[DbSession, UUID], bool]
    implemented: bool

    model_config = ConfigDict(arbitrary_types_allowed=True)


NOTIFICATION_TYPES: dict[str, NotificationTypeInfo] = {
    "quota_release_requested": NotificationTypeInfo(
        type_name="quota_release_requested",
        payload_schema=QuotaReleaseRequestedPayload,
        recipient_resolver=resolve_admin_recipient,
        implemented=True,
    ),
    "quota_release_resolved": NotificationTypeInfo(
        type_name="quota_release_resolved",
        payload_schema=QuotaReleaseResolvedPayload,
        recipient_resolver=resolve_any_recipient,
        implemented=True,
    ),
    "hitl_approval_pending": NotificationTypeInfo(
        type_name="hitl_approval_pending",
        payload_schema=HitlApprovalPendingPayload,
        recipient_resolver=resolve_admin_recipient,
        implemented=False,
    ),
    "hitl_card_expired": NotificationTypeInfo(
        type_name="hitl_card_expired",
        payload_schema=HitlCardExpiredPayload,
        recipient_resolver=resolve_any_recipient,
        implemented=False,
    ),
    "workflow_finished": NotificationTypeInfo(
        type_name="workflow_finished",
        payload_schema=WorkflowFinishedPayload,
        recipient_resolver=resolve_any_recipient,
        implemented=False,
    ),
    "catalog_news": NotificationTypeInfo(
        type_name="catalog_news",
        payload_schema=CatalogNewsPayload,
        recipient_resolver=resolve_any_recipient,
        implemented=False,
    ),
}
