"""Descarga auditada del binario de un adjunto: solo dueno o Admin (d14, tarea 7.2).

ANEXO §5: "descarga del binario SOLO al dueno y a Admin, siempre AUDITADA y sin URLs
publicas". Este modulo resuelve la ruta en disco de un adjunto ya autorizado y registra
el evento en el audit log append-only; NUNCA genera una URL firmada/publica -- el UNICO
camino de descarga es este endpoint autenticado (`GET /attachments/{id}/download`,
`app/api/attachments.py`), servido con `FileResponse` sobre la ruta que este modulo
devuelve.

**Autorizacion ya verificada por el router** (mismo criterio que `confirmation.py`): aca
se asume que quien llama ya confirmo que `user` es el dueno o tiene rol Admin. Este modulo
solo se ocupa de (a) detectar si la retencion (`retention.py`) ya purgo el binario y (b)
dejar constancia de la descarga.

**Decision del audit log (misma que `confirmation.py`, no repetida alli):** se usa
`identity_audit_events` via `log_identity_audit_event`, NO la tabla `audit_logs` de `b04`
(esa es Policy-Gate-shaped: agent/skill/tool/effect obligatorios, d11 Decision 8). Una
descarga de adjunto es un acceso de USUARIO a un binario propio (o, para Admin, ajeno por
gobernanza), analogo a la confirmacion de datos de prueba -- no una decision del Policy
Gate ni una llamada a tool.

**Momento del registro:** el evento se escribe ANTES de que el router sirva el binario,
justo despues de confirmar que sigue existiendo (no purgado). Cubre el INTENTO ya
autorizado de descarga; un fallo posterior del sistema de archivos (p. ej. borrado externo
entre el chequeo y el `FileResponse`) no es responsabilidad de este modulo y ya quedaria
igual de auditado -- la autorizacion y la decision de servir el binario fueron correctas
en el momento en que se tomaron.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session as DbSession

from resultarai.adapters.persistence_postgres.models import Attachment, User
from resultarai.app.attachments.config import AttachmentsConfig
from resultarai.app.attachments.errors import AttachmentBinaryPurgedError
from resultarai.app.identity import log_identity_audit_event

__all__ = ["AUDIT_EVENT_TYPE", "AttachmentDownload", "download_attachment"]

# Tipo de evento del audit log para la descarga del binario (tarea 7.2).
AUDIT_EVENT_TYPE = "attachment_downloaded"


@dataclass(frozen=True)
class AttachmentDownload:
    """Binario listo para servir: ruta en disco, nombre original y tipo declarado."""

    path: Path
    filename: str
    media_type: str


def download_attachment(
    db: DbSession,
    attachment: Attachment,
    user: User,
    config: AttachmentsConfig,
    *,
    now: datetime.datetime | None = None,
) -> AttachmentDownload:
    """Resuelve la ruta del binario de `attachment` y audita la descarga.

    Levanta `AttachmentBinaryPurgedError` si `storage_path` es `None` (la retencion ya lo
    purgo, `retention.py`) -- SIN auditar: no hubo descarga real, nada que registrar. Si el
    binario sigue disponible, registra el evento en `identity_audit_events` (quien, que
    adjunto, cuando) y devuelve la ruta en disco lista para `FileResponse`. No hace
    `db.commit()` (la transaccion es de quien inyecta `db`, igual que el resto de casos de
    uso de adjuntos).
    """
    if attachment.storage_path is None:
        raise AttachmentBinaryPurgedError(attachment_id=str(attachment.id))

    log_identity_audit_event(
        db,
        event_type=AUDIT_EVENT_TYPE,
        actor_user_id=user.id,
        target_ref=str(attachment.id),
        details={
            "tenant": attachment.tenant,
            "session_id": attachment.session_id,
            "owner_user_id": attachment.uploaded_by,
        },
        now=now,
    )

    return AttachmentDownload(
        path=config.storage_dir / str(attachment.storage_path),
        filename=attachment.original_name,
        media_type=attachment.declared_mime,
    )
