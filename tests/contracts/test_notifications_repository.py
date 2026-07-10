"""Contract tests for PostgresNotificationRepository (d12, task 1.2)."""

from __future__ import annotations

import datetime
from collections.abc import Generator
from datetime import timedelta

import pytest
from sqlalchemy import text

from resultarai.adapters.persistence_postgres.connection import get_db_session
from resultarai.adapters.persistence_postgres.models import User
from resultarai.adapters.persistence_postgres.notifications import PostgresNotificationRepository


@pytest.fixture(autouse=True)
def cleanup_notifications() -> Generator[None, None, None]:
    """Truncates notifications and users tables before and after each test."""
    statement = text("TRUNCATE TABLE notifications, users CASCADE")
    with get_db_session() as session:
        session.execute(statement)
        session.commit()
    yield
    with get_db_session() as session:
        session.execute(statement)
        session.commit()


def _make_user(username: str) -> User:
    with get_db_session() as session:
        user = User(
            username=username,
            display_name=username.title(),
            role="tecnico",
            password_hash="$argon2id$fake-hash-for-tests",
            status="active",
        )
        session.add(user)
        session.flush()
        session.commit()
        user_row = session.get(User, user.id)
        assert user_row is not None
        return user_row


def test_notification_repository_lifecycle() -> None:
    repo = PostgresNotificationRepository()
    user_a = _make_user("user-a")
    user_b = _make_user("user-b")

    # 1. Create (Scenario: Notificación creada con los campos mínimos)
    with get_db_session() as db:
        notif = repo.create(
            db=db,
            recipient_id=user_a.id,
            notification_type="quota_release_requested",
            payload={"amount": 100},
            deep_link="/dashboard",
        )
        db.commit()
        notif_id = notif.id
        assert notif.recipient_id == user_a.id
        assert notif.type == "quota_release_requested"
        assert notif.payload == {"amount": 100}
        assert notif.deep_link == "/dashboard"
        assert notif.read_at is None
        assert notif.created_at is not None

    # 2. Count unread
    with get_db_session() as db:
        count = repo.count_unread(db, recipient_id=user_a.id)
        assert count == 1
        # Other user count should be 0
        assert repo.count_unread(db, recipient_id=user_b.id) == 0

    # 3. List paginated
    with get_db_session() as db:
        # Create second notification
        repo.create(
            db=db,
            recipient_id=user_a.id,
            notification_type="quota_release_resolved",
            payload={"decision": "approved"},
            deep_link=None,
        )
        db.commit()

    with get_db_session() as db:
        list_a = repo.list_notifications(
            db, recipient_id=user_a.id, status="unread", limit=1, offset=0
        )
        assert len(list_a) == 1
        # The list is desc, so the second one should be first
        assert list_a[0].type == "quota_release_resolved"

        list_all = repo.list_notifications(
            db, recipient_id=user_a.id, status="all", limit=10, offset=0
        )
        assert len(list_all) == 2

    # 4. Mark read
    with get_db_session() as db:
        success = repo.mark_read(db, notification_id=notif_id, recipient_id=user_a.id)
        assert success is True
        # Try marking read for wrong recipient
        success_wrong = repo.mark_read(db, notification_id=notif_id, recipient_id=user_b.id)
        assert success_wrong is False
        db.commit()

    with get_db_session() as db:
        assert repo.count_unread(db, recipient_id=user_a.id) == 1
        notif_db = repo.get_notification(db, notification_id=notif_id, recipient_id=user_a.id)
        assert notif_db is not None
        assert notif_db.read_at is not None

    # 5. Mark all read
    with get_db_session() as db:
        count_marked = repo.mark_all_read(db, recipient_id=user_a.id)
        assert count_marked == 1
        db.commit()

    with get_db_session() as db:
        assert repo.count_unread(db, recipient_id=user_a.id) == 0


def test_notification_repository_retention() -> None:
    repo = PostgresNotificationRepository()
    user_a = _make_user("user-retention")

    # Create one notification
    with get_db_session() as db:
        notif = repo.create(
            db=db,
            recipient_id=user_a.id,
            notification_type="quota_release_requested",
            payload={"amount": 100},
        )
        # Manually alter created_at to be 5 days ago
        notif.created_at = datetime.datetime.now(datetime.UTC).replace(tzinfo=None) - timedelta(
            days=5
        )
        db.commit()

    # Query with a 2-day retention window
    with get_db_session() as db:
        # Retention window 2 days -> should exclude the 5-day old notification
        list_active = repo.list_notifications(
            db,
            recipient_id=user_a.id,
            retention_window=timedelta(days=2),
        )
        assert len(list_active) == 0

        # Without retention window or with 10 days -> should include it
        list_all = repo.list_notifications(
            db,
            recipient_id=user_a.id,
            retention_window=timedelta(days=10),
        )
        assert len(list_all) == 1

        # Count unread with retention
        count_active = repo.count_unread(
            db,
            recipient_id=user_a.id,
            retention_window=timedelta(days=2),
        )
        assert count_active == 0
