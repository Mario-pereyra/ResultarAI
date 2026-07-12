"""Orquestacion de la extraccion de un adjunto y su transicion de estados (d14, tarea 2.5).

Une el paso [4] del pipeline (ANEXO §8) con el schema de `b04`: toma un adjunto ya
persistido (`uploaded`), lo pasa a `extracting`, corre la extraccion **aislada** (worker
con timeout + memoria acotada, `worker.py`) precedida de la proteccion **zip-bomb** para
OOXML (`zip_guard.py`), y lo deja en `ready` (exito) o `error` (timeout/crash/OOM/bomba).

Transicion de estados (valores EXACTOS de la `CheckConstraint` de `attachments` en `b04`,
`resultarai/adapters/persistence_postgres/models.py`):

    uploaded --> extracting --> ready     (exito, sin secretos N3)
    uploaded --> extracting --> blocked   (exito, pero hallazgo N3: no enviable, tarea 5.1)
    uploaded --> extracting --> error     (ExtractionTimeout / ExtractionFailed / ZipBomb)

La **causa especifica** del `error` se guarda en `scan_result` del adjunto
(`{"extraction_error": {"error_code", "params"}}`) para telemetria de Admin y para que el
frontend (tarea 8.2) muestre un chip `error` con causa, nunca un fallo silencioso. La
excepcion de extraccion NUNCA se propaga como 500: se traduce a estado `error` y la
plataforma sigue operativa.

Tras una extraccion exitosa (tareas 4.1/4.3, pasos [5] y [6]-parcial del ANEXO §8) el
pipeline ademas:

- **Sanitiza** el `full_text` (`sanitize.py`): comentarios HTML/XML, caracteres
  invisibles (zero-width/control) y normalizacion NFC. El `ExtractionResult` del
  `ExtractionOutcome` lleva el texto YA sanitizado — cuando la tarea 7.1 persista
  `Extraction.full_text` y las 5.x/6.x escaneen N2/N3 y corten el `inserted_text`,
  operan sobre texto limpio. El marcador `[oculta]` de los extractores se conserva (se
  marca, no se silencia). El conteo de artefactos removidos queda en
  `scan_result["sanitization"]` (telemetria, nunca bloquea).
- **Escanea instruccion embebida** (`heuristics.py`): los flags (patrones de instruccion
  dirigida a la IA + marcador de escalacion) se persisten en
  `scan_result["injection_flags"]` SIN bloquear — el adjunto queda `ready` igual (la
  advertencia visible es del frontend, tarea 8.2; la traza los recoge de `scan_result`).
  Invariante: el marcador de escalacion DENTRO de un adjunto es dato — jamas dispara una
  escalacion de modelo (la escalacion solo existe en la SALIDA del modelo, camino d13).
- **Escanea niveles de datos N2/N3** (`data_scan.py`, tareas 5.1-5.2) sobre el texto ya
  sanitizado. Un hallazgo **N3** (secreto/credencial) deja el adjunto en `blocked` (no
  enviable) con tipo + linea + fragmento redactado en `scan_result["n3_findings"]`. Un
  hallazgo **N2** (PII) deja el adjunto `ready` pero registra `scan_result["pii_findings"]`
  y `requires_test_data_confirmation=True`: el envio queda bloqueado hasta la confirmacion
  auditada (`confirmation.py`) o el retiro del adjunto. **N3 gana sobre N2**: si hay ambos,
  el estado es `blocked` y no se pide confirmacion (no es enviable de todos modos).

Fuera de alcance (otras piezas del change): persistir el `full_text`/`Extraction` con
dedup por sha256 y el disparo en produccion viven en `pipeline.py` (tarea 7.1, que invoca
`extract_attachment` y reutiliza `finalize_extracted_attachment` para el camino dedup, sin
worker); contar tokens y truncar para el `inserted_text` (6.x) y envolver con el spotlight
(6.3; `spotlight.py`) son de la composicion. Aca `ready` significa "extraido, sanitizado,
escaneado y enviable"; `blocked` significa "extraido pero con secreto N3". El
`ExtractionResult` se devuelve en el `ExtractionOutcome` para esas etapas (el texto existe
en ambos casos: `blocked` es una extraccion exitosa pero no enviable).

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
from resultarai.app.attachments.data_scan import (
    PiiFinding,
    SecretFinding,
    scan_for_pii,
    scan_for_secrets,
)
from resultarai.app.attachments.errors import AttachmentExtractionError
from resultarai.app.attachments.filetypes import extension_of, is_ooxml
from resultarai.app.attachments.heuristics import InjectionFlag, scan_for_injection
from resultarai.app.attachments.sanitize import SanitizationResult, sanitize_extracted_text
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

    `result` viene poblado siempre que la extraccion tuvo exito (estados `ready` **y**
    `blocked`: en ambos el texto existe); `error` viene poblado solo cuando la extraccion
    fallo (estado `error`). `attachment.status` refleja la transicion aplicada.
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
    """Lleva `attachment` de `uploaded` a `ready`/`blocked`/`error` con la extraccion aislada.

    En el camino de exito, sanitiza el `full_text` (tarea 4.1), corre la heuristica de
    instruccion embebida (tarea 4.3) y escanea niveles de datos N2/N3 (tareas 5.1-5.2)
    sobre el texto ya limpio. Un hallazgo N3 deja el adjunto `blocked`; N2 lo deja `ready`
    con `requires_test_data_confirmation`; los hallazgos van a `scan_result`. No hace
    `db.commit()` (la transaccion es de quien inyecta `db`, igual que el resto de casos de
    uso). No propaga la excepcion de extraccion: la traduce a estado `error` con la causa en
    `scan_result` y la devuelve en el `ExtractionOutcome`.
    """
    attachment.status = STATUS_EXTRACTING
    db.flush()

    try:
        result = run_extraction(extract_fn, source, config)
    except AttachmentExtractionError as exc:
        mark_extraction_error(db, attachment, exc)
        return ExtractionOutcome(attachment=attachment, result=None, error=exc)

    sanitization = sanitize_extracted_text(result.full_text)
    sanitized_result = result.model_copy(update={"full_text": sanitization.text})
    finalize_extracted_attachment(
        db, attachment, sanitization.text, config, sanitization=sanitization
    )
    _ = now or get_utc_now()  # reservado para timestamps de extraccion (tareas 6.x/7.1)
    return ExtractionOutcome(attachment=attachment, result=sanitized_result, error=None)


def finalize_extracted_attachment(
    db: DbSession,
    attachment: Attachment,
    full_text: str,
    config: AttachmentsConfig,
    *,
    sanitization: SanitizationResult | None = None,
) -> None:
    """Escanea `full_text` (YA sanitizado) y fija el estado final + `scan_result`.

    Es la mitad "analisis y decision" del pipeline (pasos [5]-[6] del ANEXO §8), separada
    de la extraccion aislada para que el camino **dedup** de la tarea 7.1 (`pipeline.py`)
    la reutilice sobre el `full_text` ya persistido en `extractions` sin re-parsear el
    binario: los escaneos (heuristica de inyeccion + N3/N2) SI se re-corren en cada
    adjunto — los patrones configurados por instancia pueden haber cambiado desde la
    extraccion original y el requirement solo prohibe re-PARSEAR (decision documentada de
    la tarea 7.1). `sanitization` viene poblado solo desde `extract_attachment` (donde la
    sanitizacion acaba de correr y sus artefactos removidos son telemetria nueva); en el
    camino dedup el texto persistido ya esta limpio y no hay nada que reportar.

    N3 gana sobre N2: un secreto bloquea el adjunto (no enviable); sin secreto queda
    `ready` (la PII de N2 no bloquea, solo exige confirmacion). No hace `db.commit()`.
    """
    injection_flags = scan_for_injection(full_text)
    secret_findings = scan_for_secrets(full_text, config.extra_secret_patterns)
    pii_findings = scan_for_pii(full_text)

    blocked = bool(secret_findings)
    attachment.status = STATUS_BLOCKED if blocked else STATUS_READY
    scan_result = _record_analysis(
        attachment.scan_result,
        sanitization,
        injection_flags,
        secret_findings,
        pii_findings,
        blocked=blocked,
    )
    if scan_result is not None:
        attachment.scan_result = scan_result
    db.flush()


def mark_extraction_error(
    db: DbSession,
    attachment: Attachment,
    error: AttachmentExtractionError,
) -> None:
    """Deja `attachment` en estado `error` con la causa tipada en `scan_result`.

    Compartido entre `extract_attachment` (timeout/crash/zip-bomb del worker) y el
    runner de produccion (`pipeline.py`, p. ej. binario ausente en disco o fallo
    inesperado del pipeline): el frontend (tarea 8.2) siempre encuentra la causa
    especifica en `scan_result["extraction_error"]`, nunca un fallo silencioso (P7).
    """
    attachment.status = STATUS_ERROR
    attachment.scan_result = _record_extraction_error(attachment.scan_result, error)
    db.flush()


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


def _record_analysis(
    scan_result: dict[str, object] | None,
    sanitization: SanitizationResult | None,
    injection_flags: list[InjectionFlag],
    secret_findings: list[SecretFinding],
    pii_findings: list[PiiFinding],
    *,
    blocked: bool,
) -> dict[str, object] | None:
    """Registra sanitizacion, inyeccion y hallazgos N2/N3 en `scan_result`, preservando lo previo.

    Devuelve `None` si no hay nada que registrar (texto limpio, sin artefactos): asi un
    adjunto sano conserva `scan_result` intacto (tipicamente `NULL`) y la telemetria de
    Admin distingue "limpio" de "escaneado con hallazgos" de un vistazo. La forma completa
    de `scan_result` esta documentada en `data_scan.py`. `sanitization` es `None` en el
    camino dedup (el texto persistido ya esta limpio; no hay artefactos nuevos).
    """
    updates: dict[str, object] = {}
    if sanitization is not None and sanitization.removed_anything:
        updates["sanitization"] = sanitization.artifacts_dict()
    if injection_flags:
        updates["injection_flags"] = [flag.to_dict() for flag in injection_flags]
    if secret_findings:
        updates["n3_findings"] = [finding.to_dict() for finding in secret_findings]
    if pii_findings:
        updates["pii_findings"] = [finding.to_dict() for finding in pii_findings]
        # Solo se exige confirmacion si el adjunto NO esta bloqueado por N3: un adjunto
        # bloqueado no es enviable de todos modos (N3 gana sobre N2, ANEXO §4.4).
        if not blocked:
            updates["requires_test_data_confirmation"] = True
    if not updates:
        return None
    merged: dict[str, object] = dict(scan_result or {})
    merged.update(updates)
    return merged
