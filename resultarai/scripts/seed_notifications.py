"""Seed script for notification fixtures (d12-notificaciones, Task 7.1).

Creates example notifications for local development.  Idempotent: skips
creation when notifications already exist for the target recipient.

Usage:
    uv run python -m resultarai.scripts.seed_notifications
"""

from __future__ import annotations

import sys
import uuid

from sqlalchemy import func, select

from resultarai.adapters.persistence_postgres.connection import get_db_session
from resultarai.adapters.persistence_postgres.models import (
    Notification,
    User,
    get_utc_now,
)
from resultarai.adapters.persistence_postgres.notifications import (
    PostgresNotificationRepository,
)

# ---------------------------------------------------------------------------
# Fixture definitions
# ---------------------------------------------------------------------------

# Each entry will produce one notification.  ``read`` controls whether the
# notification is immediately marked as read after creation.
SEED_NOTIFICATIONS: list[dict] = [
    # -- quota_release_requested --
    {
        "type": "quota_release_requested",
        "payload": {
            "requester_name": "María López",
            "group_name": "Equipo Desarrollo",
            "requested_amount": 500,
            "current_usage_pct": 92,
            "message": "Necesitamos tokens adicionales para las pruebas de integración.",
        },
        "deep_link": "/admin/quotas/requests/seed-req-1",
        "read": False,
    },
    {
        "type": "quota_release_requested",
        "payload": {
            "requester_name": "Carlos García",
            "group_name": "Equipo QA",
            "requested_amount": 200,
            "current_usage_pct": 85,
            "message": "Cuota casi agotada, solicitamos ampliación.",
        },
        "deep_link": "/admin/quotas/requests/seed-req-2",
        "read": True,
    },
    # -- quota_release_resolved --
    {
        "type": "quota_release_resolved",
        "payload": {
            "resolver_name": "Admin Principal",
            "group_name": "Equipo Desarrollo",
            "released_amount": 500,
            "resolution": "approved",
            "comment": "Aprobado para sprint actual.",
        },
        "deep_link": "/admin/quotas/requests/seed-req-1",
        "read": False,
    },
    {
        "type": "quota_release_resolved",
        "payload": {
            "resolver_name": "Admin Principal",
            "group_name": "Equipo QA",
            "released_amount": 100,
            "resolution": "partially_approved",
            "comment": "Aprobamos 100 de los 200 solicitados.",
        },
        "deep_link": "/admin/quotas/requests/seed-req-2",
        "read": True,
    },
]


def _find_admin_user_id(db) -> uuid.UUID | None:  # noqa: ANN001
    """Return the ID of the first active admin user, or ``None``."""
    stmt = (
        select(User.id)
        .where(User.role == "admin", User.status == "active")
        .order_by(User.created_at)
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()


def _notifications_exist(db, recipient_id: uuid.UUID) -> bool:  # noqa: ANN001
    """Return ``True`` if seed-like notifications already exist."""
    count = db.execute(
        select(func.count(Notification.id)).where(
            Notification.recipient_id == recipient_id,
        )
    ).scalar_one()
    return count > 0


def seed_notifications() -> None:
    """Create dev notification fixtures."""
    repo = PostgresNotificationRepository()

    with get_db_session() as db:
        admin_id = _find_admin_user_id(db)

        if admin_id is None:
            from resultarai.app.identity import hash_password
            default_admin = User(
                username="admin_dev",
                display_name="Admin Dev",
                role="admin",
                password_hash=hash_password("AdminPassword123!"),
                status="active",
                must_change_password=False,
            )
            db.add(default_admin)
            db.flush()
            admin_id = default_admin.id
            print(f"👤 No active admin found. Created default admin user: admin_dev ({admin_id})")

        if _notifications_exist(db, admin_id):
            print(
                f"✅ Notifications already exist for admin user {admin_id}. "
                "Skipping seed (idempotent)."
            )
            return

        created = 0
        for entry in SEED_NOTIFICATIONS:
            notif = repo.create(
                db=db,
                recipient_id=admin_id,
                notification_type=entry["type"],
                payload=entry["payload"],
                deep_link=entry.get("deep_link"),
            )
            if entry.get("read"):
                notif.read_at = get_utc_now()
                db.flush()
            created += 1
            status = "read" if notif.read_at else "unread"
            print(f"  📬 Created {entry['type']} ({status}) → {notif.id}")

        # Commit happens automatically via get_db_session context manager.
        print(f"\n✅ Seeded {created} notifications for admin user {admin_id}.")


if __name__ == "__main__":
    seed_notifications()
