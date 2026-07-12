# ruff: noqa: E402
"""Tests del endpoint de descarga auditada de adjuntos (d14, tarea 7.2, ANEXO §5).

Cubre los escenarios de `attachments-pipeline`:

- "Un usuario ajeno intenta descargar": rechazo (404, sin filtrar existencia), sin URL
  publica de ningun tipo -- solo este endpoint autenticado.
- "Descarga por el dueno queda auditada": el dueno descarga por el endpoint autenticado
  y el evento queda en el audit log append-only (`identity_audit_events`).

Ademas: Admin puede descargar un adjunto ajeno (tambien auditado), y descargar el
binario de un adjunto ya purgado por retencion responde con el error tipado
`attachment_binary_purged` (409), nunca un 500 -- sin auditar un intento sobre un
binario que ya no existe.
"""

from __future__ import annotations

import datetime
import os
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet

# Fijar una clave estable en el entorno antes de importar nada que inicialice TotpConfig
# (mismo patron que tests/app/attachments/test_pipeline.py y test_confirm_test_data.py).
_STABLE_KEY = Fernet.generate_key().decode("utf-8")
os.environ.setdefault("IDENTITY_TOTP_ENCRYPTION_KEY", _STABLE_KEY)

import pyotp
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from resultarai.adapters.persistence_postgres.connection import SessionLocal, get_db_session
from resultarai.adapters.persistence_postgres.models import (
    Attachment,
    IdentityAuditEvent,
    TotpSecret,
    get_utc_now,
)
from resultarai.adapters.persistence_postgres.models import Session as SessionModel
from resultarai.app.api import create_app
from resultarai.app.api.attachments import get_attachments_config
from resultarai.app.attachments import AttachmentsConfig
from resultarai.app.attachments.download import AUDIT_EVENT_TYPE
from resultarai.app.identity import (
    SessionConfig,
    TotpConfig,
    get_db,
    get_session_config,
    hash_password,
)
from tests.app.identity.conftest import make_user

_CONFIG = SessionConfig(
    signing_key="test-download-signing-key-1234567890",
    idle_timeout=datetime.timedelta(minutes=30),
    absolute_lifetime=datetime.timedelta(hours=8),
    cookie_secure=False,
)

_PWD = "ValidPassword123!"
_TENANT = "test-tenant"


@pytest.fixture
def attachments_config(tmp_path: Path) -> AttachmentsConfig:
    return AttachmentsConfig(storage_dir=tmp_path / "attachments", tenant=_TENANT)


@pytest.fixture
def client(attachments_config: AttachmentsConfig) -> Iterator[TestClient]:
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
    app.dependency_overrides[get_attachments_config] = lambda: attachments_config

    with TestClient(app) as test_client:
        yield test_client


def _unique_username(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _login_new_user(client: TestClient, prefix: str, *, role: str = "funcional") -> uuid.UUID:
    """Crea un usuario del rol dado y completa su login (mismo patron que
    `tests/app/chat/test_telemetry.py::_create_user_and_login`): Admin exige TOTP
    obligatorio (`get_wizard_status`), asi que sin enrolar uno el `wizard_guard`
    global bloquearia cualquier ruta con 403; Funcional/Tecnico no tienen ese paso.
    """
    username = _unique_username(prefix)
    user_id = make_user(username, role=role, password_hash=hash_password(_PWD))

    if role == "admin":
        secret_base32 = pyotp.random_base32()
        totp_config = TotpConfig.from_env()
        fernet = Fernet(totp_config.encryption_key)
        encrypted_secret = fernet.encrypt(secret_base32.encode("utf-8"))
        with get_db_session() as db:
            db.add(TotpSecret(user_id=user_id, encrypted_secret=encrypted_secret))
            db.commit()

        r_login = client.post("/api/auth/login", json={"username": username, "password": _PWD})
        assert r_login.status_code == 200, r_login.text
        pending_token = r_login.json()["pending_token"]
        code = pyotp.TOTP(secret_base32).now()
        r_verify = client.post(
            "/api/auth/totp/verify", json={"pending_token": pending_token, "code": code}
        )
        assert r_verify.status_code == 200, r_verify.text
        return user_id

    response = client.post("/api/auth/login", json={"username": username, "password": _PWD})
    assert response.status_code == 200, response.text
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


def _make_attachment_with_binary(
    config: AttachmentsConfig,
    owner_id: uuid.UUID,
    session_id: str,
    content: bytes,
    *,
    storage_path: uuid.UUID | None,
    name: str = "reporte.txt",
) -> uuid.UUID:
    """Crea un adjunto `ready` con su binario real en disco (si `storage_path` no es
    `None`); `storage_path=None` simula un adjunto ya purgado por retencion."""
    if storage_path is not None:
        config.storage_dir.mkdir(parents=True, exist_ok=True)
        (config.storage_dir / str(storage_path)).write_bytes(content)

    attachment_id = uuid.uuid4()
    with get_db_session() as db:
        db.add(
            Attachment(
                id=attachment_id,
                session_id=session_id,
                message_id=None,
                uploaded_by=str(owner_id),
                original_name=name,
                declared_mime="text/plain",
                detected_type="text",
                size_bytes=len(content),
                sha256=uuid.uuid4().hex + uuid.uuid4().hex,
                storage_path=storage_path,
                scan_result=None,
                status="ready",
                tenant=_TENANT,
            )
        )
    return attachment_id


def _download(client: TestClient, attachment_id: uuid.UUID) -> Any:
    return client.get(f"/api/attachments/{attachment_id}/download")


def _audit_events_for(attachment_id: uuid.UUID) -> list[IdentityAuditEvent]:
    with get_db_session() as db:
        return list(
            db.scalars(
                select(IdentityAuditEvent).where(
                    IdentityAuditEvent.target_ref == str(attachment_id),
                    IdentityAuditEvent.event_type == AUDIT_EVENT_TYPE,
                )
            ).all()
        )


def test_owner_can_download_and_it_is_audited(
    client: TestClient, attachments_config: AttachmentsConfig
) -> None:
    """El dueno descarga por el endpoint autenticado: recibe el binario exacto y la
    descarga queda registrada en el audit log append-only."""
    owner_id = _login_new_user(client, "dl-owner")
    session_id = _make_session(owner_id)
    storage_path = uuid.uuid4()
    content = b"contenido real del reporte"
    attachment_id = _make_attachment_with_binary(
        attachments_config, owner_id, session_id, content, storage_path=storage_path
    )

    response = _download(client, attachment_id)
    assert response.status_code == 200, response.text
    assert response.content == content
    assert "reporte.txt" in response.headers.get("content-disposition", "")

    events = _audit_events_for(attachment_id)
    assert len(events) == 1
    assert events[0].actor_user_id == owner_id
    assert events[0].details is not None
    assert events[0].details["owner_user_id"] == str(owner_id)


def test_foreign_user_cannot_download_and_no_public_url_exists(
    client: TestClient, attachments_config: AttachmentsConfig
) -> None:
    """Un usuario ajeno (ni dueno ni Admin) no puede descargar: 404 sin filtrar
    existencia, y nada queda auditado -- no hubo descarga real."""
    owner_id = make_user(_unique_username("dl-victim"), password_hash=hash_password(_PWD))
    session_id = _make_session(owner_id)
    attachment_id = _make_attachment_with_binary(
        attachments_config,
        owner_id,
        session_id,
        b"contenido secreto",
        storage_path=None,  # no hace falta binario real: el rechazo ocurre antes
    )

    _login_new_user(client, "dl-attacker")
    response = _download(client, attachment_id)
    assert response.status_code == 404

    assert _audit_events_for(attachment_id) == []


def test_admin_can_download_a_foreign_attachment_and_it_is_audited(
    client: TestClient, attachments_config: AttachmentsConfig
) -> None:
    """Admin puede descargar el adjunto de otro usuario; tambien queda auditado."""
    owner_id = make_user(_unique_username("dl-owner-for-admin"), password_hash=hash_password(_PWD))
    session_id = _make_session(owner_id)
    storage_path = uuid.uuid4()
    content = b"contenido que solo el Admin deberia poder auditar"
    attachment_id = _make_attachment_with_binary(
        attachments_config, owner_id, session_id, content, storage_path=storage_path
    )

    admin_id = _login_new_user(client, "dl-admin", role="admin")
    response = _download(client, attachment_id)
    assert response.status_code == 200, response.text
    assert response.content == content

    events = _audit_events_for(attachment_id)
    assert len(events) == 1
    assert events[0].actor_user_id == admin_id
    assert events[0].details is not None
    assert events[0].details["owner_user_id"] == str(owner_id)


def test_download_of_purged_binary_returns_typed_error_without_audit(
    client: TestClient, attachments_config: AttachmentsConfig
) -> None:
    """El binario ya fue purgado por retencion (`storage_path IS NULL`): 409 tipado,
    nunca un 500, y sin auditar -- no hubo descarga real que registrar."""
    owner_id = _login_new_user(client, "dl-purged-owner")
    session_id = _make_session(owner_id)
    attachment_id = _make_attachment_with_binary(
        attachments_config,
        owner_id,
        session_id,
        b"contenido irrelevante: no se escribe a disco",
        storage_path=None,
    )

    response = _download(client, attachment_id)
    assert response.status_code == 409
    assert response.json()["detail"]["error_code"] == "attachment_binary_purged"

    assert _audit_events_for(attachment_id) == []


def test_download_nonexistent_attachment_returns_404(client: TestClient) -> None:
    """Un `attachment_id` inexistente responde 404 igual que uno ajeno (no filtra)."""
    _login_new_user(client, "dl-noexist")
    response = _download(client, uuid.uuid4())
    assert response.status_code == 404
