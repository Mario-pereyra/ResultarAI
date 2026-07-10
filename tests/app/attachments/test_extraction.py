"""Tests de la orquestacion de extraccion y su transicion de estados (d14, tarea 2.5, 2.4).

Cubre la transicion `uploaded -> extracting -> ready | error` sobre el schema de `b04` y la
integracion de la proteccion zip-bomb en el pipeline de extraccion:

- exito -> `ready` con el `ExtractionResult`;
- timeout del worker -> `error` con causa `extraction_timeout` en `scan_result`;
- OOXML zip-bomb -> `error` con causa `zip_bomb_suspected`, sin gastar worker ni memoria, y
  la plataforma sigue operativa (una extraccion posterior funciona).
"""

from __future__ import annotations

import io
import uuid
import zipfile
from pathlib import Path

from sqlalchemy.orm import Session as DbSession

from resultarai.adapters.persistence_postgres.connection import get_db_session
from resultarai.adapters.persistence_postgres.models import Attachment
from resultarai.app.attachments import AttachmentsConfig, extract_attachment
from resultarai.core.ports.extraction import AttachmentKind, ExtractionInput
from tests.app.attachments.fakes import fake_extract_ok, fake_extract_slow

_MIB = 1024 * 1024
_MEMORY_LIMIT = 384 * _MIB


def _config(
    tmp_path: Path,
    *,
    timeout: float = 10.0,
    zip_max: int = 100 * _MIB,
    zip_ratio: float = 50.0,
) -> AttachmentsConfig:
    return AttachmentsConfig(
        storage_dir=tmp_path / "attachments",
        tenant="test-tenant",
        extraction_timeout_seconds=timeout,
        extraction_memory_limit_bytes=_MEMORY_LIMIT,
        zip_bomb_max_uncompressed_bytes=zip_max,
        zip_bomb_max_ratio=zip_ratio,
    )


def _make_uploaded_attachment(db: DbSession, *, name: str, detected_type: str) -> Attachment:
    attachment = Attachment(
        session_id=None,
        message_id=None,
        uploaded_by="tester",
        original_name=name,
        declared_mime="application/octet-stream",
        detected_type=detected_type,
        size_bytes=10,
        sha256=uuid.uuid4().hex + uuid.uuid4().hex,  # 64 hex chars
        storage_path=None,
        scan_result=None,
        status="uploaded",
        tenant="test-tenant",
    )
    db.add(attachment)
    db.flush()
    return attachment


def _zip_bomb_bytes(uncompressed_bytes: int) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("bloat.bin", b"\x00" * uncompressed_bytes)
    return buffer.getvalue()


def test_extract_attachment_success_sets_ready(tmp_path: Path) -> None:
    """Un extractor que retorna bien lleva el adjunto de `uploaded` a `ready`."""
    config = _config(tmp_path)
    with get_db_session() as db:
        attachment = _make_uploaded_attachment(db, name="notas.txt", detected_type="text")
        source = ExtractionInput(kind=AttachmentKind.TEXT, filename="notas.txt", content=b"hola")

        outcome = extract_attachment(db, attachment, fake_extract_ok, source, config)

        assert outcome.attachment.status == "ready"
        assert outcome.error is None
        assert outcome.result is not None
        assert outcome.result.full_text == "contenido extraido de notas.txt"
        attachment_id = attachment.id

    with get_db_session() as db:
        stored = db.get(Attachment, attachment_id)
        assert stored is not None
        assert stored.status == "ready"


def test_extract_attachment_timeout_sets_error_with_cause(tmp_path: Path) -> None:
    """Un extractor que agota el timeout deja el adjunto en `error` con causa especifica."""
    config = _config(tmp_path, timeout=0.4)
    with get_db_session() as db:
        attachment = _make_uploaded_attachment(db, name="grande.txt", detected_type="text")
        source = ExtractionInput(kind=AttachmentKind.TEXT, filename="grande.txt", content=b"hola")

        outcome = extract_attachment(db, attachment, fake_extract_slow, source, config)

        assert outcome.attachment.status == "error"
        assert outcome.result is None
        assert outcome.error is not None
        assert outcome.error.error_code == "extraction_timeout"
        attachment_id = attachment.id

    with get_db_session() as db:
        stored = db.get(Attachment, attachment_id)
        assert stored is not None
        assert stored.status == "error"
        assert stored.scan_result is not None
        assert stored.scan_result["extraction_error"]["error_code"] == "extraction_timeout"


def test_extract_attachment_zip_bomb_sets_error_and_platform_survives(tmp_path: Path) -> None:
    """Un OOXML zip-bomb deja el adjunto en `error` sin agotar memoria; luego todo sigue OK.

    El chequeo zip-bomb corre ANTES del worker: la bomba se rechaza leyendo el indice del
    ZIP (reason `declared_size`), sin descomprimir. `fake_extract_ok` se pasa como extractor
    pero nunca se invoca. Una extraccion posterior confirma que la plataforma sigue operativa.
    """
    config = _config(tmp_path, zip_max=8 * _MIB)
    bomb = _zip_bomb_bytes(64 * _MIB)

    with get_db_session() as db:
        attachment = _make_uploaded_attachment(db, name="bomba.xlsx", detected_type="excel")
        source = ExtractionInput(
            kind=AttachmentKind.SPREADSHEET, filename="bomba.xlsx", content=bomb
        )

        outcome = extract_attachment(db, attachment, fake_extract_ok, source, config)

        assert outcome.attachment.status == "error"
        assert outcome.error is not None
        assert outcome.error.error_code == "zip_bomb_suspected"
        assert outcome.error.params["reason"] == "declared_size"
        bomb_id = attachment.id

        # La plataforma sigue operativa: otra extraccion (texto) se procesa sin problema.
        healthy = _make_uploaded_attachment(db, name="ok.txt", detected_type="text")
        healthy_source = ExtractionInput(
            kind=AttachmentKind.TEXT, filename="ok.txt", content=b"hola"
        )
        healthy_outcome = extract_attachment(db, healthy, fake_extract_ok, healthy_source, config)
        assert healthy_outcome.attachment.status == "ready"

    with get_db_session() as db:
        stored = db.get(Attachment, bomb_id)
        assert stored is not None
        assert stored.status == "error"
        assert stored.scan_result is not None
        assert stored.scan_result["extraction_error"]["error_code"] == "zip_bomb_suspected"
