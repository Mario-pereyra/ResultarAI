"""FastAPI router para la subida de adjuntos: `POST /api/attachments` (d14, tareas 2.1-2.3).

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
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from resultarai.adapters.persistence_postgres.models import Session as SessionModel
from resultarai.adapters.persistence_postgres.models import User
from resultarai.app.attachments import (
    AttachmentRejectedError,
    AttachmentsConfig,
    UploadSource,
    create_attachment,
)
from resultarai.app.identity import get_current_user, get_db

router = APIRouter(prefix="/api", tags=["attachments"])


def get_attachments_config() -> AttachmentsConfig:
    """Proveedor inyectable de la config de adjuntos (por defecto, desde entorno).

    Mismo patron que `get_session_config`: los tests la sobreescriben via
    `app.dependency_overrides` para apuntar `storage_dir` a un directorio temporal y
    fijar limites chicos.
    """
    return AttachmentsConfig.from_env()


class AttachmentResponse(BaseModel):
    """Adjunto recien subido, en estado inicial `uploaded` (pendiente de extraccion).

    No expone `storage_path` (el UUID del binario en disco): la descarga es un endpoint
    autenticado y auditado aparte (tarea 7.2), nunca una URL directa (ANEXO §5).
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
    db: Annotated[DbSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    config: Annotated[AttachmentsConfig, Depends(get_attachments_config)],
) -> AttachmentResponse:
    """Sube un adjunto al borrador de `session_id` y lo deja en estado `uploaded`.

    El dueno se deriva **siempre** de la cookie de sesion (`get_current_user`), nunca
    del payload. Una sesion ajena o inexistente responde 404 sin filtrar el motivo
    (mismo criterio que los endpoints de chat). Los rechazos de validacion (tamano,
    tipo, macros, ejecutable, PDF con contrasena, sexto adjunto) responden 422 con el
    contrato tipado descrito en el docstring del modulo -- sin escribir el binario a
    disco: el archivo rechazado no queda disponible para extraccion (tarea 2.3).
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
