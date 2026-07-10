"""Orquestacion de la extraccion de un adjunto y su transicion de estados (d14, tarea 2.5).

Une el paso [4] del pipeline (ANEXO §8) con el schema de `b04`: toma un adjunto ya
persistido (`uploaded`), lo pasa a `extracting`, corre la extraccion **aislada** (worker
con timeout + memoria acotada, `worker.py`) precedida de la proteccion **zip-bomb** para
OOXML (`zip_guard.py`), y lo deja en `ready` (exito) o `error` (timeout/crash/OOM/bomba).

Transicion de estados (valores EXACTOS de la `CheckConstraint` de `attachments` en `b04`,
`resultarai/adapters/persistence_postgres/models.py`):

    uploaded --> extracting --> ready   (exito)
    uploaded --> extracting --> error   (ExtractionTimeout / ExtractionFailed / ZipBomb)

La **causa especifica** del `error` se guarda en `scan_result` del adjunto
(`{"extraction_error": {"error_code", "params"}}`) para telemetria de Admin y para que el
frontend (tarea 8.2) muestre un chip `error` con causa, nunca un fallo silencioso. La
excepcion de extraccion NUNCA se propaga como 500: se traduce a estado `error` y la
plataforma sigue operativa.

Fuera de alcance de esta tarea (tareas posteriores): persistir el `full_text`/`Extraction`
con dedup por sha256 (7.1), sanitizar y escanear N2/N3 (4.x/5.x), contar tokens y truncar
para el `inserted_text` (6.x). Aca `ready` significa "extraido con exito"; el
`ExtractionResult` se devuelve en el `ExtractionOutcome` para esas etapas.

El extractor concreto se **inyecta** (`Callable`/`ExtractionPort.extract`): este modulo no
importa ningun adapter de `resultarai/adapters/extraction_*`.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session as DbSession

from resultarai.adapters.persistence_postgres.models import Attachment, get_utc_now
from resultarai.app.attachments.config import AttachmentsConfig
from resultarai.app.attachments.errors import AttachmentExtractionError
from resultarai.app.attachments.filetypes import extension_of, is_ooxml
from resultarai.app.attachments.worker import Extractor, run_in_isolated_worker
from resultarai.app.attachments.zip_guard import inspect_ooxml_for_zip_bomb
from resultarai.core.ports.extraction import ExtractionInput, ExtractionResult

# Estados de `b04` (CheckConstraint de attachments); usados tal cual, sin redefinir schema.
STATUS_UPLOADED = "uploaded"
STATUS_EXTRACTING = "extracting"
STATUS_READY = "ready"
STATUS_BLOCKED = "blocked"
STATUS_ERROR = "error"


@dataclass
class ExtractionOutcome:
    """Resultado de orquestar la extraccion de un adjunto.

    Exactamente uno de `result`/`error` viene poblado: `result` en `ready`, `error` en
    `error`. `attachment.status` refleja la transicion aplicada.
    """

    attachment: Attachment
    result: ExtractionResult | None
    error: AttachmentExtractionError | None


def run_extraction(
    extract_fn: Extractor,
    source: ExtractionInput,
    config: AttachmentsConfig,
) -> ExtractionResult:
    """Corre la extraccion aislada de `source`, con proteccion zip-bomb previa para OOXML.

    Levanta `ZipBombSuspectedError` (OOXML sobre umbral), `ExtractionTimeoutError` o
    `ExtractionFailedError` (todas `AttachmentExtractionError`). El chequeo zip-bomb corre
    ANTES de gastar un worker: una bomba se rechaza leyendo solo el indice del ZIP, sin
    descomprimir ni agotar memoria.
    """
    if is_ooxml(extension_of(source.filename)):
        ooxml_bytes = _ooxml_bytes(source)
        if ooxml_bytes is not None:
            inspect_ooxml_for_zip_bomb(
                ooxml_bytes,
                max_uncompressed_bytes=config.zip_bomb_max_uncompressed_bytes,
                max_ratio=config.zip_bomb_max_ratio,
            )

    return run_in_isolated_worker(
        extract_fn,
        source,
        timeout_seconds=config.extraction_timeout_seconds,
        memory_limit_bytes=config.extraction_memory_limit_bytes,
    )


def extract_attachment(
    db: DbSession,
    attachment: Attachment,
    extract_fn: Extractor,
    source: ExtractionInput,
    config: AttachmentsConfig,
    *,
    now: datetime.datetime | None = None,
) -> ExtractionOutcome:
    """Lleva `attachment` de `uploaded` a `ready`/`error` corriendo la extraccion aislada.

    No hace `db.commit()` (la transaccion es de quien inyecta `db`, igual que el resto de
    casos de uso). No propaga la excepcion de extraccion: la traduce a estado `error` con
    la causa en `scan_result` y la devuelve en el `ExtractionOutcome`.
    """
    attachment.status = STATUS_EXTRACTING
    db.flush()

    try:
        result = run_extraction(extract_fn, source, config)
    except AttachmentExtractionError as exc:
        attachment.status = STATUS_ERROR
        attachment.scan_result = _record_extraction_error(attachment.scan_result, exc)
        db.flush()
        return ExtractionOutcome(attachment=attachment, result=None, error=exc)

    attachment.status = STATUS_READY
    db.flush()
    _ = now or get_utc_now()  # reservado para timestamps de extraccion (tareas 6.x/7.1)
    return ExtractionOutcome(attachment=attachment, result=result, error=None)


def _ooxml_bytes(source: ExtractionInput) -> bytes | None:
    """Bytes crudos del OOXML para inspeccionar el indice del ZIP (content o source_path).

    Leer el binario comprimido es seguro en memoria (lo comprimido es chico; una bomba
    miente en el DESCOMPRIMIDO, que `zip_guard` nunca materializa). Si no se puede leer,
    devuelve `None` y la deteccion queda al respaldo del worker aislado.
    """
    if source.content is not None:
        return source.content
    if source.source_path is not None:
        try:
            return Path(source.source_path).read_bytes()
        except OSError:
            return None
    return None


def _record_extraction_error(
    scan_result: dict[str, object] | None,
    error: AttachmentExtractionError,
) -> dict[str, object]:
    """Fija la causa del `error` en `scan_result` preservando lo que ya hubiera."""
    merged: dict[str, object] = dict(scan_result or {})
    merged["extraction_error"] = {"error_code": error.error_code, "params": error.params}
    return merged
