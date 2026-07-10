"""Postgres implementation of NotificationRepository (d12)."""

from __future__ import annotations

import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session as DbSession

from resultarai.adapters.persistence_postgres.models import Notification, get_utc_now


class PostgresNotificationRepository:
    """Postgres implementation of NotificationRepository.

    Satisface estructuralmente el Protocol ``NotificationRepository`` de
    ``resultarai/app/use_cases/notifications/ports.py`` sin heredarlo: un adapter
    no puede importar ``app/`` (contrato de capas app -> adapters -> core de
    import-linter); el tipado estructural de los Protocols hace innecesaria la
    herencia nominal.
    """

    def create(
        self,
        db: DbSession,
        recipient_id: UUID,
        notification_type: str,
        payload: dict[str, Any],
        deep_link: str | None = None,
    ) -> Notification:
        notification = Notification(
            recipient_id=recipient_id,
            type=notification_type,
            payload=payload,
            deep_link=deep_link,
            created_at=get_utc_now(),
        )
        db.add(notification)
        db.flush()  # populate ID
        return notification

    def list_notifications(
        self,
        db: DbSession,
        recipient_id: UUID,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
        retention_window: datetime.timedelta | None = None,
    ) -> list[Notification]:
        stmt = select(Notification).where(Notification.recipient_id == recipient_id)

        # Apply status filter
        if status == "unread":
            stmt = stmt.where(Notification.read_at.is_(None))
        elif status == "read":
            stmt = stmt.where(Notification.read_at.is_not(None))

        # Apply retention window
        if retention_window is not None:
            cutoff = get_utc_now() - retention_window
            stmt = stmt.where(Notification.created_at >= cutoff)

        stmt = stmt.order_by(Notification.created_at.desc()).limit(limit).offset(offset)
        return list(db.execute(stmt).scalars().all())

    def count_unread(
        self,
        db: DbSession,
        recipient_id: UUID,
        retention_window: datetime.timedelta | None = None,
    ) -> int:
        stmt = select(func.count(Notification.id)).where(
            and_(
                Notification.recipient_id == recipient_id,
                Notification.read_at.is_(None),
            )
        )

        if retention_window is not None:
            cutoff = get_utc_now() - retention_window
            stmt = stmt.where(Notification.created_at >= cutoff)

        return db.execute(stmt).scalar_one()

    def mark_read(
        self,
        db: DbSession,
        notification_id: UUID,
        recipient_id: UUID,
        now: datetime.datetime | None = None,
    ) -> bool:
        stmt = select(Notification).where(
            and_(
                Notification.id == notification_id,
                Notification.recipient_id == recipient_id,
            )
        )
        notif = db.execute(stmt).scalar_one_or_none()
        if notif is None:
            return False

        if notif.read_at is None:
            notif.read_at = now or get_utc_now()
            db.flush()
        return True

    def mark_all_read(
        self,
        db: DbSession,
        recipient_id: UUID,
        now: datetime.datetime | None = None,
    ) -> int:
        stmt = select(Notification).where(
            and_(
                Notification.recipient_id == recipient_id,
                Notification.read_at.is_(None),
            )
        )
        unread_notifs = db.execute(stmt).scalars().all()
        read_time = now or get_utc_now()
        count = 0
        for notif in unread_notifs:
            notif.read_at = read_time
            count += 1
        if count > 0:
            db.flush()
        return count

    def get_notification(
        self,
        db: DbSession,
        notification_id: UUID,
        recipient_id: UUID,
    ) -> Notification | None:
        stmt = select(Notification).where(
            and_(
                Notification.id == notification_id,
                Notification.recipient_id == recipient_id,
            )
        )
        return db.execute(stmt).scalar_one_or_none()
