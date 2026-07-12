"""Tests de la purga por retencion (d14, tarea 7.2, ANEXO §5).

Cubre los escenarios de `retention.py`:

- un adjunto vencido pierde el binario en disco Y su `full_text` compartido (la
  `Extraction` se borra), pero la `inserted_text` de `message_attachments` sobrevive
  intacta (tabla append-only, ver el docstring del modulo);
- un adjunto NO vencido queda intacto (binario y extraccion sin tocar);
- dedup: dos adjuntos comparten la misma `Extraction`; mientras uno de los dos siga
  vigente, el `full_text` se conserva -- recien se borra cuando AMBOS vencen.
"""

from __future__ import annotations

import datetime
import hashlib
import uuid
from pathlib import Path

from resultarai.adapters.persistence_postgres.connection import get_db_session
from resultarai.adapters.persistence_postgres.models import (
    Attachment,
    Extraction,
    Message,
    MessageAttachment,
    get_utc_now,
)
from resultarai.adapters.persistence_postgres.models import Session as SessionModel
from resultarai.app.attachments.config import AttachmentsConfig
from resultarai.app.attachments.retention import purge_expired_attachments

_TENANT = "test-tenant"
_MODEL_PROFILE = "openai_gpt_4o"


def _config(tmp_path: Path, *, retention_days: int = 90) -> AttachmentsConfig:
    return AttachmentsConfig(
        storage_dir=tmp_path / "attachments",
        tenant=_TENANT,
        retention_days=retention_days,
    )


def _write_binary(config: AttachmentsConfig, content: bytes) -> uuid.UUID:
    storage_uuid = uuid.uuid4()
    config.storage_dir.mkdir(parents=True, exist_ok=True)
    (config.storage_dir / str(storage_uuid)).write_bytes(content)
    return storage_uuid


def _make_session_and_message(owner: str = "owner-1") -> tuple[str, uuid.UUID]:
    session_id = f"sess_{uuid.uuid4().hex}"
    with get_db_session() as db:
        db.add(SessionModel(id=session_id, model_profile=_MODEL_PROFILE))
        db.flush()
        message = Message(
            session_id=session_id,
            role="user",
            content="hola, adjunto un archivo",
            model_profile=_MODEL_PROFILE,
        )
        db.add(message)
        db.flush()
        message_id = message.id
    return session_id, message_id


def _make_extraction(full_text: str, sha256: str) -> uuid.UUID:
    with get_db_session() as db:
        extraction = Extraction(
            tenant=_TENANT, sha256=sha256, full_text=full_text, extractor_version="fake@1.0"
        )
        db.add(extraction)
        db.flush()
        return extraction.id


def _make_attachment(
    *,
    session_id: str | None,
    storage_path: uuid.UUID | None,
    extraction_id: uuid.UUID | None,
    created_at: datetime.datetime,
    name: str = "archivo.txt",
) -> uuid.UUID:
    with get_db_session() as db:
        attachment = Attachment(
            session_id=session_id,
            message_id=None,
            uploaded_by="owner-1",
            original_name=name,
            declared_mime="text/plain",
            detected_type="text",
            size_bytes=10,
            sha256=hashlib.sha256(name.encode()).hexdigest(),
            storage_path=storage_path,
            scan_result=None,
            status="ready",
            tenant=_TENANT,
            extraction_id=extraction_id,
            created_at=created_at,
        )
        db.add(attachment)
        db.flush()
        return attachment.id


def _make_message_attachment(message_id: uuid.UUID, attachment_id: uuid.UUID) -> None:
    with get_db_session() as db:
        db.add(
            MessageAttachment(
                message_id=message_id,
                attachment_id=attachment_id,
                inserted_text="<adjunto id=x1y2>contenido insertado del adjunto</adjunto>",
                token_count=42,
                truncated=False,
            )
        )


def test_purge_deletes_binary_and_full_text_but_keeps_inserted_text(tmp_path: Path) -> None:
    """Adjunto vencido: se borra el binario Y el `full_text` compartido (unico referente),
    pero `message_attachments.inserted_text` sobrevive intacta (tabla append-only)."""
    config = _config(tmp_path, retention_days=90)
    now = get_utc_now()
    expired_created_at = now - datetime.timedelta(days=91)

    session_id, message_id = _make_session_and_message()
    storage_uuid = _write_binary(config, b"contenido del binario original")
    extraction_id = _make_extraction("texto extraido completo", sha256="a" * 64)
    attachment_id = _make_attachment(
        session_id=session_id,
        storage_path=storage_uuid,
        extraction_id=extraction_id,
        created_at=expired_created_at,
    )
    _make_message_attachment(message_id, attachment_id)

    binary_path = config.storage_dir / str(storage_uuid)
    assert binary_path.exists()

    with get_db_session() as db:
        result = purge_expired_attachments(db, config, now=now)
        db.commit()

    assert result.purged_attachment_ids == [attachment_id]
    assert result.deleted_extraction_ids == [extraction_id]
    assert not binary_path.exists()

    with get_db_session() as db:
        attachment = db.get(Attachment, attachment_id)
        assert attachment is not None
        assert attachment.storage_path is None
        assert attachment.extraction_id is None

        assert db.get(Extraction, extraction_id) is None

        inserted = db.get(MessageAttachment, (message_id, attachment_id))
        assert inserted is not None
        assert (
            inserted.inserted_text == "<adjunto id=x1y2>contenido insertado del adjunto</adjunto>"
        )
        assert inserted.token_count == 42


def test_purge_leaves_non_expired_attachment_untouched(tmp_path: Path) -> None:
    """Un adjunto reciente (dentro de `retention_days`) no pierde binario ni extraccion."""
    config = _config(tmp_path, retention_days=90)
    now = get_utc_now()
    recent_created_at = now - datetime.timedelta(days=1)

    session_id, _message_id = _make_session_and_message()
    storage_uuid = _write_binary(config, b"contenido vigente")
    extraction_id = _make_extraction("texto extraido vigente", sha256="b" * 64)
    attachment_id = _make_attachment(
        session_id=session_id,
        storage_path=storage_uuid,
        extraction_id=extraction_id,
        created_at=recent_created_at,
    )

    binary_path = config.storage_dir / str(storage_uuid)

    with get_db_session() as db:
        result = purge_expired_attachments(db, config, now=now)
        db.commit()

    assert result.purged_attachment_ids == []
    assert result.deleted_extraction_ids == []
    assert binary_path.exists()

    with get_db_session() as db:
        attachment = db.get(Attachment, attachment_id)
        assert attachment is not None
        assert attachment.storage_path == storage_uuid
        assert attachment.extraction_id == extraction_id
        assert db.get(Extraction, extraction_id) is not None


def test_purge_dedup_keeps_full_text_while_one_reference_is_still_active(
    tmp_path: Path,
) -> None:
    """Dos adjuntos comparten la misma `Extraction` (dedup por sha256): mientras uno de
    los dos siga vigente, el `full_text` se conserva; recien se borra cuando el segundo
    tambien vence."""
    config = _config(tmp_path, retention_days=90)
    now = get_utc_now()
    expired_at = now - datetime.timedelta(days=91)
    fresh_at = now - datetime.timedelta(days=1)

    session_id, _message_id = _make_session_and_message()
    extraction_id = _make_extraction("texto compartido por dedup", sha256="c" * 64)

    old_storage = _write_binary(config, b"binario del adjunto vencido")
    new_storage = _write_binary(config, b"binario del adjunto vigente")

    old_attachment_id = _make_attachment(
        session_id=session_id,
        storage_path=old_storage,
        extraction_id=extraction_id,
        created_at=expired_at,
        name="vencido.txt",
    )
    new_attachment_id = _make_attachment(
        session_id=session_id,
        storage_path=new_storage,
        extraction_id=extraction_id,
        created_at=fresh_at,
        name="vigente.txt",
    )

    old_path = config.storage_dir / str(old_storage)
    new_path = config.storage_dir / str(new_storage)

    # --- Primera corrida: solo el adjunto vencido pierde su binario; la extraccion
    # compartida sobrevive porque el adjunto vigente todavia la referencia. ---
    with get_db_session() as db:
        result = purge_expired_attachments(db, config, now=now)
        db.commit()

    assert result.purged_attachment_ids == [old_attachment_id]
    assert result.deleted_extraction_ids == []
    assert not old_path.exists()
    assert new_path.exists()

    with get_db_session() as db:
        old_attachment = db.get(Attachment, old_attachment_id)
        assert old_attachment is not None
        assert old_attachment.storage_path is None
        # La extraccion sigue vigente: el adjunto vencido SIGUE apuntandole (no se
        # purgo el full_text todavia, dedup ANEXO §2 P2/§5).
        assert old_attachment.extraction_id == extraction_id

        new_attachment = db.get(Attachment, new_attachment_id)
        assert new_attachment is not None
        assert new_attachment.storage_path == new_storage
        assert new_attachment.extraction_id == extraction_id

        assert db.get(Extraction, extraction_id) is not None

    # --- Segunda corrida, mas adelante: el adjunto que antes era vigente tambien vence.
    # Recien ahi se borra la extraccion compartida. ---
    later = now + datetime.timedelta(days=95)
    with get_db_session() as db:
        result2 = purge_expired_attachments(db, config, now=later)
        db.commit()

    assert result2.purged_attachment_ids == [new_attachment_id]
    assert result2.deleted_extraction_ids == [extraction_id]
    assert not new_path.exists()

    with get_db_session() as db:
        assert db.get(Extraction, extraction_id) is None
        old_attachment_after = db.get(Attachment, old_attachment_id)
        new_attachment_after = db.get(Attachment, new_attachment_id)
        assert old_attachment_after is not None
        assert new_attachment_after is not None
        assert old_attachment_after.extraction_id is None
        assert new_attachment_after.extraction_id is None


def test_purge_is_idempotent_and_binary_already_missing_is_not_an_error(
    tmp_path: Path,
) -> None:
    """Si el archivo ya no esta en disco (borrado externo), la purga no falla: solo
    limpia la fila (idempotente ante una segunda corrida)."""
    config = _config(tmp_path, retention_days=90)
    now = get_utc_now()
    expired_at = now - datetime.timedelta(days=200)

    session_id, _message_id = _make_session_and_message()
    storage_uuid = uuid.uuid4()  # nunca se escribe a disco: simula un binario ya ausente
    attachment_id = _make_attachment(
        session_id=session_id,
        storage_path=storage_uuid,
        extraction_id=None,
        created_at=expired_at,
    )

    with get_db_session() as db:
        result = purge_expired_attachments(db, config, now=now)
        db.commit()
    assert result.purged_attachment_ids == [attachment_id]

    # Segunda corrida: ya no queda nada que purgar (storage_path ya es NULL).
    with get_db_session() as db:
        result2 = purge_expired_attachments(db, config, now=now)
        db.commit()
    assert result2.purged_attachment_ids == []
