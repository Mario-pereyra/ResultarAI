# ruff: noqa: E402
"""Integration tests for notifications endpoints and E2E quota triggers (d12, sections 3-4)."""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Annotated, Any
from uuid import UUID

from cryptography.fernet import Fernet

_STABLE_KEY = Fernet.generate_key().decode("utf-8")
os.environ.setdefault("IDENTITY_TOTP_ENCRYPTION_KEY", _STABLE_KEY)

import pyotp
import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as DbSession

from resultarai.adapters.persistence_postgres.connection import SessionLocal, get_db_session
from resultarai.adapters.persistence_postgres.models import Notification, TotpSecret, User
from resultarai.app.api import create_app
from resultarai.app.identity import (
    SESSION_COOKIE,
    SessionConfig,
    TotpConfig,
    get_db,
    get_session_config,
    hash_password,
)
from resultarai.app.use_cases.notifications.quota_triggers import (
    request_quota_release_test_trigger,
    resolve_quota_release_test_trigger,
)
from tests.app.identity.conftest import make_user

import datetime

_CONFIG = SessionConfig(
    signing_key="test-notif-key-for-notifications-and-access-control",
    idle_timeout=datetime.timedelta(minutes=30),
    absolute_lifetime=datetime.timedelta(hours=8),
    cookie_secure=False,
)


def make_completed_admin(username: str, password_hash: str) -> tuple[UUID, str]:
    """Crea un administrador con TOTP enrolado para pasar el wizard."""
    user_id = make_user(username, role="admin", password_hash=password_hash)
    secret_base32 = pyotp.random_base32()

    totp_config = TotpConfig.from_env()
    fernet = Fernet(totp_config.encryption_key)
    encrypted_secret = fernet.encrypt(secret_base32.encode("utf-8"))

    with get_db_session() as db:
        db.add(TotpSecret(user_id=user_id, encrypted_secret=encrypted_secret))
        db.commit()
    return user_id, secret_base32


def login_admin(client: TestClient, username: str, pwd: str, secret_base32: str) -> None:
    r_login = client.post("/api/auth/login", json={"username": username, "password": pwd})
    assert r_login.status_code == 200
    res_data = r_login.json()
    assert res_data["status"] == "pending_totp"
    pending_token = res_data["pending_token"]
    totp = pyotp.TOTP(secret_base32)
    code = totp.now()
    r_verify = client.post(
        "/api/auth/totp/verify", json={"pending_token": pending_token, "code": code}
    )
    assert r_verify.status_code == 200


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app()

    def _override_db() -> Iterator[DbSession]:
        session = SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_session_config] = lambda: _CONFIG

    with TestClient(app) as test_client:
        yield test_client


def post_csrf(client: TestClient, url: str, json: dict[str, Any] | None = None) -> Any:
    csrf_token = client.cookies.get("resultarai_csrf")
    headers = {}
    if csrf_token:
        headers["X-CSRF-Token"] = csrf_token
    return client.post(url, json=json, headers=headers)


# ---------------------------------------------------------------------------
# Section 3: E2E quota release triggers
# ---------------------------------------------------------------------------


def test_quota_release_request_notifies_all_admins() -> None:
    """3.1 Solicitud de liberación notifica a todos los Admin del tenant."""
    admin_pwd = "AdminPassword123!"
    admin1_id, _ = make_completed_admin("notif-admin1", hash_password(admin_pwd))
    admin2_id, _ = make_completed_admin("notif-admin2", hash_password(admin_pwd))
    requestor_id = make_user("notif-requestor", role="funcional", password_hash=hash_password("Pass123!"))

    with get_db_session() as db:
        notifications = request_quota_release_test_trigger(
            db=db,
            requestor_id=requestor_id,
            quota_name="API calls",
            current_consumption=105.5,
        )
        db.commit()

    assert len(notifications) == 2
    recipient_ids = {n.recipient_id for n in notifications}
    assert admin1_id in recipient_ids
    assert admin2_id in recipient_ids
    assert all(n.type == "quota_release_requested" for n in notifications)
    assert all(n.payload["requestor_username"] == "notif-requestor" for n in notifications)


def test_quota_release_resolve_notifies_requestor() -> None:
    """3.2 El solicitante es notificado de la decisión (concedida y denegada)."""
    requestor_id = make_user("notif-resolv", role="tecnico", password_hash=hash_password("Pass123!"))

    # Concedida
    with get_db_session() as db:
        notif_approved = resolve_quota_release_test_trigger(
            db=db,
            requestor_id=requestor_id,
            decision="approved",
            quota_name="API calls",
            reason="Uso justificado",
        )
        db.commit()

    assert notif_approved.recipient_id == requestor_id
    assert notif_approved.type == "quota_release_resolved"
    assert notif_approved.payload["decision"] == "approved"

    # Denegada
    with get_db_session() as db:
        notif_denied = resolve_quota_release_test_trigger(
            db=db,
            requestor_id=requestor_id,
            decision="denied",
            quota_name="Storage",
            reason=None,
        )
        db.commit()

    assert notif_denied.payload["decision"] == "denied"


# ---------------------------------------------------------------------------
# Section 4: Notification API endpoints
# ---------------------------------------------------------------------------


def test_list_notifications_filtered_unread(client: TestClient) -> None:
    """4.1 Listar solo no leídas."""
    admin_pwd = "AdminPassword123!"
    admin_id, secret = make_completed_admin("list-admin", hash_password(admin_pwd))
    login_admin(client, "list-admin", admin_pwd, secret)

    # Create test notifications via DB directly
    from resultarai.adapters.persistence_postgres.notifications import PostgresNotificationRepository
    repo = PostgresNotificationRepository()

    with get_db_session() as db:
        repo.create(db, admin_id, "quota_release_requested", {"requestor_username": "x", "quota_name": "a", "current_consumption": 1.0})
        n2 = repo.create(db, admin_id, "quota_release_requested", {"requestor_username": "y", "quota_name": "b", "current_consumption": 2.0})
        repo.mark_read(db, n2.id, admin_id)
        db.commit()

    r = client.get("/api/notifications?status=unread")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert all(not item["read"] for item in data["items"])


def test_list_notifications_pagination(client: TestClient) -> None:
    """4.1 Paginación no devuelve todo el historial de una vez."""
    admin_pwd = "AdminPassword123!"
    admin_id, secret = make_completed_admin("page-admin", hash_password(admin_pwd))
    login_admin(client, "page-admin", admin_pwd, secret)

    from resultarai.adapters.persistence_postgres.notifications import PostgresNotificationRepository
    repo = PostgresNotificationRepository()

    with get_db_session() as db:
        for i in range(5):
            repo.create(db, admin_id, "quota_release_requested", {"requestor_username": f"u{i}", "quota_name": "q", "current_consumption": float(i)})
        db.commit()

    r1 = client.get("/api/notifications?page=1&page_size=2")
    assert r1.status_code == 200
    d1 = r1.json()
    assert len(d1["items"]) == 2
    assert d1["has_next"] is True
    assert d1["page"] == 1

    r2 = client.get("/api/notifications?page=2&page_size=2")
    d2 = r2.json()
    assert len(d2["items"]) == 2

    # Items should not overlap
    ids1 = {item["id"] for item in d1["items"]}
    ids2 = {item["id"] for item in d2["items"]}
    assert ids1.isdisjoint(ids2)


def test_user_cannot_see_other_user_notifications(client: TestClient) -> None:
    """4.1 Un usuario no ve las notificaciones de otro."""
    admin_pwd = "AdminPassword123!"
    admin_a_id, secret_a = make_completed_admin("vis-admin-a", hash_password(admin_pwd))
    admin_b_id, secret_b = make_completed_admin("vis-admin-b", hash_password(admin_pwd))

    from resultarai.adapters.persistence_postgres.notifications import PostgresNotificationRepository
    repo = PostgresNotificationRepository()

    with get_db_session() as db:
        repo.create(db, admin_a_id, "quota_release_requested", {"requestor_username": "x", "quota_name": "q", "current_consumption": 1.0})
        repo.create(db, admin_b_id, "quota_release_requested", {"requestor_username": "y", "quota_name": "q", "current_consumption": 2.0})
        db.commit()

    # Login as admin B
    login_admin(client, "vis-admin-b", admin_pwd, secret_b)
    r = client.get("/api/notifications")
    assert r.status_code == 200
    data = r.json()
    # Only admin B's notification should be visible
    assert data["total"] == 1
    assert data["items"][0]["payload"]["requestor_username"] == "y"


def test_unread_count(client: TestClient) -> None:
    """4.2 El contador refleja el estado real de no-leídas."""
    admin_pwd = "AdminPassword123!"
    admin_id, secret = make_completed_admin("cnt-admin", hash_password(admin_pwd))
    login_admin(client, "cnt-admin", admin_pwd, secret)

    from resultarai.adapters.persistence_postgres.notifications import PostgresNotificationRepository
    repo = PostgresNotificationRepository()

    with get_db_session() as db:
        n1 = repo.create(db, admin_id, "quota_release_requested", {"requestor_username": "a", "quota_name": "q", "current_consumption": 1.0})
        repo.create(db, admin_id, "quota_release_requested", {"requestor_username": "b", "quota_name": "q", "current_consumption": 2.0})
        repo.create(db, admin_id, "quota_release_requested", {"requestor_username": "c", "quota_name": "q", "current_consumption": 3.0})
        db.commit()
        notif_id = n1.id

    r = client.get("/api/notifications/unread-count")
    assert r.status_code == 200
    assert r.json()["count"] == 3

    # Mark one as read
    post_csrf(client, f"/api/notifications/{notif_id}/read")

    r2 = client.get("/api/notifications/unread-count")
    assert r2.json()["count"] == 2


def test_mark_notification_read(client: TestClient) -> None:
    """4.3 Marcar una notificación como leída."""
    admin_pwd = "AdminPassword123!"
    admin_id, secret = make_completed_admin("mark-admin", hash_password(admin_pwd))
    login_admin(client, "mark-admin", admin_pwd, secret)

    from resultarai.adapters.persistence_postgres.notifications import PostgresNotificationRepository
    repo = PostgresNotificationRepository()

    with get_db_session() as db:
        n1 = repo.create(db, admin_id, "quota_release_requested", {"requestor_username": "x", "quota_name": "q", "current_consumption": 1.0})
        db.commit()
        notif_id = n1.id

    r = post_csrf(client, f"/api/notifications/{notif_id}/read")
    assert r.status_code == 200
    assert r.json() == {"status": "success"}


def test_mark_notification_read_foreign_rejected(client: TestClient) -> None:
    """4.3 Acceso directo a una notificación ajena es rechazado."""
    admin_pwd = "AdminPassword123!"
    admin_a_id, _ = make_completed_admin("for-admin-a", hash_password(admin_pwd))
    admin_b_id, secret_b = make_completed_admin("for-admin-b", hash_password(admin_pwd))

    from resultarai.adapters.persistence_postgres.notifications import PostgresNotificationRepository
    repo = PostgresNotificationRepository()

    with get_db_session() as db:
        n_a = repo.create(db, admin_a_id, "quota_release_requested", {"requestor_username": "x", "quota_name": "q", "current_consumption": 1.0})
        db.commit()
        foreign_id = n_a.id

    # Login as admin B and try to mark admin A's notification
    login_admin(client, "for-admin-b", admin_pwd, secret_b)
    r = post_csrf(client, f"/api/notifications/{foreign_id}/read")
    assert r.status_code == 404
    assert r.json()["detail"] == "Notificación no encontrada."


def test_mark_all_read(client: TestClient) -> None:
    """4.4 Marcar todas las notificaciones como leídas."""
    admin_pwd = "AdminPassword123!"
    admin_id, secret = make_completed_admin("all-admin", hash_password(admin_pwd))
    login_admin(client, "all-admin", admin_pwd, secret)

    from resultarai.adapters.persistence_postgres.notifications import PostgresNotificationRepository
    repo = PostgresNotificationRepository()

    with get_db_session() as db:
        for i in range(3):
            repo.create(db, admin_id, "quota_release_requested", {"requestor_username": f"u{i}", "quota_name": "q", "current_consumption": float(i)})
        db.commit()

    r = post_csrf(client, "/api/notifications/read-all")
    assert r.status_code == 200
    assert r.json()["status"] == "success"
    assert r.json()["count"] == 3

    r2 = client.get("/api/notifications/unread-count")
    assert r2.json()["count"] == 0


def test_admin_role_filter_on_emission() -> None:
    """4.5 Un usuario sin rol Admin nunca recibe una notificación reservada a Admin."""
    admin_pwd = "AdminPassword123!"
    admin_id, _ = make_completed_admin("role-admin", hash_password(admin_pwd))
    funcional_id = make_user("role-func", role="funcional", password_hash=hash_password("Pass123!"))

    with get_db_session() as db:
        notifications = request_quota_release_test_trigger(
            db=db,
            requestor_id=funcional_id,
            quota_name="Tokens",
            current_consumption=500.0,
        )
        db.commit()

    # Only admin should have received it
    recipient_ids = {n.recipient_id for n in notifications}
    assert admin_id in recipient_ids
    assert funcional_id not in recipient_ids
