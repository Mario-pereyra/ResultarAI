# ruff: noqa: E402
"""Tests del pipeline de produccion: dedup por sha256 y wiring real (d14, tarea 7.1).

Cubre el escenario ANEXO §2 P2/§5 "resubida del mismo archivo reutiliza la extraccion"
(sin re-parsear el binario) y sus vecinos inmediatos, todos sobre `process_attachment`
(`app/attachments/pipeline.py`):

- binario nuevo -> extrae de verdad (worker aislado real, extractor fake picklable) y
  persiste una fila en `extractions` con `extractor_version`, vinculada por
  `extraction_id`, en estado `ready`;
- mismo binario resubido (mismo tenant+sha256) -> NO vuelve a invocar al extractor (se
  prueba con un `resolve` que levanta si se lo llama), se vincula a la MISMA fila de
  `extractions`, y su estado final sale de RE-escanear el `full_text` ya persistido;
- el mismo binario con un secreto N3 -> el camino dedup tambien re-escanea (no copia el
  `scan_result` del primero) y dos deja `blocked`;
- `storage_path` ausente (fila inconsistente, sin extraccion previa) -> `error` con
  causa tipada `missing_binary`, sin excepcion;
- la carrera de insercion documentada en `_persist_extraction` (dos subidas simultaneas
  del mismo binario nuevo) reutiliza la fila ganadora en vez de propagar el
  `IntegrityError`;
- wiring end-to-end: subir por el endpoint real (`POST /api/attachments`) dispara la
  extraccion via `BackgroundTasks` (el runner default, `get_extraction_runner`) sin que
  el test invoque el pipeline a mano.
"""

from __future__ import annotations

import hashlib
import io
import os
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet

# Fijar una clave estable en el entorno antes de importar nada que inicialice TotpConfig
# (mismo patron que tests/app/attachments/test_upload.py y tests/app/chat/test_sessions.py).
_STABLE_KEY = Fernet.generate_key().decode("utf-8")
os.environ.setdefault("IDENTITY_TOTP_ENCRYPTION_KEY", _STABLE_KEY)

import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as DbSession

from resultarai.adapters.persistence_postgres.connection import SessionLocal, get_db_session
from resultarai.adapters.persistence_postgres.models import Attachment, Extraction, get_utc_now
from resultarai.adapters.persistence_postgres.models import Session as SessionModel
from resultarai.app.api import create_app
from resultarai.app.api.attachments import get_attachments_config
from resultarai.app.attachments import AttachmentsConfig
from resultarai.app.attachments.pipeline import (
    ExtractorResolver,
    _persist_extraction,  # whitebox: cubre directo el camino de carrera bajo SAVEPOINT
    find_extraction,
    process_attachment,
)
from resultarai.app.attachments.worker import Extractor
from resultarai.app.identity import (
    SessionConfig,
    get_db,
    get_session_config,
    hash_password,
)
from resultarai.core.ports.extraction import AttachmentKind
from tests.app.attachments.fakes import (
    PDF_SCANNED_EXTRACTOR_VERSION,
    PDF_SCANNED_FULL_TEXT,
    SECRET_TEXT,
    fake_extract_ok,
    fake_extract_with_secret,
)
from tests.app.identity.conftest import make_user

_CONFIG = SessionConfig(
    signing_key="test-pipeline-signing-key-1234567890",
    idle_timeout=datetime.timedelta(minutes=30),
    absolute_lifetime=datetime.timedelta(hours=8),
    cookie_secure=False,
)

_PWD = "ValidPassword123!"


def _config(tmp_path: Path) -> AttachmentsConfig:
    """Config con un `RLIMIT_AS` generoso: estos tests ejercitan el DEDUP, no el limite de
    memoria del worker (eso ya lo cubre `test_worker.py`/`test_extraction.py` con fakes
    dedicados) -- un tope ajustado innecesariamente solo arriesgaria falsos negativos por
    presion de memoria acumulada de la sesion de tests (muchos forks reales del worker
    aislado en la misma corrida)."""
    return AttachmentsConfig(
        storage_dir=tmp_path / "attachments",
        tenant="test-tenant",
        extraction_memory_limit_bytes=1536 * 1024 * 1024,
    )


def _write_binary(config: AttachmentsConfig, content: bytes) -> uuid.UUID:
    """Escribe `content` a disco bajo un UUID nuevo (como lo hace `upload.py` en cada
    subida) y devuelve el UUID; el binario real existe aunque el fake extractor no lo
    lea, para que el test no dependa de un atajo del fake."""
    storage_uuid = uuid.uuid4()
    config.storage_dir.mkdir(parents=True, exist_ok=True)
    (config.storage_dir / str(storage_uuid)).write_bytes(content)
    return storage_uuid


def _make_uploaded_attachment(
    db: DbSession,
    *,
    tenant: str,
    sha256: str,
    storage_path: uuid.UUID | None,
    name: str = "archivo.txt",
    detected_type: str = "text",
) -> Attachment:
    attachment = Attachment(
        session_id=None,
        message_id=None,
        uploaded_by="tester",
        original_name=name,
        declared_mime="application/octet-stream",
        detected_type=detected_type,
        size_bytes=10,
        sha256=sha256,
        storage_path=storage_path,
        scan_result=None,
        status="uploaded",
        tenant=tenant,
    )
    db.add(attachment)
    db.flush()
    return attachment


def _resolver_returning(extractor: Extractor) -> ExtractorResolver:
    """`resolve` que ignora `kind` y siempre devuelve `extractor` (fake picklable)."""

    def _resolve(kind: AttachmentKind) -> Extractor:
        return extractor

    return _resolve


def _resolver_recording(extractor: Extractor, calls: list[AttachmentKind]) -> ExtractorResolver:
    """Como `_resolver_returning`, pero deja constancia de cada `kind` invocado."""

    def _resolve(kind: AttachmentKind) -> Extractor:
        calls.append(kind)
        return extractor

    return _resolve


def _resolver_forbidden() -> ExtractorResolver:
    """`resolve` que SIEMPRE falla: prueba que el camino dedup nunca lo invoca."""

    def _resolve(kind: AttachmentKind) -> Extractor:
        raise AssertionError(
            "no debia re-parsear: el binario ya tiene una extraccion persistida (dedup)"
        )

    return _resolve


# --------------------------------------------------------------------------------------
# Binario nuevo (camino de extraccion real)
# --------------------------------------------------------------------------------------


def test_process_attachment_new_binary_extracts_and_persists_extraction(tmp_path: Path) -> None:
    """Un binario sin extraccion previa se extrae de verdad y queda `ready`."""
    config = _config(tmp_path)
    content = b"contenido de prueba nuevo"
    sha256 = hashlib.sha256(content).hexdigest()
    calls: list[AttachmentKind] = []

    with get_db_session() as db:
        storage_uuid = _write_binary(config, content)
        attachment = _make_uploaded_attachment(
            db, tenant=config.tenant, sha256=sha256, storage_path=storage_uuid
        )

        result = process_attachment(
            db, attachment, config, resolve=_resolver_recording(fake_extract_ok, calls)
        )

        assert result.reused is False
        assert result.error is None
        assert result.extraction is not None
        assert result.attachment.status == "ready"
        assert result.attachment.extraction_id == result.extraction.id
        assert calls == [AttachmentKind.TEXT]  # se invoco el extractor UNA vez
        attachment_id = attachment.id
        extraction_id = result.extraction.id

    with get_db_session() as db:
        stored = db.get(Attachment, attachment_id)
        assert stored is not None
        assert stored.status == "ready"
        assert stored.extraction_id == extraction_id

        extraction = db.get(Extraction, extraction_id)
        assert extraction is not None
        assert extraction.tenant == config.tenant
        assert extraction.sha256 == sha256
        assert extraction.full_text == "contenido extraido de archivo.txt"
        assert extraction.extractor_version == "fake@1.0"


# --------------------------------------------------------------------------------------
# Resubida del mismo archivo (escenario principal de la tarea 7.1, ANEXO §2 P2, §5)
# --------------------------------------------------------------------------------------


def test_process_attachment_reused_binary_reuses_extraction_without_reparsing(
    tmp_path: Path,
) -> None:
    """Escenario "resubida del mismo archivo reutiliza la extraccion" sin re-parsear.

    Dos adjuntos distintos (mismo tenant+sha256, storage_path DISTINTO -- asi se
    comporta `upload.py` en cada subida real): el segundo se vincula a la MISMA fila de
    `extractions` que el primero y su `resolve` esta armado para levantar si se lo
    invoca -- probando que el binario nunca se vuelve a parsear.
    """
    config = _config(tmp_path)
    content = b"contenido compartido entre dos subidas"
    sha256 = hashlib.sha256(content).hexdigest()

    with get_db_session() as db:
        storage_uuid_1 = _write_binary(config, content)
        attachment1 = _make_uploaded_attachment(
            db, tenant=config.tenant, sha256=sha256, storage_path=storage_uuid_1, name="primero.txt"
        )
        first_calls: list[AttachmentKind] = []
        result1 = process_attachment(
            db, attachment1, config, resolve=_resolver_recording(fake_extract_ok, first_calls)
        )
        assert result1.reused is False
        assert len(first_calls) == 1
        assert result1.extraction is not None
        extraction_id = result1.extraction.id

        storage_uuid_2 = _write_binary(config, content)
        attachment2 = _make_uploaded_attachment(
            db, tenant=config.tenant, sha256=sha256, storage_path=storage_uuid_2, name="segundo.txt"
        )

        result2 = process_attachment(db, attachment2, config, resolve=_resolver_forbidden())

        assert result2.reused is True
        assert result2.error is None
        assert result2.extraction is not None
        assert result2.extraction.id == extraction_id  # MISMA fila, no una nueva
        assert attachment2.extraction_id == extraction_id
        assert attachment2.status == "ready"  # sale del re-escaneo del full_text persistido
        attachment2_id = attachment2.id

    with get_db_session() as db:
        rows = (
            db.query(Extraction)
            .filter(Extraction.tenant == config.tenant, Extraction.sha256 == sha256)
            .all()
        )
        assert len(rows) == 1  # una sola fila para el mismo binario (ANEXO §2 P2)
        assert rows[0].id == extraction_id

        stored2 = db.get(Attachment, attachment2_id)
        assert stored2 is not None
        assert stored2.extraction_id == extraction_id
        assert stored2.status == "ready"


def test_process_attachment_dedup_path_rescans_and_blocks_on_secret(tmp_path: Path) -> None:
    """Adjunto con secreto N3 resubido: el camino dedup RE-escanea (no copia) y `blocked`.

    El binario nunca se re-parsea (mismo `resolve` prohibido que el escenario anterior),
    pero el hallazgo N3 SI se recalcula sobre el `full_text` ya persistido -- decision
    documentada en `pipeline.py`/`extraction.py`: solo el PARSEO se salta, los escaneos
    se re-corren siempre.
    """
    config = _config(tmp_path)
    content = SECRET_TEXT.encode("utf-8")
    sha256 = hashlib.sha256(content).hexdigest()

    with get_db_session() as db:
        storage_uuid_1 = _write_binary(config, content)
        attachment1 = _make_uploaded_attachment(
            db,
            tenant=config.tenant,
            sha256=sha256,
            storage_path=storage_uuid_1,
            name="secreto1.txt",
        )
        result1 = process_attachment(
            db, attachment1, config, resolve=_resolver_returning(fake_extract_with_secret)
        )
        assert result1.attachment.status == "blocked"
        assert result1.extraction is not None
        extraction_id = result1.extraction.id

        storage_uuid_2 = _write_binary(config, content)
        attachment2 = _make_uploaded_attachment(
            db,
            tenant=config.tenant,
            sha256=sha256,
            storage_path=storage_uuid_2,
            name="secreto2.txt",
        )

        result2 = process_attachment(db, attachment2, config, resolve=_resolver_forbidden())

        assert result2.reused is True
        assert result2.extraction is not None
        assert result2.extraction.id == extraction_id
        assert result2.attachment.status == "blocked"  # re-escaneado, no un fallback a ready
        scan_result = result2.attachment.scan_result
        assert scan_result is not None
        assert scan_result["n3_findings"][0]["secret_type"] == "openai_api_key"


def test_process_attachment_dedup_path_preserves_pdf_scanned_signal(tmp_path: Path) -> None:
    """Escenario "PDF escaneado ofrece OCR diferido" (ANEXO §2.2, §10) + resubida.

    `PdfStructure.is_scanned` no se persiste en `extractions` (b04 sin migraciones para
    este change): la resubida del MISMO PDF escaneado (dedup, sin re-parsear -- mismo
    `resolve` prohibido que los demas tests de este archivo) debe seguir mostrando la
    causa "PDF escaneado" porque `finalize_extracted_attachment` la RE-deriva del
    `full_text` ya persistido (decision documentada en el docstring del modulo).

    La fila de `extractions` se SIEMBRA directo (mismo criterio que
    `test_persist_extraction_handles_concurrent_insert_race`) con `PDF_SCANNED_FULL_TEXT`
    -- fuente unica compartida con `fake_extract_pdf_scanned`, byte-identica a lo que la
    extraccion real persiste (texto limpio: sanitizacion identidad; el camino fresco
    worker->deteccion ya lo cubre `test_extraction.py::
    test_extract_attachment_scanned_pdf_marks_ready_with_offer_no_ocr`). Sembrar en vez
    de extraer evita a proposito el worker aislado real: el camino dedup por definicion
    NO corre worker, y el proceso hijo del worker es susceptible a la presion de memoria
    de la maquina bajo la suite completa (fragilidad preexistente documentada en
    `openspec/BACKLOG-DESCUBRIMIENTOS.md`) -- asi este test es 100% determinista. Ademas,
    sin `scan_result` previo de ningun otro adjunto, la UNICA fuente posible de la señal
    es la re-derivacion del texto persistido (no hay nada que copiar).
    """
    config = _config(tmp_path)
    content = b"binario de PDF escaneado (el fake ignora el contenido real)"
    sha256 = hashlib.sha256(content).hexdigest()

    with get_db_session() as db:
        seeded = Extraction(
            tenant=config.tenant,
            sha256=sha256,
            full_text=PDF_SCANNED_FULL_TEXT,
            extractor_version=PDF_SCANNED_EXTRACTOR_VERSION,
        )
        db.add(seeded)
        db.flush()
        extraction_id = seeded.id

    with get_db_session() as db:
        storage_uuid = _write_binary(config, content)
        attachment = _make_uploaded_attachment(
            db,
            tenant=config.tenant,
            sha256=sha256,
            storage_path=storage_uuid,
            name="escaneado2.pdf",
            detected_type="pdf",
        )

        result = process_attachment(db, attachment, config, resolve=_resolver_forbidden())

        assert result.reused is True  # NO se re-parseo el binario
        assert result.error is None
        assert result.extraction is not None
        assert result.extraction.id == extraction_id  # MISMA fila de extractions
        assert result.attachment.status == "ready"  # advierte, no bloquea
        scan_result = result.attachment.scan_result
        assert scan_result is not None
        # La señal sobrevive al dedup: re-derivada del full_text persistido, no copiada.
        assert scan_result["pdf_scanned"] == {"page_count": 2, "avg_chars_per_page": 2.0}
        attachment_id = attachment.id

    with get_db_session() as db:
        stored = db.get(Attachment, attachment_id)
        assert stored is not None
        assert stored.status == "ready"
        assert stored.scan_result is not None
        assert stored.scan_result["pdf_scanned"] == {"page_count": 2, "avg_chars_per_page": 2.0}


# --------------------------------------------------------------------------------------
# Fila inconsistente: sin binario ni extraccion previa
# --------------------------------------------------------------------------------------


def test_process_attachment_missing_storage_path_sets_error_without_raising(
    tmp_path: Path,
) -> None:
    """`storage_path` ausente (y sin extraccion previa) -> `error` tipado, sin excepcion."""
    config = _config(tmp_path)
    sha256 = hashlib.sha256(b"binario que nunca se escribio a disco").hexdigest()

    with get_db_session() as db:
        attachment = _make_uploaded_attachment(
            db, tenant=config.tenant, sha256=sha256, storage_path=None, name="perdido.txt"
        )

        result = process_attachment(db, attachment, config)  # resolve default: no se invoca

        assert result.reused is False
        assert result.extraction is None
        assert result.error is not None
        assert result.error.error_code == "extraction_failed"
        assert result.error.params == {"cause": "missing_binary"}
        assert result.attachment.status == "error"
        attachment_id = attachment.id

    with get_db_session() as db:
        stored = db.get(Attachment, attachment_id)
        assert stored is not None
        assert stored.status == "error"
        assert stored.scan_result is not None
        assert stored.scan_result["extraction_error"] == {
            "error_code": "extraction_failed",
            "params": {"cause": "missing_binary"},
        }


# --------------------------------------------------------------------------------------
# Carrera de insercion (docstring de `_persist_extraction`)
# --------------------------------------------------------------------------------------


def test_persist_extraction_handles_concurrent_insert_race(tmp_path: Path) -> None:
    """Dos subidas simultaneas del mismo binario nuevo: la perdedora reutiliza la fila.

    Simula la carrera insertando la fila "ganadora" ANTES de invocar `_persist_extraction`
    (la funcion que corre bajo SAVEPOINT en el camino real cuando el lookup inicial de
    `process_attachment` no encontro nada porque la otra subida todavia no habia
    comprometido su insercion). El `IntegrityError` del UniqueConstraint
    (`uq_extractions_tenant_sha256`) no se propaga: se re-consulta y se devuelve la fila
    ganadora, nunca una segunda fila para el mismo `(tenant, sha256)`.
    """
    config = _config(tmp_path)
    sha256 = hashlib.sha256(b"contenido en carrera de insercion").hexdigest()

    with get_db_session() as db:
        winner = Extraction(
            tenant=config.tenant,
            sha256=sha256,
            full_text="texto de la extraccion ganadora",
            extractor_version="racer@1.0",
        )
        db.add(winner)
        db.flush()
        winner_id = winner.id

    with get_db_session() as db:
        attachment = _make_uploaded_attachment(
            db,
            tenant=config.tenant,
            sha256=sha256,
            storage_path=uuid.uuid4(),
            name="tardio.txt",
        )

        reused = _persist_extraction(db, attachment, "texto perdedor de la carrera", "loser@1.0")

        assert reused.id == winner_id
        assert reused.full_text == "texto de la extraccion ganadora"

    with get_db_session() as db:
        rows = (
            db.query(Extraction)
            .filter(Extraction.tenant == config.tenant, Extraction.sha256 == sha256)
            .all()
        )
        assert len(rows) == 1
        assert rows[0].id == winner_id


def test_find_extraction_returns_none_for_unknown_sha256(tmp_path: Path) -> None:
    """`find_extraction` distingue "binario nunca visto" de una fila real (sanity check)."""
    with get_db_session() as db:
        assert find_extraction(db, tenant="test-tenant", sha256="0" * 64) is None


# --------------------------------------------------------------------------------------
# Wiring: el endpoint real dispara la extraccion via BackgroundTasks (sin invocacion manual)
# --------------------------------------------------------------------------------------


@pytest.fixture
def attachments_config(tmp_path: Path) -> AttachmentsConfig:
    return _config(tmp_path)


@pytest.fixture
def client(attachments_config: AttachmentsConfig) -> Iterator[TestClient]:
    """TestClient con overrides de DB, config de sesion y config de adjuntos.

    Deliberadamente NO sobreescribe `get_extraction_runner`: este es el UNICO test del
    change que ejercita el proveedor de PRODUCCION tal cual quedo cableado en
    `app/api/attachments.py` (el resto de los tests de este archivo llaman
    `process_attachment` directo, sin pasar por HTTP).
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

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_session_config] = lambda: _CONFIG
    app.dependency_overrides[get_attachments_config] = lambda: attachments_config

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


def _post_upload(client: TestClient, session_id: str, filename: str, content: bytes) -> Any:
    csrf_token = client.cookies.get("resultarai_csrf")
    headers = {"X-CSRF-Token": csrf_token} if csrf_token else {}
    return client.post(
        "/api/attachments",
        files={"file": (filename, io.BytesIO(content), "text/plain")},
        data={"session_id": session_id},
        headers=headers,
    )


def test_upload_endpoint_wires_real_extraction_pipeline_to_ready(
    client: TestClient,
) -> None:
    """Subir por el endpoint real deja el adjunto `ready` sin invocar el pipeline a mano.

    `BackgroundTasks` de FastAPI corre DESPUES del 201 (decision documentada en
    `pipeline.py`); `TestClient` las ejecuta antes de devolver la respuesta al llamador.
    El endpoint comitea a mano ANTES de encolar la extraccion (docstring de
    `upload_attachment_endpoint`: con el scope default de una dependencia `yield`
    -- `scope="request"` -- el `commit()` de `get_db` correria DESPUES de las
    background tasks, no antes), asi que para cuando este test recibe la respuesta 201,
    la extraccion real (extractor de texto de verdad, worker aislado real, sin fakes) ya
    corrio de punta a punta sobre un adjunto que su propia sesion aislada si pudo ver.
    """
    owner_id = _login_new_user(client, "att-wired")
    session_id = _make_session(owner_id)

    response = _post_upload(client, session_id, "notas.txt", b"contenido limpio de prueba")
    assert response.status_code == 201, response.text
    attachment_id = uuid.UUID(response.json()["id"])

    with get_db_session() as db:
        attachment = db.get(Attachment, attachment_id)
        assert attachment is not None
        assert attachment.status == "ready"
        assert attachment.extraction_id is not None
        assert attachment.extraction is not None
        assert "contenido limpio de prueba" in attachment.extraction.full_text
