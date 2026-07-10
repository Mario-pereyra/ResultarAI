# ruff: noqa: E402
"""Tests del endpoint de confirmacion auditada de datos de prueba (d14, tarea 5.2).

Cubre el escenario "PII detectada requiere confirmacion registrada en el audit log" de
`attachments-security`: el dueno de un adjunto con PII N2 confirma "son datos de prueba",
la confirmacion queda en el audit log append-only (`identity_audit_events`), el adjunto
pasa de no-enviable a enviable, y un usuario ajeno no puede confirmar (404).
"""

from __future__ import annotations

import datetime
import os
import uuid
from collections.abc import Iterator
from typing import Any

from cryptography.fernet import Fernet

_STABLE_KEY = Fernet.generate_key().decode("utf-8")
os.environ.setdefault("IDENTITY_TOTP_ENCRYPTION_KEY", _STABLE_KEY)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from resultarai.adapters.persistence_postgres.connection import SessionLocal, get_db_session
from resultarai.adapters.persistence_postgres.models import (
    Attachment,
    IdentityAuditEvent,
    get_utc_now,
)
from resultarai.adapters.persistence_postgres.models import Session as SessionModel
from resultarai.app.api import create_app
from resultarai.app.attachments.confirmation import AUDIT_EVENT_TYPE
from resultarai.app.identity import SessionConfig, get_db, get_session_config, hash_password
from tests.app.identity.conftest import make_user

_CONFIG = SessionConfig(
    signing_key="test-confirm-signing-key-1234567890",
    idle_timeout=datetime.timedelta(minutes=30),
    absolute_lifetime=datetime.timedelta(hours=8),
    cookie_secure=False,
)

_PWD = "ValidPassword123!"

_PII_SCAN_RESULT: dict[str, Any] = {
    "pii_findings": [
        {"entity_type": "EMAIL_ADDRESS", "count": 2, "lines": [1]},
        {"entity_type": "BO_CI", "count": 1, "lines": [2]},
    ],
    "requires_test_data_confirmation": True,
}


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


def _unique_username(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _login_new_user(client: TestClient, prefix: str) -> uuid.UUID:
    username = _unique_username(prefix)
    user_id = make_user(username, role="funcional", password_hash=hash_password(_PWD))
    response = client.post("/api/auth/login", json={"username": username, "password": _PWD})
    assert response.status_code == 200
    return user_id


def _make_session(owner_id: uuid.UUID) -> str:
    session_id = f"sess_{uuid.uuid4().hex}"
    with get_db_session() as db:
        db.add(
            SessionModel(
                id=session_id,
                model_profile="openai_gpt_4o",
                owner_user_id=owner_id,
                agent_id="default_chat",
                last_activity_at=get_utc_now(),
            )
        )
    return session_id


def _make_attachment(
    owner_id: uuid.UUID, session_id: str, scan_result: dict[str, Any] | None
) -> uuid.UUID:
    """Crea un adjunto `ready` (post-extraccion) del usuario con el `scan_result` dado."""
    attachment_id = uuid.uuid4()
    with get_db_session() as db:
        db.add(
            Attachment(
                id=attachment_id,
                session_id=session_id,
                message_id=None,
                uploaded_by=str(owner_id),
                original_name="planilla.csv",
                declared_mime="text/csv",
                detected_type="csv",
                size_bytes=100,
                sha256=uuid.uuid4().hex + uuid.uuid4().hex,
                storage_path=uuid.uuid4(),
                scan_result=scan_result,
                status="ready",
                tenant="test-tenant",
            )
        )
    return attachment_id


def _post_confirm(client: TestClient, attachment_id: uuid.UUID) -> Any:
    csrf_token = client.cookies.get("resultarai_csrf")
    headers = {"X-CSRF-Token": csrf_token} if csrf_token else {}
    return client.post(f"/api/attachments/{attachment_id}/confirm-test-data", headers=headers)


def test_confirm_records_audit_and_makes_sendable(client: TestClient) -> None:
    """El dueno confirma: audit log escrito, `scan_result` marcado y adjunto ya enviable."""
    owner_id = _login_new_user(client, "confirm-owner")
    session_id = _make_session(owner_id)
    attachment_id = _make_attachment(owner_id, session_id, dict(_PII_SCAN_RESULT))

    response = _post_confirm(client, attachment_id)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["requires_test_data_confirmation"] is False
    assert body["sendable"] is True

    with get_db_session() as db:
        # La confirmacion quedo en el audit log append-only, con actor y target correctos.
        events = db.scalars(
            select(IdentityAuditEvent).where(
                IdentityAuditEvent.target_ref == str(attachment_id),
                IdentityAuditEvent.event_type == AUDIT_EVENT_TYPE,
            )
        ).all()
        assert len(events) == 1
        assert events[0].actor_user_id == owner_id
        assert events[0].details is not None
        assert events[0].details["findings_summary"] == {"EMAIL_ADDRESS": 2, "BO_CI": 1}

        # El adjunto quedo marcado como confirmado (sin migrar el schema de b04).
        stored = db.get(Attachment, attachment_id)
        assert stored is not None
        assert stored.scan_result is not None
        assert stored.scan_result["requires_test_data_confirmation"] is False
        assert stored.scan_result["test_data_confirmation"]["confirmed_by"] == str(owner_id)
        assert "confirmed_at" in stored.scan_result["test_data_confirmation"]


def test_confirm_by_foreign_user_returns_404(client: TestClient) -> None:
    """Un usuario que no es el dueno no puede confirmar (404, sin filtrar existencia)."""
    owner_id = make_user(_unique_username("confirm-victim"), password_hash=hash_password(_PWD))
    session_id = _make_session(owner_id)
    attachment_id = _make_attachment(owner_id, session_id, dict(_PII_SCAN_RESULT))

    # El atacante inicia su propia sesion.
    _login_new_user(client, "confirm-attacker")
    response = _post_confirm(client, attachment_id)
    assert response.status_code == 404

    with get_db_session() as db:
        # No se escribio ningun evento de audit ni se marco el adjunto ajeno.
        events = db.scalars(
            select(IdentityAuditEvent).where(IdentityAuditEvent.target_ref == str(attachment_id))
        ).all()
        assert events == []
        stored = db.get(Attachment, attachment_id)
        assert stored is not None
        assert stored.scan_result is not None
        assert stored.scan_result["requires_test_data_confirmation"] is True


def test_confirm_without_pending_confirmation_returns_409(client: TestClient) -> None:
    """Confirmar un adjunto sin PII pendiente (o ya confirmado) responde 409."""
    owner_id = _login_new_user(client, "confirm-nopending")
    session_id = _make_session(owner_id)
    attachment_id = _make_attachment(owner_id, session_id, None)  # limpio, nada que confirmar

    response = _post_confirm(client, attachment_id)
    assert response.status_code == 409
    assert response.json()["detail"]["error_code"] == "no_pending_confirmation"
