"""NotificationRepository Protocol definition (d12)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.orm import Session as DbSession

from resultarai.adapters.persistence_postgres.models import Notification


class NotificationRepository(Protocol):
    """Protocol for persisting and managing notifications."""

    def create(
        self,
        db: DbSession,
        recipient_id: UUID,
        notification_type: str,
        payload: dict[str, Any],
        deep_link: str | None = None,
    ) -> Notification:
        """Create and persist a new notification."""
        ...

    def list_notifications(
        self,
        db: DbSession,
        recipient_id: UUID,
        status: str | None = None,  # "unread", "read", or "all"
        limit: int = 20,
        offset: int = 0,
        retention_window: timedelta | None = None,
    ) -> list[Notification]:
        """List notifications for a recipient, filtered by status, ordered desc by created_at."""
        ...

    def count_unread(
        self,
        db: DbSession,
        recipient_id: UUID,
        retention_window: timedelta | None = None,
    ) -> int:
        """Count unread notifications for a recipient, respecting retention window."""
        ...

    def mark_read(
        self,
        db: DbSession,
        notification_id: UUID,
        recipient_id: UUID,
        now: datetime | None = None,
    ) -> bool:
        """Mark a specific notification as read. Returns True if found and updated."""
        ...

    def mark_all_read(
        self,
        db: DbSession,
        recipient_id: UUID,
        now: datetime | None = None,
    ) -> int:
        """Mark all notifications of the recipient as read. Returns number of updated rows."""
        ...

    def get_notification(
        self,
        db: DbSession,
        notification_id: UUID,
        recipient_id: UUID,
    ) -> Notification | None:
        """Get a specific notification if it belongs to the recipient."""
        ...
