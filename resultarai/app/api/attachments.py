"""FastAPI router para adjuntos: subida (`POST /api/attachments`, d14 tareas 2.1-2.3),
consulta/vista previa (`GET /api/attachments/{id}`, `GET /api/attachments/{id}/preview`,
tarea 6.3 -- soporte de 8.1/8.3) y descarga auditada del binario
(`GET /api/attachments/{id}/download`, tarea 7.2, ANEXO §5).

Ruta bajo `/api` para ser coherente con el resto de la API (`chat.py`). La subida usa
`multipart/form-data`: el binario en `file` y el borrador destino en `session_id`.

**Autenticacion:** misma sesion que chat (`get_current_user`) + CSRF de doble envio
(enforced globalmente por `csrf_guard` en `create_app`).

**Contrato de errores (nota de §10):** los rechazos devuelven **HTTP 422** con
`detail = {"error_code": str, "params": {...}}`. El `error_code` es estable
(`too_large`, `type_not_allowed`, `type_forged`, `macros_not_allowed`,
`compressed_not_allowed`, `executable_rejected`, `legacy_doc`, `image_not_supported`,
`pdf_password`, `too_many_attachments`) y `params` trae lo accionable (limite concreto, extension
detectada, etc.). El texto exacto de [ANEXO §10](../../../../design/ANEXO-ATTACHMENTS.md)
en voseo lo reconstruye el frontend via i18n a partir de `error_code` + `params`
(tareas 8.2/8.4) -- el backend NO renderiza ese texto. Ver ``attachments/errors.py``
para el mapa error_code -> texto §10.

El Content-Type que declara el navegador se guarda solo como metadato (`declared_mime`)
y NUNCA se usa para decidir el tipo (ANEXO §4.1): la decision es por extension +
magic bytes.

**`get_registries` importado de `chat.py` (no redefinido aca):** mismo patron que
`get_turn_stream_registry` en `app/api/chat_stream.py` -- `create_app()` solo
sobreescribe UNA vez el `get_registries` de `chat.py`
(`app/api/__init__.py::get_registries_override`); importar el MISMO objeto de funcion
aca hace que ese unico override tambien aplique a este router, sin duplicar wiring de
produccion ni de tests. `get_attachments_config` vive en `app/attachments/dependency.py`
(no en `chat.py` ni aca) precisamente para que ninguno de los dos routers de API tenga
que importar al otro.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from resultarai.adapters.persistence_postgres.models import Attachment, User
from resultarai.adapters.persistence_postgres.models import Session as SessionModel
from resultarai.app.api.chat import get_registries
from resultarai.app.attachments import (
    AttachmentBinaryPurgedError,
    AttachmentRejectedError,
    AttachmentsConfig,
    NoPendingConfirmationError,
    UploadSource,
    confirm_test_data,
    create_attachment,
    describe_token_usage,
    download_attachment,
    find_first_insertion,
    is_sendable,
)

# Re-exportado explícitamente (alias redundante `as`, mismo motivo que
# `get_turn_stream_registry` en `app/api/chat_stream.py`): `tests/app/attachments/
# test_upload.py` importa `get_attachments_config` DESDE este módulo para
# sobreescribirlo, y mypy --strict exige `import X as X` para contar un nombre
# importado como parte de la API pública re-exportada de un módulo sin `__all__`.
from resultarai.app.attachments.dependency import get_attachments_config as get_attachments_config
from resultarai.app.attachments.pipeline import run_attachment_extraction_by_id
from resultarai.app.identity import get_current_user, get_db
from resultarai.core.registries import Registries

router = APIRouter(prefix="/api", tags=["attachments"])

# Firma del runner que el endpoint de subida encola en `BackgroundTasks` (decision de
# disparo documentada en `pipeline.py`): recibe el id del adjunto ya persistido y no
# devuelve nada (el resultado queda en `attachments`/`extractions`, nunca en la respuesta
# HTTP, que ya viajo). Inyectable para que los tests sustituyan la extraccion real (p. ej.
# por una version sincrona o un fake que cuenta invocaciones) sin tocar el endpoint.
ExtractionRunner = Callable[[uuid.UUID], None]


def get_extraction_runner(
    config: Annotated[AttachmentsConfig, Depends(get_attachments_config)],
) -> ExtractionRunner:
    """Proveedor real del runner de extraccion: encola `run_attachment_extraction_by_id`.

    Cierra la extraccion sobre la MISMA `config` resuelta para la subida (misma
    `storage_dir`/limites de instancia), via `Depends` normal -- no hace falta un
    override de produccion aparte: cuando un test sobreescribe `get_attachments_config`
    (p. ej. `storage_dir` temporal), este proveedor lo hereda automaticamente. Los tests
    que quieren sustituir la extraccion en si (no solo su config) sobreescriben
    `get_extraction_runner` directamente.
    """

    def _run(attachment_id: uuid.UUID) -> None:
        run_attachment_extraction_by_id(attachment_id, config)

    return _run


class AttachmentResponse(BaseModel):
    """Adjunto recien subido, en estado inicial `uploaded` (pendiente de extraccion).

    No expone `storage_path` (el UUID del binario en disco): la descarga es el endpoint
    autenticado y auditado `GET /attachments/{id}/download` (tarea 7.2, mas abajo en este
    modulo), nunca una URL directa (ANEXO §5).
    """

    id: str
    session_id: str | None
    status: str
    original_name: str
    detected_type: str | None
    size_bytes: int
    sha256: str
    created_at: str


def _read_upload(file: UploadFile) -> bytes:
    """Lee todo el binario subido desde el inicio (SpooledTemporaryFile sincrono)."""
    file.file.seek(0)
    return file.file.read()


@router.post("/attachments", status_code=201)
def upload_attachment_endpoint(
    file: Annotated[UploadFile, File(...)],
    session_id: Annotated[str, Form(...)],
    background_tasks: BackgroundTasks,
    db: Annotated[DbSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    config: Annotated[AttachmentsConfig, Depends(get_attachments_config)],
    extraction_runner: Annotated[ExtractionRunner, Depends(get_extraction_runner)],
) -> AttachmentResponse:
    """Sube un adjunto al borrador de `session_id` y lo deja en estado `uploaded`.

    El dueno se deriva **siempre** de la cookie de sesion (`get_current_user`), nunca
    del payload. Una sesion ajena o inexistente responde 404 sin filtrar el motivo
    (mismo criterio que los endpoints de chat). Los rechazos de validacion (tamano,
    tipo, macros, ejecutable, PDF con contrasena, sexto adjunto) responden 422 con el
    contrato tipado descrito en el docstring del modulo -- sin escribir el binario a
    disco: el archivo rechazado no queda disponible para extraccion (tarea 2.3).

    Tras el 201, encola la extraccion real (`pipeline.py`, tarea 7.1: dedup por sha256 o
    parseo aislado) en `BackgroundTasks`, DESPUES de que este handler retorna -- nunca
    bloquea la respuesta con el parseo.

    **Por que se comitea aca, a mano, contra la convencion del resto del codigo (`db` no
    hace `commit()`, es responsabilidad de `get_db`):** `run_attachment_extraction_by_id`
    corre en su PROPIA sesion/conexion (`get_db_session` de `pipeline.py`), distinta de
    esta. Con el scope **default** de una dependencia `yield` (`scope="request"`, FastAPI
    >= 0.121: ver "Early exit and scope" de la docs de FastAPI), el `commit()` de `get_db`
    corre DESPUES de enviar la respuesta -- y las `BackgroundTasks` tambien corren como
    parte de enviar la respuesta (`Response.background`), ANTES de ese `commit()` final,
    no despues. Sin este commit explicito, la sesion aislada del runner jamas veria el
    adjunto (otra conexion, otra transaccion) y `run_attachment_extraction_by_id` lo
    encontraria `None`.
    """
    session = db.get(SessionModel, session_id)
    if session is None or session.owner_user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Sesión no encontrada.")

    source = UploadSource(
        filename=file.filename,
        declared_mime=file.content_type or "",
        declared_size=getattr(file, "size", None),
        read=lambda: _read_upload(file),
    )

    try:
        attachment = create_attachment(db, config, current_user, session, source)
    except AttachmentRejectedError as exc:
        raise HTTPException(
            status_code=422,
            detail={"error_code": exc.error_code, "params": exc.params},
        ) from exc

    # Commit explicito (ver docstring): deja el adjunto DURABLE y visible para otra
    # conexion antes de encolar la extraccion, que corre en su propia sesion aislada.
    db.commit()

    background_tasks.add_task(extraction_runner, attachment.id)

    return AttachmentResponse(
        id=str(attachment.id),
        session_id=attachment.session_id,
        status=attachment.status,
        original_name=attachment.original_name,
        detected_type=attachment.detected_type,
        size_bytes=attachment.size_bytes,
        sha256=attachment.sha256,
        created_at=attachment.created_at.isoformat(),
    )


class TestDataConfirmationResponse(BaseModel):
    """Estado del adjunto tras confirmar que su PII son datos de prueba (tarea 5.2)."""

    id: str
    status: str
    requires_test_data_confirmation: bool
    sendable: bool


@router.post("/attachments/{attachment_id}/confirm-test-data")
def confirm_test_data_endpoint(
    attachment_id: uuid.UUID,
    db: Annotated[DbSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TestDataConfirmationResponse:
    """Confirma que la PII detectada (N2) en el adjunto son datos de prueba (ANEXO §4.4).

    Solo el **dueno** puede confirmar: un adjunto ajeno o inexistente responde 404 sin
    filtrar existencia (mismo criterio que la subida). La confirmacion queda en el audit
    log append-only (`confirmation.confirm_test_data`) y baja el bloqueo de envio N2. Si el
    adjunto no tiene una confirmacion pendiente (sin PII, ya confirmada, o bloqueado por N3)
    responde 409, sin re-auditar.
    """
    attachment = db.get(Attachment, attachment_id)
    if attachment is None or attachment.uploaded_by != str(current_user.id):
        raise HTTPException(status_code=404, detail="Adjunto no encontrado.")

    try:
        confirm_test_data(db, attachment, current_user)
    except NoPendingConfirmationError as exc:
        raise HTTPException(
            status_code=409,
            detail={"error_code": "no_pending_confirmation", "params": {}},
        ) from exc

    scan_result = attachment.scan_result or {}
    return TestDataConfirmationResponse(
        id=str(attachment.id),
        status=attachment.status,
        requires_test_data_confirmation=bool(
            scan_result.get("requires_test_data_confirmation", False)
        ),
        sendable=is_sendable(attachment),
    )


class AttachmentStatusResponse(BaseModel):
    """Estado + metadatos de un adjunto para el frontend (soporte de 8.1/8.3).

    `scan_summary` es el `scan_result` TAL CUAL (ver `app/attachments/data_scan.py`):
    ya viene sin datos en claro por construccion (los hallazgos N2/N3 solo guardan
    tipo/cantidad/linea y un fragmento REDACTADO, nunca el secreto o la PII original),
    asi que no hace falta un filtrado adicional aca para exponerlo.

    `token_count`/`included_percent`/`truncated` viajan AMBOS -- tokens (unidad
    Tecnico/Admin) y % (unidad Funcional, ANEXO §3.4) -- server-side; el rol lo decide
    el CLIENTE (decision documentada en `app/attachments/insertion.py`). `inserted`
    distingue si son la insercion YA persistida (`message_attachments`) o una
    ESTIMACION sobre `full_text` (adjunto todavia no enviado en ningun mensaje). Todos
    `None` si el adjunto todavia no tiene extraccion disponible (no `ready`/`blocked`).
    """

    id: str
    status: str
    original_name: str
    detected_type: str | None
    size_bytes: int
    created_at: str
    sendable: bool
    requires_test_data_confirmation: bool
    scan_summary: dict[str, Any] | None
    inserted: bool
    token_count: int | None
    included_percent: int | None
    truncated: bool | None


@router.get("/attachments/{attachment_id}")
def get_attachment_endpoint(
    attachment_id: uuid.UUID,
    db: Annotated[DbSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    registries: Annotated[Registries, Depends(get_registries)],
    config: Annotated[AttachmentsConfig, Depends(get_attachments_config)],
) -> AttachmentStatusResponse:
    """Estado + metadatos de un adjunto (soporte de 8.1: chip de estado del composer).

    Solo el **dueno** puede consultarlo: un adjunto ajeno o inexistente responde 404
    sin filtrar existencia (mismo criterio que el resto de los endpoints de adjuntos).
    """
    attachment = db.get(Attachment, attachment_id)
    if attachment is None or attachment.uploaded_by != str(current_user.id):
        raise HTTPException(status_code=404, detail="Adjunto no encontrado.")

    usage = describe_token_usage(db, registries, config, attachment)
    scan_result = attachment.scan_result or {}
    return AttachmentStatusResponse(
        id=str(attachment.id),
        status=attachment.status,
        original_name=attachment.original_name,
        detected_type=attachment.detected_type,
        size_bytes=attachment.size_bytes,
        created_at=attachment.created_at.isoformat(),
        sendable=is_sendable(attachment),
        requires_test_data_confirmation=bool(
            scan_result.get("requires_test_data_confirmation", False)
        ),
        scan_summary=attachment.scan_result,
        inserted=usage.inserted,
        token_count=usage.token_count,
        included_percent=usage.included_percent,
        truncated=usage.truncated,
    )


class AttachmentPreviewResponse(BaseModel):
    """ "Ver lo que verá el agente" (ANEXO §3.4) -- semántica pre/post inserción:

    - **`inserted=True`** (el adjunto ya se envió en algún mensaje de la sesión, ANEXO
      §7 punto 4): `text` es la `inserted_text` EXACTA (con sus marcadores de truncado,
      byte-idéntica a la que viajó al modelo), `token_count`/`truncated` los valores
      REALES persistidos en `message_attachments`, `included_percent` calculado contra
      el `full_text` original (si sigue disponible; ver `describe_token_usage`).
    - **`inserted=False`** (todavía no se envió en ningún mensaje): `text` es el
      `full_text` TAL CUAL -- "lo que se insertaría hasta ahora" (el truncado por
      relevancia todavía no corrió: depende del texto del mensaje que lo acompañe,
      design.md decisión 8) -- con `token_count` del `full_text` completo e
      `included_percent` PROVISIONAL: 100 si cabría entero en el presupuesto por
      archivo, o la fracción estimada que entraría si no.
    """

    id: str
    inserted: bool
    text: str
    token_count: int
    included_percent: int
    truncated: bool


@router.get("/attachments/{attachment_id}/preview")
def preview_attachment_endpoint(
    attachment_id: uuid.UUID,
    db: Annotated[DbSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    registries: Annotated[Registries, Depends(get_registries)],
    config: Annotated[AttachmentsConfig, Depends(get_attachments_config)],
) -> AttachmentPreviewResponse:
    """ "Ver lo que verá el agente" -- ver semántica pre/post en `AttachmentPreviewResponse`.

    Solo el **dueno** puede verla (404 sin filtrar existencia si es ajena/inexistente).
    409 `extraction_not_ready` si el adjunto todavía no tiene extracción disponible
    (no está `ready`/`blocked` todavía, o su `full_text` fue purgado por retención sin
    que exista ya una inserción -- caso extremo, ANEXO §5).
    """
    attachment = db.get(Attachment, attachment_id)
    if attachment is None or attachment.uploaded_by != str(current_user.id):
        raise HTTPException(status_code=404, detail="Adjunto no encontrado.")

    first_insertion = find_first_insertion(db, attachment_id)
    if first_insertion is not None:
        usage = describe_token_usage(db, registries, config, attachment)
        return AttachmentPreviewResponse(
            id=str(attachment.id),
            inserted=True,
            text=first_insertion.inserted_text,
            token_count=first_insertion.token_count,
            included_percent=(
                usage.included_percent if usage.included_percent is not None else 100
            ),
            truncated=first_insertion.truncated,
        )

    if attachment.extraction is None:
        raise HTTPException(
            status_code=409,
            detail={"error_code": "extraction_not_ready", "params": {}},
        )

    usage = describe_token_usage(db, registries, config, attachment)
    if usage.token_count is None or usage.included_percent is None or usage.truncated is None:
        raise HTTPException(  # pragma: no cover - defensivo: extraction != None ya lo garantiza
            status_code=409,
            detail={"error_code": "extraction_not_ready", "params": {}},
        )
    return AttachmentPreviewResponse(
        id=str(attachment.id),
        inserted=False,
        text=attachment.extraction.full_text,
        token_count=usage.token_count,
        included_percent=usage.included_percent,
        truncated=usage.truncated,
    )


@router.get("/attachments/{attachment_id}/download")
def download_attachment_endpoint(
    attachment_id: uuid.UUID,
    db: Annotated[DbSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    config: Annotated[AttachmentsConfig, Depends(get_attachments_config)],
) -> FileResponse:
    """Descarga el binario original de un adjunto (tarea 7.2, ANEXO §5).

    Autorizacion: SOLO el **dueno** o un usuario con rol **Admin**; cualquier otro (o un
    `attachment_id` inexistente) responde 404 sin filtrar existencia -- mismo criterio que
    el resto de los endpoints de adjuntos, extendido para no revelarle a un Admin
    tampoco si el id existe cuando ademas no es Admin (imposible: Admin siempre pasa).
    Nunca una URL firmada/publica: este es el UNICO camino de descarga, autenticado por
    cookie de sesion + CSRF (`csrf_guard`, global). Cada descarga autorizada queda
    registrada en el audit log append-only (`download.py` -> `identity_audit_events`),
    ANTES de servir el binario.

    409 `attachment_binary_purged` si la retencion (`retention.py`, tarea 7.2) ya elimino
    el binario de disco -- error tipado, nunca un 500.
    """
    attachment = db.get(Attachment, attachment_id)
    is_owner = attachment is not None and attachment.uploaded_by == str(current_user.id)
    is_admin = current_user.role == "admin"
    if attachment is None or not (is_owner or is_admin):
        raise HTTPException(status_code=404, detail="Adjunto no encontrado.")

    try:
        download = download_attachment(db, attachment, current_user, config)
    except AttachmentBinaryPurgedError as exc:
        raise HTTPException(
            status_code=409,
            detail={"error_code": "attachment_binary_purged", "params": {}},
        ) from exc

    return FileResponse(
        path=download.path,
        filename=download.filename,
        media_type=download.media_type,
    )
