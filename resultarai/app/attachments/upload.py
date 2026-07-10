"""Caso de uso: subir un adjunto, validarlo y persistirlo (d14, tareas 2.1-2.3).

Orquesta el pipeline de subida del ANEXO §8 (pasos [1]-[3]) sobre el schema de `b04`
(`attachments`), sin redefinirlo:

- [1] SUBIDA: se recibe multipart y se aplica el limite de tamano POR TIPO (matriz §9,
  config) y el maximo de **5 adjuntos por mensaje** (config).
- [2] VALIDACION: allowlist tras decodificar el nombre + magic bytes + PDF sin
  contrasena (ver ``validation.py``). El binario rechazado NUNCA se escribe a disco ni
  crea fila: no queda disponible para extraccion (tarea 2.3).
- [3] ALMACENAR: sha256 calculado al subir; el binario se guarda en disco como UUID sin
  extension, fuera del webroot; `original_name` viaja solo como metadato.

**Punto de chequeo del maximo de 5 (decision documentada):** en `b04`,
`message_attachments` asocia adjunto <-> mensaje recien al ENVIAR (tarea 6.3); al subir
todavia no hay mensaje. Por eso el borrador del composer se modela como los adjuntos de
la sesion aun sin mensaje: `attachments` con `session_id` fijado y `message_id IS NULL`.
El limite se chequea al SUBIR contando esos adjuntos pendientes del mismo usuario en la
misma sesion; el sexto se rechaza antes de escribir nada.

El estado inicial "subiendo" del ANEXO es el estado en vuelo del cliente; al persistir,
la fila queda en `uploaded` (el estado de `b04` para "subido, pendiente de extraccion").
La transicion a `extracting`/`ready` es de las tareas 3.x (extractores), fuera de aqui.
"""

from __future__ import annotations

import datetime
import hashlib
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from resultarai.adapters.persistence_postgres.models import Attachment, User, get_utc_now
from resultarai.adapters.persistence_postgres.models import Session as SessionModel
from resultarai.app.attachments.config import AttachmentsConfig
from resultarai.app.attachments.errors import TooManyAttachmentsError
from resultarai.app.attachments.validation import check_size, resolve_type, verify_content

# Estado de `b04` para "subido, pendiente de extraccion" (CheckConstraint de attachments).
_STATUS_UPLOADED = "uploaded"

_DEFAULT_MIME = "application/octet-stream"


@dataclass
class UploadSource:
    """Fuente de un adjunto entrante, desacoplada del transporte (UploadFile de FastAPI).

    `read` es perezoso a proposito: permite rechazar por tamano declarado ANTES de
    materializar el binario completo en memoria.
    """

    filename: str | None
    declared_mime: str
    declared_size: int | None
    read: Callable[[], bytes]


def count_pending_attachments(db: DbSession, session_id: str, uploaded_by: str) -> int:
    """Cuenta los adjuntos del borrador: misma sesion, mismo usuario, aun sin mensaje."""
    stmt = (
        select(func.count())
        .select_from(Attachment)
        .where(
            Attachment.session_id == session_id,
            Attachment.message_id.is_(None),
            Attachment.uploaded_by == uploaded_by,
        )
    )
    return db.scalar(stmt) or 0


def create_attachment(
    db: DbSession,
    config: AttachmentsConfig,
    user: User,
    session: SessionModel,
    source: UploadSource,
    *,
    now: datetime.datetime | None = None,
) -> Attachment:
    """Valida y persiste un adjunto en estado `uploaded`; devuelve la fila creada.

    Levanta un `AttachmentRejectedError` tipado (sin escribir disco ni fila) si supera
    algun limite o falla la validacion de seguridad. No hace `db.commit()`: la
    transaccion es de quien inyecta `db` (igual que el resto de casos de uso de chat).
    """
    uploaded_by = str(user.id)

    # [1] Maximo de adjuntos por mensaje (borrador): chequeo antes de leer el binario.
    if count_pending_attachments(db, session.id, uploaded_by) >= config.max_attachments_per_message:
        raise TooManyAttachmentsError(limit=config.max_attachments_per_message)

    # [2] Tipo por nombre (blocklist educativa + allowlist).
    resolved = resolve_type(config, source.filename)

    # [1] Tamano por tipo: primero por el tamano declarado (evita materializar un binario
    # gigante), luego por el tamano real ya leido (autoritativo).
    if source.declared_size is not None:
        check_size(config, resolved.category, source.declared_size)
    content = source.read()
    check_size(config, resolved.category, len(content))

    # [2] Coherencia de firma binaria + PDF sin contrasena.
    verify_content(resolved.extension, resolved.category, content)

    # [3] sha256 al subir (dedup completo = tarea 7.1; aca solo se persiste el hash).
    sha256 = hashlib.sha256(content).hexdigest()

    # [3] Binario a disco como UUID sin extension, fuera del webroot.
    storage_uuid = uuid.uuid4()
    _write_binary(config.storage_dir, storage_uuid, content)

    attachment = Attachment(
        session_id=session.id,
        message_id=None,
        uploaded_by=uploaded_by,
        original_name=resolved.original_name,
        declared_mime=source.declared_mime or _DEFAULT_MIME,
        detected_type=resolved.category.value,
        size_bytes=len(content),
        sha256=sha256,
        storage_path=storage_uuid,
        scan_result=None,
        status=_STATUS_UPLOADED,
        tenant=config.tenant,
        extraction_id=None,
        created_at=now or get_utc_now(),
    )
    db.add(attachment)
    db.flush()
    return attachment


def _write_binary(storage_dir: Path, storage_uuid: uuid.UUID, content: bytes) -> None:
    """Escribe el binario en `storage_dir/<uuid>` (sin extension), creando el dir."""
    storage_dir.mkdir(parents=True, exist_ok=True)
    (storage_dir / str(storage_uuid)).write_bytes(content)
