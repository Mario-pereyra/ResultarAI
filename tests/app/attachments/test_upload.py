# ruff: noqa: E402
"""Tests de subida y validacion de adjuntos (d14, tareas 2.1-2.3).

Cubre los escenarios de las specs `attachments-pipeline` (subida con limites) y
`attachments-security` (tipo real, rechazos de formatos activos): excede tamano de su
tipo, sexto adjunto, tipo falsificado, fuera del allowlist, .xlsm, .exe, doble
extension, PDF con contrasena, y el camino feliz.
"""

from __future__ import annotations

import datetime
import io
import os
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet

# Fijar una clave estable en el entorno antes de importar nada que inicialice TotpConfig
# (mismo patron que tests/app/chat/test_sessions.py).
_STABLE_KEY = Fernet.generate_key().decode("utf-8")
os.environ.setdefault("IDENTITY_TOTP_ENCRYPTION_KEY", _STABLE_KEY)

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from pypdf import PdfWriter
from sqlalchemy.orm import Session as DbSession

from resultarai.adapters.persistence_postgres.connection import SessionLocal, get_db_session
from resultarai.adapters.persistence_postgres.models import Attachment, get_utc_now
from resultarai.adapters.persistence_postgres.models import Session as SessionModel
from resultarai.app.api import create_app
from resultarai.app.api.attachments import get_attachments_config
from resultarai.app.attachments import AttachmentsConfig, FileCategory
from resultarai.app.identity import (
    SessionConfig,
    get_db,
    get_session_config,
    hash_password,
)
from tests.app.identity.conftest import make_user

_CONFIG = SessionConfig(
    signing_key="test-attachments-signing-key-1234567890",
    idle_timeout=datetime.timedelta(minutes=30),
    absolute_lifetime=datetime.timedelta(hours=8),
    cookie_secure=False,  # deshabilitado Secure para extraer la cookie en el test client
)

_PWD = "ValidPassword123!"


@pytest.fixture
def attachments_config(tmp_path: Path) -> AttachmentsConfig:
    """Config de adjuntos con `storage_dir` aislado por test y tenant de prueba.

    Es un dataclass mutable: un test que necesite un limite chico lo ajusta antes de
    subir (p. ej. `size_limits_bytes[FileCategory.EXCEL] = 1024`).
    """
    return AttachmentsConfig(storage_dir=tmp_path / "attachments", tenant="test-tenant")


@pytest.fixture
def client(attachments_config: AttachmentsConfig) -> Iterator[TestClient]:
    """TestClient con overrides de DB, config de sesion y config de adjuntos."""
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
    """Crea un usuario nuevo, hace login y devuelve su id."""
    username = _unique_username(prefix)
    user_id = make_user(username, role=role, password_hash=hash_password(_PWD))
    response = client.post("/api/auth/login", json={"username": username, "password": _PWD})
    assert response.status_code == 200
    return user_id


def _make_session(owner_id: uuid.UUID) -> str:
    """Inserta una sesion de chat minima del usuario y devuelve su id."""
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


def _post_upload(
    client: TestClient,
    session_id: str,
    filename: str,
    content: bytes,
    content_type: str = "application/octet-stream",
) -> Any:
    """Sube un adjunto adjuntando el header CSRF de la cookie de sesion actual."""
    csrf_token = client.cookies.get("resultarai_csrf")
    headers = {"X-CSRF-Token": csrf_token} if csrf_token else {}
    return client.post(
        "/api/attachments",
        files={"file": (filename, io.BytesIO(content), content_type)},
        data={"session_id": session_id},
        headers=headers,
    )


def _xlsx_bytes() -> bytes:
    """Genera un .xlsx real (ZIP OOXML valido) en memoria."""
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet["A1"] = "codigo"
    sheet["B1"] = "descripcion"
    sheet["A2"] = 1
    sheet["B2"] = "producto de prueba"
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _encrypted_pdf_bytes() -> bytes:
    """Genera un PDF de una pagina protegido con contrasena."""
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.encrypt("secret-password")
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


# --------------------------------------------------------------------------------------
# Camino feliz (tarea 2.1)
# --------------------------------------------------------------------------------------


def test_upload_xlsx_persists_uploaded_with_sha256_and_storage_uuid(
    client: TestClient, attachments_config: AttachmentsConfig
) -> None:
    """Sube un .xlsx valido: queda `uploaded` con sha256 y binario UUID fuera del webroot."""
    owner_id = _login_new_user(client, "att-happy")
    session_id = _make_session(owner_id)
    content = _xlsx_bytes()

    response = _post_upload(client, session_id, "balance marzo.xlsx", content)
    assert response.status_code == 201, response.text
    data = response.json()

    assert data["status"] == "uploaded"
    assert data["session_id"] == session_id
    assert data["detected_type"] == "excel"
    assert data["original_name"] == "balance marzo.xlsx"
    assert data["size_bytes"] == len(content)
    assert len(data["sha256"]) == 64
    # La respuesta no expone el storage_path (no hay URL directa del binario).
    assert "storage_path" not in data

    # En base: estado inicial, hash y binario UUID sin extension en el storage_dir.
    with get_db_session() as db:
        attachment = db.get(Attachment, uuid.UUID(data["id"]))
        assert attachment is not None
        assert attachment.status == "uploaded"
        assert attachment.message_id is None  # borrador: aun no asociado a un mensaje
        assert attachment.tenant == "test-tenant"
        assert attachment.uploaded_by == str(owner_id)
        assert attachment.storage_path is not None
        stored = attachments_config.storage_dir / str(attachment.storage_path)
        assert stored.exists()
        assert stored.suffix == ""  # sin extension en disco
        assert stored.read_bytes() == content


def test_upload_text_file_without_binary_signature_succeeds(client: TestClient) -> None:
    """Un formato de texto (.md) no lleva magic byte y se acepta igual."""
    owner_id = _login_new_user(client, "att-text")
    session_id = _make_session(owner_id)

    response = _post_upload(client, session_id, "notas.md", b"# Titulo\n\ncontenido")
    assert response.status_code == 201, response.text
    assert response.json()["detected_type"] == "text"


# --------------------------------------------------------------------------------------
# Limites (tarea 2.1)
# --------------------------------------------------------------------------------------


def test_upload_exceeding_type_size_limit_is_rejected(
    client: TestClient, attachments_config: AttachmentsConfig
) -> None:
    """Un Excel que supera el limite de su tipo se rechaza con el limite concreto."""
    owner_id = _login_new_user(client, "att-toobig")
    session_id = _make_session(owner_id)
    # Limite de Excel deliberadamente chico (config de instancia): un .xlsx real lo supera.
    attachments_config.size_limits_bytes[FileCategory.EXCEL] = 1024

    response = _post_upload(client, session_id, "grande.xlsx", _xlsx_bytes())
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["error_code"] == "too_large"
    assert detail["params"]["limit_bytes"] == 1024
    assert detail["params"]["type_group"] == "excel"


def test_sixth_attachment_in_same_draft_is_rejected(client: TestClient) -> None:
    """El sexto adjunto del mismo borrador se rechaza con too_many_attachments."""
    owner_id = _login_new_user(client, "att-sixth")
    session_id = _make_session(owner_id)

    # Pre-siembra 5 adjuntos pendientes (message_id NULL) del mismo usuario y sesion.
    with get_db_session() as db:
        for index in range(5):
            db.add(
                Attachment(
                    session_id=session_id,
                    message_id=None,
                    uploaded_by=str(owner_id),
                    original_name=f"previo-{index}.txt",
                    declared_mime="text/plain",
                    detected_type="text",
                    size_bytes=10,
                    sha256=uuid.uuid4().hex + uuid.uuid4().hex,  # 64 hex chars
                    storage_path=uuid.uuid4(),
                    status="uploaded",
                    tenant="test-tenant",
                )
            )

    response = _post_upload(client, session_id, "sexto.txt", b"contenido")
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["error_code"] == "too_many_attachments"
    assert detail["params"]["limit"] == 5


# --------------------------------------------------------------------------------------
# Tipo real: allowlist y magic bytes (tarea 2.2)
# --------------------------------------------------------------------------------------


def test_forged_xlsx_rejected_by_signature(client: TestClient) -> None:
    """Un .xlsx cuya firma no es ZIP/OOXML se rechaza como tipo falsificado."""
    owner_id = _login_new_user(client, "att-forged")
    session_id = _make_session(owner_id)

    response = _post_upload(client, session_id, "datos.xlsx", b"esto no es un zip, es texto")
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["error_code"] == "type_forged"
    assert detail["params"]["extension"] == ".xlsx"


def test_extension_outside_allowlist_rejected(client: TestClient) -> None:
    """Una extension fuera del allowlist se rechaza como tipo no soportado."""
    owner_id = _login_new_user(client, "att-unknown")
    session_id = _make_session(owner_id)

    response = _post_upload(client, session_id, "raro.foo", b"lo que sea")
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["error_code"] == "type_not_allowed"
    assert detail["params"]["extension"] == ".foo"


def test_double_extension_classified_by_last_extension(client: TestClient) -> None:
    """`informe.pdf.exe` clasifica por la ultima extension (.exe) y se rechaza."""
    owner_id = _login_new_user(client, "att-double")
    session_id = _make_session(owner_id)

    response = _post_upload(client, session_id, "informe.pdf.exe", b"MZ\x90\x00binario")
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["error_code"] == "executable_rejected"
    assert detail["params"]["extension"] == ".exe"


# --------------------------------------------------------------------------------------
# Rechazos de formatos activos/peligrosos (tarea 2.3)
# --------------------------------------------------------------------------------------


def test_xlsm_with_macros_rejected(client: TestClient) -> None:
    """Un .xlsm (con macros) se rechaza de plano, sin intentar parsearlo."""
    owner_id = _login_new_user(client, "att-macro")
    session_id = _make_session(owner_id)

    # Contenido con firma ZIP valida: aun asi se rechaza por extension, antes de contenido.
    response = _post_upload(client, session_id, "reporte.xlsm", b"PK\x03\x04resto")
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["error_code"] == "macros_not_allowed"
    assert detail["params"]["extension"] == ".xlsm"


def test_executable_rejected(client: TestClient) -> None:
    """Un .exe se rechaza de plano."""
    owner_id = _login_new_user(client, "att-exe")
    session_id = _make_session(owner_id)

    response = _post_upload(client, session_id, "malware.exe", b"MZ\x90\x00binario")
    assert response.status_code == 422
    assert response.json()["detail"]["error_code"] == "executable_rejected"


def test_password_protected_pdf_rejected(client: TestClient) -> None:
    """Un PDF protegido con contrasena se rechaza sin reintentos."""
    owner_id = _login_new_user(client, "att-pdfpw")
    session_id = _make_session(owner_id)

    response = _post_upload(client, session_id, "protegido.pdf", _encrypted_pdf_bytes())
    assert response.status_code == 422
    assert response.json()["detail"]["error_code"] == "pdf_password"


def test_image_rejected_with_own_error_code(client: TestClient) -> None:
    """Una imagen (.png) se rechaza en V1 con error_code PROPIO `image_not_supported`.

    Escenario "Imagen rechazada con alternativa accionable" de `attachments-ui`: el codigo
    es distinguible de `type_not_allowed` para que el frontend muestre el texto "Imagen
    (V1)" de ANEXO §10 con su alternativa (pegar el texto del error / exportar a PDF/Excel).
    """
    owner_id = _login_new_user(client, "att-image")
    session_id = _make_session(owner_id)

    # Firma PNG valida: el rechazo ocurre por extension (antes de mirar contenido).
    response = _post_upload(client, session_id, "captura.png", b"\x89PNG\r\n\x1a\n", "image/png")
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["error_code"] == "image_not_supported"
    assert detail["params"]["extension"] == ".png"


def test_image_extensions_all_rejected_as_image(client: TestClient) -> None:
    """`.jpg/.jpeg/.gif/.webp` tambien se rechazan como `image_not_supported`."""
    owner_id = _login_new_user(client, "att-images")
    session_id = _make_session(owner_id)

    for filename in ("foto.jpg", "foto.jpeg", "anim.gif", "logo.webp"):
        response = _post_upload(client, session_id, filename, b"binario de imagen")
        assert response.status_code == 422, filename
        assert response.json()["detail"]["error_code"] == "image_not_supported", filename


def test_rejected_file_leaves_no_attachment_row(
    client: TestClient, attachments_config: AttachmentsConfig
) -> None:
    """Un adjunto rechazado no persiste fila ni binario (no queda para extraccion)."""
    owner_id = _login_new_user(client, "att-norow")
    session_id = _make_session(owner_id)

    response = _post_upload(client, session_id, "malware.exe", b"MZ binario")
    assert response.status_code == 422

    with get_db_session() as db:
        rows = db.query(Attachment).filter(Attachment.session_id == session_id).all()
        assert rows == []
    # Tampoco se creo el directorio/binario de storage.
    if attachments_config.storage_dir.exists():
        assert list(attachments_config.storage_dir.iterdir()) == []


# --------------------------------------------------------------------------------------
# Autorizacion (coherente con el resto de la API)
# --------------------------------------------------------------------------------------


def test_upload_to_foreign_session_returns_404(client: TestClient) -> None:
    """Subir a una sesion ajena responde 404 sin filtrar existencia."""
    _login_new_user(client, "att-attacker")
    other_owner = make_user(_unique_username("att-victim"), password_hash=hash_password(_PWD))
    foreign_session = _make_session(other_owner)

    response = _post_upload(client, foreign_session, "notas.txt", b"hola")
    assert response.status_code == 404


def test_upload_without_authentication_returns_401(client: TestClient) -> None:
    """Sin sesion autenticada, la subida responde 401."""
    owner_id = make_user(_unique_username("att-anon"), password_hash=hash_password(_PWD))
    session_id = _make_session(owner_id)

    response = client.post(
        "/api/attachments",
        files={"file": ("notas.txt", io.BytesIO(b"hola"), "text/plain")},
        data={"session_id": session_id},
    )
    assert response.status_code in (401, 403)
