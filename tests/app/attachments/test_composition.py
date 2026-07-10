# ruff: noqa: E402
"""Tests de composición server-side del mensaje con adjuntos (d14, tareas 6.2-6.3).

Cubre los escenarios de la spec (`attachments-pipeline`) bajo los requirements
"Composición del mensaje con la extracción al final del contexto" y "Pedir otra parte
inserta un fragmento nuevo sin re-procesar", más los casos adicionales pedidos por la
tarea: presupuesto por mensaje excedido, envío bloqueado por N3/N2 sin confirmar, ramas
que reutilizan `inserted_text` byte-idéntica, y vista previa pre/post inserción
(soporte de 8.1/8.3).

Los adjuntos se construyen DIRECTO en la base (`Attachment` + `Extraction`), sin pasar
por el endpoint de subida real: el hueco documentado en
`app/use_cases/chat/_attachments.py` (tarea `7.1` de este mismo change, dedup +
persistencia de `full_text`, todavía no implementada) significa que HOY ningún camino
de producción deja un adjunto con `extraction_id` poblado. Construir la fila
directamente simula exactamente lo que `7.1` dejará wireado, siguiendo el mismo patrón
que `tests/app/attachments/test_confirm_test_data.py`.
"""

from __future__ import annotations

import datetime
import os
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import patch

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
    Extraction,
    Message,
    MessageAttachment,
    get_utc_now,
)
from resultarai.adapters.persistence_postgres.models import Session as SessionModel
from resultarai.app.api import create_app
from resultarai.app.api.chat import get_registries, get_response_generator
from resultarai.app.api.chat_stream import (
    get_streaming_response_generator,
    get_turn_stream_registry,
)
from resultarai.app.attachments import AttachmentsConfig
from resultarai.app.attachments.dependency import get_attachments_config
from resultarai.app.identity import SessionConfig, get_db, get_session_config, hash_password
from resultarai.app.startup import bootstrap
from resultarai.app.use_cases.chat import TurnCompletion, TurnFragment
from resultarai.app.use_cases.chat.stream_registry import TurnStreamRegistry
from tests.app.identity.conftest import make_user

_CONFIG = SessionConfig(
    signing_key="test-attachments-composition-signing-key",
    idle_timeout=datetime.timedelta(minutes=30),
    absolute_lifetime=datetime.timedelta(hours=8),
    cookie_secure=False,
)
_PWD = "ValidPassword123!"


class _CountingResponseGenerator:
    """Doble de `ResponseGenerator`: registra cada llamada en `order` (para verificar
    que la cuota se evalúa ANTES del generador) y devuelve texto fijo.
    """

    def __init__(self, order: list[str]) -> None:
        self.order = order
        self.calls = 0
        self.last_history: list[Message] | None = None

    def __call__(self, *, session: Any, history: list[Message]) -> str:
        self.calls += 1
        self.last_history = history
        self.order.append("generate")
        return f"respuesta generada #{self.calls}"


class _StreamingEchoGenerator:
    """Doble mínimo de `StreamingResponseGenerator` para el test de wiring SSE."""

    def __call__(self, *, session: Any, history: Any) -> Iterator[TurnFragment | TurnCompletion]:
        yield TurnFragment("hola")
        yield TurnCompletion(model_profile_id=session.model_profile, is_alternate_model=False)


@pytest.fixture
def call_order() -> list[str]:
    return []


@pytest.fixture
def response_generator(call_order: list[str]) -> _CountingResponseGenerator:
    return _CountingResponseGenerator(call_order)


@pytest.fixture
def client(tmp_path: Path, response_generator: _CountingResponseGenerator) -> Iterator[TestClient]:
    """TestClient con presupuestos de tokens CHICOS (calibrados por los tests) para
    forzar el truncado y el rechazo por presupuesto de mensaje sin documentos gigantes.
    """
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

    attachments_config = AttachmentsConfig(
        storage_dir=tmp_path,
        token_budget_per_file=200,
        token_budget_per_message=350,
    )

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_session_config] = lambda: _CONFIG
    app.dependency_overrides[get_registries] = lambda: bootstrap(Path("manifests"))
    app.dependency_overrides[get_response_generator] = lambda: response_generator
    app.dependency_overrides[get_streaming_response_generator] = lambda: _StreamingEchoGenerator()
    app.dependency_overrides[get_turn_stream_registry] = lambda: TurnStreamRegistry()
    app.dependency_overrides[get_attachments_config] = lambda: attachments_config

    with TestClient(app) as test_client:
        yield test_client


def _unique_username(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def login(client: TestClient, username: str, pwd: str) -> None:
    r = client.post("/api/auth/login", json={"username": username, "password": pwd})
    assert r.status_code == 200


def _create_user_and_login(client: TestClient, prefix: str) -> uuid.UUID:
    username = _unique_username(prefix)
    user_id = make_user(username, role="funcional", password_hash=hash_password(_PWD))
    login(client, username, _PWD)
    return user_id


def post_csrf(client: TestClient, url: str, json: dict[str, Any] | None = None) -> Any:
    csrf_token = client.cookies.get("resultarai_csrf")
    headers = {"X-CSRF-Token": csrf_token} if csrf_token else {}
    return client.post(url, json=json, headers=headers)


def _create_session(client: TestClient) -> str:
    response = post_csrf(client, "/api/sessions", json={"agent_id": "default_chat"})
    assert response.status_code == 201, response.text
    session_id: str = response.json()["id"]
    return session_id


def _make_attachment(
    owner_id: uuid.UUID,
    session_id: str,
    *,
    full_text: str | None,
    status: str = "ready",
    detected_type: str = "docx",
    scan_result: dict[str, Any] | None = None,
) -> uuid.UUID:
    """Crea un `Attachment` (+ `Extraction` si `full_text` no es `None`) directo en la
    base, simulando lo que dejaría el pipeline de subida+extracción real (ver docstring
    del módulo: tarea `7.1` pendiente).
    """
    attachment_id = uuid.uuid4()
    extraction_id: uuid.UUID | None = None
    with get_db_session() as db:
        if full_text is not None:
            extraction_id = uuid.uuid4()
            db.add(
                Extraction(
                    id=extraction_id,
                    tenant="default",
                    sha256=uuid.uuid4().hex + uuid.uuid4().hex,
                    full_text=full_text,
                    extractor_version="test@0",
                )
            )
            db.flush()
        db.add(
            Attachment(
                id=attachment_id,
                session_id=session_id,
                message_id=None,
                uploaded_by=str(owner_id),
                original_name="documento.docx",
                declared_mime="application/octet-stream",
                detected_type=detected_type,
                size_bytes=len(full_text or ""),
                sha256=uuid.uuid4().hex + uuid.uuid4().hex,
                storage_path=uuid.uuid4(),
                scan_result=scan_result,
                status=status,
                tenant="default",
                extraction_id=extraction_id,
            )
        )
    return attachment_id


def _send_message(
    client: TestClient,
    session_id: str,
    text: str,
    *,
    attachment_ids: list[uuid.UUID] | None = None,
    edits_message_id: str | None = None,
) -> Any:
    payload: dict[str, Any] = {"text": text}
    if attachment_ids is not None:
        payload["attachment_ids"] = [str(a) for a in attachment_ids]
    if edits_message_id is not None:
        payload["edits_message_id"] = edits_message_id
    return post_csrf(client, f"/api/sessions/{session_id}/messages", json=payload)


def _message_attachment_row(message_id: str, attachment_id: uuid.UUID) -> MessageAttachment:
    with get_db_session() as db:
        row = db.get(MessageAttachment, (uuid.UUID(message_id), attachment_id))
        assert row is not None
        db.expunge(row)
        return row


# --- Tarea 6.3: el adjunto entra al final, cuota evaluada antes del generador -------


def test_attachment_wraps_at_end_of_message_and_quota_evaluated_before_generator(
    client: TestClient, response_generator: _CountingResponseGenerator, call_order: list[str]
) -> None:
    owner_id = _create_user_and_login(client, "compose-owner")
    session_id = _create_session(client)
    attachment_id = _make_attachment(
        owner_id, session_id, full_text="Contenido corto del archivo adjunto de prueba."
    )

    with patch(
        "resultarai.app.use_cases.chat.turns.evaluate_quota_before_generation",
        wraps=lambda **kw: call_order.append("quota"),
    ):
        response = _send_message(
            client, session_id, "Revisá este archivo por favor", attachment_ids=[attachment_id]
        )

    assert response.status_code == 201, response.text
    body = response.json()
    content = body["user_message"]["content"]

    # El adjunto entra AL FINAL del contenido, después del texto del usuario.
    assert content.startswith("Revisá este archivo por favor\n\n")
    assert content.index("Revisá este archivo por favor") < content.index("<adjunto")
    assert '<adjunto nombre="documento.docx" tipo="docx" id="att_' in content
    assert content.rstrip().endswith("</adjunto>")
    assert "Contenido corto del archivo adjunto de prueba." in content

    # La cuota (seam de d16) se evaluó ANTES de invocar al generador.
    assert call_order == ["quota", "generate"]

    with get_db_session() as db:
        link = db.get(MessageAttachment, (uuid.UUID(body["user_message"]["id"]), attachment_id))
        assert link is not None
        assert link.truncated is False
        assert link.token_count > 0

        stored_attachment = db.get(Attachment, attachment_id)
        assert stored_attachment is not None
        assert stored_attachment.message_id == uuid.UUID(body["user_message"]["id"])


# --- Presupuesto por mensaje excedido -----------------------------------------------


def test_message_token_budget_exceeded_rejects_send_without_creating_message(
    client: TestClient,
) -> None:
    owner_id = _create_user_and_login(client, "budget-owner")
    session_id = _create_session(client)
    # Cada adjunto entra individualmente bajo el presupuesto POR ARCHIVO (200), pero
    # la SUMA de ambos supera el presupuesto por mensaje del fixture (350).
    filler = " ".join(f"palabra{n}" for n in range(150))
    attachment_a = _make_attachment(owner_id, session_id, full_text=f"Archivo A. {filler}")
    attachment_b = _make_attachment(owner_id, session_id, full_text=f"Archivo B. {filler}")

    response = _send_message(
        client, session_id, "Adjunto dos archivos", attachment_ids=[attachment_a, attachment_b]
    )

    assert response.status_code == 422, response.text
    assert response.json()["detail"]["error_code"] == "message_token_budget_exceeded"

    with get_db_session() as db:
        messages = (
            db.execute(select(Message).where(Message.session_id == session_id)).scalars().all()
        )
        assert messages == []


# --- Envío bloqueado por N3/N2 sin confirmar ------------------------------------------


def test_blocked_n3_attachment_rejects_send(client: TestClient) -> None:
    owner_id = _create_user_and_login(client, "n3-owner")
    session_id = _create_session(client)
    attachment_id = _make_attachment(
        owner_id, session_id, full_text="Password=secreto123", status="blocked"
    )

    response = _send_message(
        client, session_id, "Adjunto este archivo", attachment_ids=[attachment_id]
    )

    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert detail["error_code"] == "attachment_not_sendable"
    assert detail["params"]["status"] == "blocked"


def test_unconfirmed_n2_attachment_rejects_send(client: TestClient) -> None:
    owner_id = _create_user_and_login(client, "n2-owner")
    session_id = _create_session(client)
    attachment_id = _make_attachment(
        owner_id,
        session_id,
        full_text="Contacto: alguien@ejemplo.com",
        status="ready",
        scan_result={"requires_test_data_confirmation": True},
    )

    response = _send_message(
        client, session_id, "Adjunto este archivo", attachment_ids=[attachment_id]
    )

    assert response.status_code == 422, response.text
    assert response.json()["detail"]["error_code"] == "attachment_not_sendable"


def test_foreign_attachment_rejects_send(client: TestClient) -> None:
    """Un adjunto de OTRO usuario responde `attachment_not_found` (404), no filtra."""
    victim_id = make_user(_unique_username("n-victim"), password_hash=hash_password(_PWD))
    victim_session = f"sess_{uuid.uuid4().hex}"
    with get_db_session() as db:
        db.add(
            SessionModel(
                id=victim_session,
                model_profile="openai_gpt_4o",
                owner_user_id=victim_id,
                agent_id="default_chat",
                last_activity_at=get_utc_now(),
            )
        )
    attachment_id = _make_attachment(victim_id, victim_session, full_text="dato ajeno")

    _create_user_and_login(client, "n-attacker")
    attacker_session = _create_session(client)

    response = _send_message(
        client, attacker_session, "intento ajeno", attachment_ids=[attachment_id]
    )
    assert response.status_code == 404, response.text
    assert response.json()["detail"]["error_code"] == "attachment_not_found"


# --- Ramas reutilizan inserted_text byte-idéntica -------------------------------------


def test_branches_reuse_byte_identical_inserted_text(client: TestClient) -> None:
    owner_id = _create_user_and_login(client, "branch-owner")
    session_id = _create_session(client)

    # Documento con secciones, para que el texto del mensaje SÍ importe en la
    # relevancia -- si el truncado se re-corriera en la rama, el resultado cambiaría.
    filler = " ".join(f"relleno{n}" for n in range(60))
    full_text = (
        "# Manual\n\nIntro.\n\n"
        f"## Facturación\n\nContenido sobre facturación electrónica. {filler}\n\n"
        f"## Inventario\n\nContenido sobre inventario físico. {filler}\n"
    )
    attachment_id = _make_attachment(owner_id, session_id, full_text=full_text)

    first = _send_message(
        client, session_id, "Necesito info de facturación", attachment_ids=[attachment_id]
    )
    assert first.status_code == 201, first.text
    first_user_message_id = first.json()["user_message"]["id"]
    first_link = _message_attachment_row(first_user_message_id, attachment_id)

    # Edita el mensaje con un texto TOTALMENTE distinto (otro tema), mismo adjunto.
    edited = _send_message(
        client,
        session_id,
        "En realidad pregunto por el inventario físico",
        attachment_ids=[attachment_id],
        edits_message_id=first_user_message_id,
    )
    assert edited.status_code == 201, edited.text
    edited_user_message_id = edited.json()["user_message"]["id"]
    assert edited_user_message_id != first_user_message_id
    second_link = _message_attachment_row(edited_user_message_id, attachment_id)

    # Byte-idéntica: la rama NO volvió a truncar con el nuevo texto de relevancia.
    assert second_link.inserted_text == first_link.inserted_text
    assert second_link.token_count == first_link.token_count
    assert second_link.truncated == first_link.truncated

    with get_db_session() as db:
        stored_attachment = db.get(Attachment, attachment_id)
        assert stored_attachment is not None
        # `Attachment.message_id` sigue apuntando a la PRIMERA inserción.
        assert stored_attachment.message_id == uuid.UUID(first_user_message_id)


# --- Tarea 6.2: pedir otra parte, sin re-procesar -------------------------------------


def test_request_fragment_inserts_new_message_without_reextraction(client: TestClient) -> None:
    owner_id = _create_user_and_login(client, "fragment-owner")
    session_id = _create_session(client)

    filler = " ".join(f"relleno{n}" for n in range(60))
    full_text = (
        "# Manual\n\nIntro.\n\n"
        f"## Facturación\n\nContenido sobre facturación electrónica. {filler}\n\n"
        f"## Inventario\n\nContenido sobre inventario físico, con mucho detalle "
        f"adicional para forzar su omisión por presupuesto. {filler} {filler} {filler}\n"
    )
    attachment_id = _make_attachment(owner_id, session_id, full_text=full_text)

    first = _send_message(
        client, session_id, "Necesito info de facturación", attachment_ids=[attachment_id]
    )
    assert first.status_code == 201, first.text
    first_content = first.json()["user_message"]["content"]
    # La sección "Inventario" quedó omitida por presupuesto (documento calibrado para
    # exceder el presupuesto por archivo del fixture, 200 tokens).
    assert (
        '[… sección "Inventario" omitida por límite de espacio — pedila explícitamente '
        "si la necesitás …]" in first_content
    )

    # "Pedir otra parte": ningún extractor real debe re-invocarse (usa `full_text` YA
    # almacenado, tarea 6.2). Si algo del pipeline de extracción se llamara, estos
    # dobles lo delatan.
    with (
        patch(
            "resultarai.app.attachments.extraction.extract_attachment",
            side_effect=AssertionError("no debería re-extraerse el binario"),
        ),
        patch(
            "resultarai.app.attachments.extraction.run_extraction",
            side_effect=AssertionError("no debería re-parsearse el binario"),
        ),
    ):
        fragment_response = post_csrf(
            client,
            f"/api/sessions/{session_id}/attachments/{attachment_id}/fragment",
            json={"section_title": "Inventario"},
        )

    assert fragment_response.status_code == 201, fragment_response.text
    fragment_message = fragment_response.json()
    assert fragment_message["role"] == "user"
    assert "Contenido sobre inventario físico" in fragment_message["content"]
    assert '<adjunto nombre="documento.docx"' in fragment_message["content"]

    # Cuelga de la rama activa (el mensaje de usuario del turno anterior -- no hubo
    # respuesta de agente real en este `client` para ese primer turno síncrono, así que
    # el leaf activo es el `assistant_message` generado por el doble).
    assert fragment_message["parent_id"] == first.json()["assistant_message"]["id"]

    with get_db_session() as db:
        link = db.get(MessageAttachment, (uuid.UUID(fragment_message["id"]), attachment_id))
        assert link is not None
        assert "Contenido sobre inventario físico" in link.inserted_text

        # La inserción ORIGINAL (del primer mensaje) sigue intacta -- append-only, no
        # se re-truncó.
        original_link = _message_attachment_row(first.json()["user_message"]["id"], attachment_id)
        assert (
            '[… sección "Inventario" omitida por límite de espacio' in original_link.inserted_text
        )


def test_request_fragment_unknown_section_returns_404(client: TestClient) -> None:
    owner_id = _create_user_and_login(client, "fragment-404")
    session_id = _create_session(client)
    attachment_id = _make_attachment(
        owner_id, session_id, full_text="# Manual\n\n## Sección Real\n\nTexto.\n"
    )

    response = post_csrf(
        client,
        f"/api/sessions/{session_id}/attachments/{attachment_id}/fragment",
        json={"section_title": "Sección Que No Existe"},
    )
    assert response.status_code == 404
    assert response.json()["detail"]["error_code"] == "section_not_found"


# --- Vista previa pre y post inserción (soporte de 8.1/8.3) --------------------------


def test_preview_pre_and_post_insertion(client: TestClient) -> None:
    owner_id = _create_user_and_login(client, "preview-owner")
    session_id = _create_session(client)
    full_text = "Contenido corto del archivo, cabe entero en el presupuesto."
    attachment_id = _make_attachment(owner_id, session_id, full_text=full_text)

    pre = client.get(f"/api/attachments/{attachment_id}/preview")
    assert pre.status_code == 200, pre.text
    pre_body = pre.json()
    assert pre_body["inserted"] is False
    assert pre_body["text"] == full_text
    assert pre_body["included_percent"] == 100
    assert pre_body["truncated"] is False
    assert pre_body["token_count"] > 0

    status_pre = client.get(f"/api/attachments/{attachment_id}")
    assert status_pre.status_code == 200, status_pre.text
    assert status_pre.json()["inserted"] is False
    assert status_pre.json()["token_count"] == pre_body["token_count"]

    send = _send_message(client, session_id, "Mirá este archivo", attachment_ids=[attachment_id])
    assert send.status_code == 201, send.text

    post = client.get(f"/api/attachments/{attachment_id}/preview")
    assert post.status_code == 200, post.text
    post_body = post.json()
    assert post_body["inserted"] is True
    assert post_body["text"] == full_text
    assert post_body["truncated"] is False

    status_post = client.get(f"/api/attachments/{attachment_id}")
    assert status_post.status_code == 200, status_post.text
    assert status_post.json()["inserted"] is True
    assert status_post.json()["sendable"] is True


def test_preview_by_foreign_user_returns_404(client: TestClient) -> None:
    owner_id = make_user(_unique_username("preview-victim"), password_hash=hash_password(_PWD))
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
    attachment_id = _make_attachment(owner_id, session_id, full_text="dato ajeno")

    _create_user_and_login(client, "preview-attacker")
    response = client.get(f"/api/attachments/{attachment_id}/preview")
    assert response.status_code == 404


# --- Wiring del streaming (mismo contrato aditivo que el endpoint síncrono) ----------


def test_streaming_endpoint_accepts_attachment_ids(client: TestClient) -> None:
    owner_id = _create_user_and_login(client, "stream-owner")
    session_id = _create_session(client)
    attachment_id = _make_attachment(owner_id, session_id, full_text="Contenido de prueba.")

    csrf_token = client.cookies.get("resultarai_csrf")
    headers = {"X-CSRF-Token": csrf_token} if csrf_token else {}
    with client.stream(
        "POST",
        f"/api/sessions/{session_id}/messages/stream",
        json={"text": "Revisá esto", "attachment_ids": [str(attachment_id)]},
        headers=headers,
    ) as response:
        assert response.status_code == 200, response.read()
        user_message_id = response.headers["X-User-Message-Id"]
        list(response.iter_text())  # drena el stream

    with get_db_session() as db:
        message = db.get(Message, uuid.UUID(user_message_id))
        assert message is not None
        assert "<adjunto nombre=" in message.content
        link = db.get(MessageAttachment, (uuid.UUID(user_message_id), attachment_id))
        assert link is not None
