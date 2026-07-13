"""Pipeline de produccion de la extraccion: dedup por sha256 + wiring real (d14, tarea 7.1).

Cierra el hueco documentado en `app/use_cases/chat/_attachments.py`: hasta esta tarea,
ningun camino de produccion disparaba la extraccion tras la subida ni poblaba
`Attachment.extraction`. Este modulo une la subida (`upload.py`, estado `uploaded`) con la
orquestacion aislada (`extraction.py`) y la persistencia de `extractions` (schema de
`b04`, sin redefinirlo), siguiendo el paso [3] del ANEXO §8: "sha256; si existe hash ->
saltar a [5]".

**Dedup por sha256 (ANEXO §2 P2, §5):** la extraccion corre UNA sola vez por binario por
instancia. Si ya existe una fila en `extractions` para `(tenant, sha256)` (UniqueConstraint
`uq_extractions_tenant_sha256`), el adjunto nuevo se vincula a ESA extraccion y el parseo
se salta por completo (ni worker ni binario).

**Decision documentada — re-escaneo en vez de copia del `scan_result`:** en el camino
dedup, los escaneos (heuristica de inyeccion + niveles N2/N3) se RE-CORREN sobre el
`full_text` ya almacenado, en vez de copiar el `scan_result` del adjunto previo. Razones:
(a) es barato — opera sobre texto ya extraido y sanitizado, sin re-parsear el binario, que
es lo unico que el requirement "Extraccion una sola vez" prohibe; (b) es mas robusto — los
patrones de escaneo configurables por instancia (`extra_secret_patterns`) pueden haber
cambiado desde la extraccion original, y copiar un `scan_result` viejo perpetuaria un
veredicto desactualizado; (c) el `scan_result` es un juicio POR ADJUNTO (incluye la
confirmacion N2 del dueno, que no es transferible entre adjuntos/duenos distintos del
mismo binario). El estado final (`ready`/`blocked`) sale directo del re-escaneo, sin pasar
por `extracting` (no hay extraccion en curso).

**Decision documentada — la señal de "PDF escaneado" sobrevive al dedup sin tocar el
schema de `b04`:** `PdfStructure.is_scanned` (el booleano que calcula `PdfExtractor` sobre
las paginas ya parseadas) NUNCA se persiste — `extractions` solo tiene `full_text`/
`extractor_version` (columnas de `b04`, sin migraciones para este change). En el camino
dedup no hay `ExtractionResult` disponible (no se re-parsea el binario), asi que
`finalize_extracted_attachment` (`extraction.py::_detect_scanned_pdf`) RE-deriva el
promedio de caracteres por pagina a partir de los marcadores `--- página N ---` que YA
estan en el `full_text` persistido — mismo criterio que el re-escaneo de N2/N3/instruccion
embebida de arriba: solo el PARSEO del binario se salta, el analisis sobre texto se
re-corre siempre. Por eso `process_attachment` calcula `kind` UNA sola vez (antes del
branch dedup/extraccion real, en vez de solo en el branch de extraccion real como antes) y
lo pasa a `finalize_extracted_attachment` en ambos caminos.

**Decision documentada — disparo con `BackgroundTasks` de FastAPI:** la extraccion real se
dispara DESPUES del 201 de la subida, como background task del mismo proceso
(`run_attachment_extraction_by_id`, encolada por el endpoint via el proveedor inyectable
`get_extraction_runner` de `app/api/attachments.py`). El frontend ya hace polling del
estado (`GET /attachments/{id}`, adapter de la tarea 8.1), asi que el flujo natural es
responder rapido con `uploaded` y dejar que el estado avance a `ready`/`blocked`/`error`
por detras; correr sincrono dentro del request bloquearia la respuesta el timeout entero
(30 s) ante un binario hostil. El trabajo pesado (el parseo) corre igualmente AISLADO en
el worker con timeout + memoria acotada (`worker.py`); la background task solo orquesta.
Los tests invocan `process_attachment` directo o inyectan su propio runner.

**Race de insercion (dos subidas simultaneas del mismo binario nuevo):** ambas pueden
pasar el lookup sin encontrar fila y extraer en paralelo; la segunda insercion violaria el
UniqueConstraint. Se inserta bajo SAVEPOINT (`begin_nested`) y, ante `IntegrityError`, se
re-consulta y reutiliza la fila ganadora (la extraccion es determinista: mismo binario,
mismo `full_text`).

El extractor concreto por tipo se resuelve con `resolve_extractor` (mapa
`AttachmentKind -> adapter extraction_*`); el resolver es inyectable en
`process_attachment` para que los tests cuenten invocaciones sin tocar produccion. Los
extractores son clases sin estado y sus metodos `extract` son picklables (requisito del
worker `forkserver`/`spawn`, verificado por test).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from resultarai.adapters.extraction_docx import DocxExtractor
from resultarai.adapters.extraction_pdf import PdfExtractor
from resultarai.adapters.extraction_spreadsheet import SpreadsheetExtractor
from resultarai.adapters.extraction_text import TextExtractor
from resultarai.adapters.persistence_postgres.connection import get_db_session
from resultarai.adapters.persistence_postgres.models import Attachment, Extraction
from resultarai.app.attachments.config import AttachmentsConfig
from resultarai.app.attachments.errors import AttachmentExtractionError, ExtractionFailedError
from resultarai.app.attachments.extraction import (
    STATUS_EXTRACTING,
    STATUS_UPLOADED,
    extract_attachment,
    finalize_extracted_attachment,
    mark_extraction_error,
)
from resultarai.app.attachments.filetypes import attachment_kind_of
from resultarai.app.attachments.worker import Extractor
from resultarai.core.ports.extraction import AttachmentKind, ExtractionInput, ExtractionPort

__all__ = [
    "ExtractorResolver",
    "PipelineResult",
    "find_extraction",
    "process_attachment",
    "resolve_extractor",
    "run_attachment_extraction_by_id",
]

ExtractorResolver = Callable[[AttachmentKind], Extractor]

# AttachmentKind -> constructor del adapter (clases sin estado; una instancia por
# extraccion). TEXT/CODE/LOG comparten el TextExtractor (ANEXO §2.5).
_EXTRACTOR_FACTORIES: dict[AttachmentKind, Callable[[], ExtractionPort]] = {
    AttachmentKind.SPREADSHEET: SpreadsheetExtractor,
    AttachmentKind.PDF: PdfExtractor,
    AttachmentKind.DOCX: DocxExtractor,
    AttachmentKind.TEXT: TextExtractor,
    AttachmentKind.CODE: TextExtractor,
    AttachmentKind.LOG: TextExtractor,
}


def resolve_extractor(kind: AttachmentKind) -> Extractor:
    """Extractor real (`adapters/extraction_*`) para la familia `kind`.

    Devuelve el metodo `extract` de una instancia nueva: es un bound method picklable
    (clase importable + instancia sin estado no picklable-hostil), requisito para cruzar
    al proceso hijo del worker aislado.
    """
    return _EXTRACTOR_FACTORIES[kind]().extract


@dataclass(frozen=True)
class PipelineResult:
    """Resultado de procesar un adjunto subido (dedup o extraccion real).

    `extraction` es la fila de `extractions` vinculada (nueva o reutilizada); `None` solo
    si la extraccion fallo (`attachment.status == 'error'`, causa en `error` y en
    `scan_result`). `reused=True` significa que el binario NO se parseo: se reutilizo el
    `full_text` ya almacenado (dedup por sha256).
    """

    attachment: Attachment
    extraction: Extraction | None
    reused: bool
    error: AttachmentExtractionError | None


def find_extraction(db: DbSession, *, tenant: str, sha256: str) -> Extraction | None:
    """Fila de `extractions` para `(tenant, sha256)`, o `None` si el binario es nuevo."""
    stmt = select(Extraction).where(Extraction.tenant == tenant, Extraction.sha256 == sha256)
    return db.scalars(stmt).first()


def process_attachment(
    db: DbSession,
    attachment: Attachment,
    config: AttachmentsConfig,
    *,
    resolve: ExtractorResolver | None = None,
) -> PipelineResult:
    """Lleva un adjunto `uploaded` a su estado final: dedup por sha256 o extraccion real.

    - **Hash ya visto** (fila en `extractions` para `(tenant, sha256)`): vincula
      `attachment.extraction_id` a esa fila y salta el parseo por completo; el estado
      final (`ready`/`blocked`) sale de RE-escanear el `full_text` almacenado (decision
      re-escaneo vs copia: docstring del modulo).
    - **Binario nuevo**: corre la extraccion aislada (`extract_attachment`: worker con
      timeout/memoria, sanitizacion, escaneos) y persiste el `full_text` sanitizado +
      `extractor_version` en `extractions` (una sola vez por binario, ANEXO §2 P2).

    No hace `db.commit()`: la transaccion es de quien inyecta `db` (mismo criterio que el
    resto de los casos de uso). `resolve` permite inyectar el mapa de extractores en tests.
    """
    resolve_fn = resolve or resolve_extractor
    # Calculado UNA sola vez: lo necesitan tanto el branch dedup (para que
    # `finalize_extracted_attachment` sepa si corresponde re-derivar "PDF escaneado", ver
    # docstring del modulo) como el branch de extraccion real (`ExtractionInput`/`resolve_fn`).
    kind = attachment_kind_of(attachment.detected_type)

    existing = find_extraction(db, tenant=attachment.tenant, sha256=attachment.sha256)
    if existing is not None:
        attachment.extraction_id = existing.id
        finalize_extracted_attachment(db, attachment, existing.full_text, config, kind=kind)
        return PipelineResult(attachment=attachment, extraction=existing, reused=True, error=None)

    if attachment.storage_path is None:
        # Fila inconsistente (sin binario en disco ni extraccion previa): error tipado,
        # nunca un fallo silencioso (P7).
        error = ExtractionFailedError(cause="missing_binary")
        mark_extraction_error(db, attachment, error)
        return PipelineResult(attachment=attachment, extraction=None, reused=False, error=error)

    source = ExtractionInput(
        kind=kind,
        filename=attachment.original_name,
        source_path=str(config.storage_dir / str(attachment.storage_path)),
    )
    outcome = extract_attachment(db, attachment, resolve_fn(kind), source, config)
    if outcome.result is None:
        return PipelineResult(
            attachment=attachment, extraction=None, reused=False, error=outcome.error
        )

    extraction = _persist_extraction(
        db, attachment, outcome.result.full_text, outcome.result.extractor_version
    )
    attachment.extraction_id = extraction.id
    db.flush()
    return PipelineResult(attachment=attachment, extraction=extraction, reused=False, error=None)


def run_attachment_extraction_by_id(attachment_id: uuid.UUID, config: AttachmentsConfig) -> None:
    """Runner de produccion: procesa un adjunto recien subido en una sesion de DB propia.

    Es la funcion que el endpoint de subida encola en `BackgroundTasks` (decision de
    disparo: docstring del modulo). Abre su PROPIA sesion (`get_db_session`), en su propia
    conexion: el endpoint comitea a mano la sesion del request ANTES de encolar (docstring
    de `upload_attachment_endpoint`, `app/api/attachments.py`) precisamente para que esta
    sesion, distinta, siempre encuentre el adjunto ya durable -- el scope default de una
    dependencia `yield` (`scope="request"`) haria que el `commit()` de `get_db` corriera
    DESPUES de las background tasks, no antes. Solo procesa adjuntos aun `uploaded`
    (idempotente ante reintentos/duplicados de encolado).

    Un fallo de EXTRACCION ya queda registrado por `process_attachment` (estado `error` +
    causa). Un fallo inesperado del propio pipeline (p. ej. DB caida a mitad) se contiene
    y se intenta registrar como `error` con causa `pipeline_failure` en una sesion fresca:
    el chip del frontend nunca queda girando en silencio (P7).
    """
    try:
        with get_db_session() as db:
            attachment = db.get(Attachment, attachment_id)
            if attachment is None or attachment.status != STATUS_UPLOADED:
                return
            process_attachment(db, attachment, config)
    except Exception:
        _mark_pipeline_failure(attachment_id)


def _persist_extraction(
    db: DbSession, attachment: Attachment, full_text: str, extractor_version: str
) -> Extraction:
    """Inserta la fila de `extractions` bajo SAVEPOINT; ante carrera, reutiliza la ganadora."""
    try:
        with db.begin_nested():
            extraction = Extraction(
                tenant=attachment.tenant,
                sha256=attachment.sha256,
                full_text=full_text,
                extractor_version=extractor_version,
            )
            db.add(extraction)
            db.flush()
    except IntegrityError:
        winner = find_extraction(db, tenant=attachment.tenant, sha256=attachment.sha256)
        if winner is None:  # pragma: no cover - defensivo: el UniqueConstraint la garantiza
            raise
        return winner
    return extraction


def _mark_pipeline_failure(attachment_id: uuid.UUID) -> None:
    """Best-effort: registra un fallo inesperado del pipeline como estado `error`."""
    try:
        with get_db_session() as db:
            attachment = db.get(Attachment, attachment_id)
            if attachment is None or attachment.status not in (
                STATUS_UPLOADED,
                STATUS_EXTRACTING,
            ):
                return
            mark_extraction_error(db, attachment, ExtractionFailedError(cause="pipeline_failure"))
    except Exception:
        return
