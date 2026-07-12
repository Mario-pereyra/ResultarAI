"""Purga por retencion del binario y su `full_text` compartido (d14, tarea 7.2, ANEXO §5).

ANEXO §5: "retencion configurable (default 90 dias) del binario/`full_text` conservando
`inserted_text`". `AttachmentsConfig.retention_days` (`config.py`) ya trae el default y su
variable de entorno; este modulo implementa la purga en si: una funcion invocable,
`purge_expired_attachments`, que un job externo (cron/scheduler) dispararia periodicamente.

**El scheduling real NO es parte de esta tarea** (asi lo aclara el enunciado de 7.2): el
repo todavia no tiene un mecanismo de jobs/cron propio (no hay ningun `apscheduler`,
Celery beat, ni comando `manage.py`-like en `pyproject.toml`/`resultarai/`); la funcion
queda lista para conectarse a cualquiera de esos cuando exista (hueco documentado en el
reporte de la tarea).

**Investigacion de triggers append-only en `b04` (migraciones de
`persistence_postgres/migrations/versions/`), tal como pide la tarea:**

- `messages`, `compaction_markers` y `message_attachments` tienen el trigger
  `prevent_update_delete_*` -> `prevent_update_or_delete()` (ver
  `28d73d938a65_create_conversation_persistence.py` y
  `c6a9321d50ac_create_attachment_storage.py`): cualquier UPDATE/DELETE sobre esas tablas
  lanza una excepcion de Postgres. Esto es justamente lo que GARANTIZA que
  `message_attachments.inserted_text` sobreviva la purga sin que este modulo tenga que
  protegerla explicitamente: ni siquiera PODRIA tocarla.
- `attachments` y `extractions` NO tienen ese trigger (mismas migraciones): son mutables.
  La purga se apoya en eso:
  - En `attachments`: UPDATE de `storage_path` a `NULL` (la fila y el resto de columnas
    -- incluido `scan_result`, `sha256`, metadatos -- se conservan intactas; solo el
    puntero al binario en disco desaparece).
  - En `extractions`: `full_text` es `NOT NULL` (`models.py`), asi que no se puede
    "vaciar" una fila sin migrar el schema -- prohibido por esta tarea. La purga real de
    un `full_text` es entonces el DELETE completo de su fila, permitido (sin trigger)
    SOLO cuando TODOS los adjuntos que la referencian (mismo `extraction_id`, por dedup de
    sha256) ya estan vencidos: si sobrevive un adjunto no vencido que comparte el mismo
    binario, el `full_text` se conserva para el (requirement de dedup, ANEXO §2 P2/§5).
    `attachments.extraction_id` tiene `ondelete="SET NULL"` (migracion
    `c6a9321d50ac`), asi que ese DELETE deja automaticamente `extraction_id=NULL` a nivel
    de fila para cualquier adjunto que siguiera apuntando a ella -- consistente con el
    caso ya documentado en `insertion.py`/`app/api/attachments.py`
    ("`full_text` purgado por retencion" con `attachment.extraction is None`).

En consecuencia, esta tarea NO requiere ninguna migracion nueva: ambas tablas ya admiten
exactamente las mutaciones que la purga necesita.
"""

from __future__ import annotations

import contextlib
import datetime
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from resultarai.adapters.persistence_postgres.models import Attachment, Extraction, get_utc_now
from resultarai.app.attachments.config import AttachmentsConfig

__all__ = ["PurgeResult", "purge_expired_attachments"]


@dataclass(frozen=True)
class PurgeResult:
    """Adjuntos y extracciones tocados por una corrida de `purge_expired_attachments`."""

    purged_attachment_ids: list[uuid.UUID] = field(default_factory=list)
    deleted_extraction_ids: list[uuid.UUID] = field(default_factory=list)


def purge_expired_attachments(
    db: DbSession,
    config: AttachmentsConfig,
    *,
    now: datetime.datetime | None = None,
) -> PurgeResult:
    """Purga el binario y, cuando corresponde, el `full_text` de los adjuntos vencidos.

    Un adjunto esta "vencido" cuando `created_at < now - retention_days` (misma
    referencia de tiempo que la subida, config leida de `AttachmentsConfig.retention_days`
    -- ANEXO §5, default 90 dias). Para cada adjunto vencido con binario aun en disco
    (`storage_path IS NOT NULL`):

    1. Borra el archivo de `storage_dir/<storage_path>` (best-effort: si ya no esta, no es
       un error).
    2. Deja `attachment.storage_path = None` -- la fila sigue existiendo, con su
       `scan_result`/metadatos intactos; solo el binario desaparece.

    Despues, para cada `Extraction` referenciada por algun adjunto recien purgado,
    verifica si TODAVIA queda algun adjunto no vencido apuntandole (dedup por sha256,
    ANEXO §2 P2/§5): si NINGUNO sobrevive, borra la fila de `extractions` completa (unica
    forma posible de "vaciar" `full_text`, que es `NOT NULL`; ver el docstring del modulo).
    El DELETE deja `extraction_id=NULL` a nivel de fila para cualquier adjunto que aun
    apuntara a ella (`ondelete=SET NULL`); este modulo ademas lo refleja en los objetos
    `Attachment` ya cargados en esta sesion (el `Session` de SQLAlchemy no los refresca
    solo, `expire_on_commit=False` en `connection.py`).

    `message_attachments.inserted_text` nunca se toca: esa tabla es append-only (trigger
    de Postgres, ver el docstring del modulo) y la conversacion sigue legible aunque el
    binario/`full_text` originales ya no existan.

    No hace `db.commit()`: la transaccion es de quien inyecta `db` (mismo criterio que el
    resto de casos de uso de adjuntos); quien invoque esta funcion desde un job real debe
    comitear despues de una corrida exitosa.
    """
    cutoff = (now or get_utc_now()) - datetime.timedelta(days=config.retention_days)

    expired_attachments = list(
        db.scalars(
            select(Attachment).where(
                Attachment.created_at < cutoff,
                Attachment.storage_path.is_not(None),
            )
        )
    )

    purged_attachment_ids: list[uuid.UUID] = []
    touched_extraction_ids: set[uuid.UUID] = set()

    for attachment in expired_attachments:
        _delete_binary(config.storage_dir, attachment.storage_path)  # type: ignore[arg-type]
        if attachment.extraction_id is not None:
            touched_extraction_ids.add(attachment.extraction_id)
        attachment.storage_path = None
        purged_attachment_ids.append(attachment.id)
    if expired_attachments:
        db.flush()

    deleted_extraction_ids: list[uuid.UUID] = []
    for extraction_id in touched_extraction_ids:
        still_referenced = (
            db.scalar(
                select(func.count())
                .select_from(Attachment)
                .where(
                    Attachment.extraction_id == extraction_id,
                    Attachment.created_at >= cutoff,
                )
            )
            or 0
        )
        if still_referenced:
            continue

        extraction = db.get(Extraction, extraction_id)
        if extraction is None:  # pragma: no cover - defensivo: ya vinculada, deberia existir
            continue
        db.delete(extraction)
        deleted_extraction_ids.append(extraction_id)

        # Refleja en memoria el SET NULL que la FK ya aplico a nivel de fila, para que los
        # objetos `Attachment` cargados en ESTA sesion no queden con un `extraction_id`
        # obsoleto (`expire_on_commit=False`, `connection.py`).
        for attachment in expired_attachments:
            if attachment.extraction_id == extraction_id:
                attachment.extraction_id = None

    if deleted_extraction_ids:
        db.flush()

    return PurgeResult(
        purged_attachment_ids=purged_attachment_ids,
        deleted_extraction_ids=deleted_extraction_ids,
    )


def _delete_binary(storage_dir: Path, storage_uuid: uuid.UUID) -> None:
    """Borra `storage_dir/<storage_uuid>`; ausente-ya no es un error (idempotente)."""
    path = storage_dir / str(storage_uuid)
    with contextlib.suppress(FileNotFoundError):
        path.unlink()
