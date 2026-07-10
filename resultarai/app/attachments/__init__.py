"""Contexto de adjuntos: subida, validacion de seguridad OWASP y persistencia (d14).

Alcance actual (tareas 2.1-2.5, 3.5, 4.1-4.3, 5.1-5.3, 6.1-6.3): endpoint de subida
multipart, limites por tipo y por mensaje configurables, validacion de tipo real
(allowlist + magic bytes), rechazo de formatos activos/peligrosos y de imagenes en V1,
proteccion zip-bomb OOXML, worker de parseo aislado con timeout + memoria acotada,
sanitizacion, heuristica anti prompt-injection, escaneo de niveles de datos N2/N3
(secretos -> bloqueo; PII -> confirmacion auditada), presupuesto de tokens y truncado
por relevancia UNA VEZ al insertar (`truncation.py`) y consulta de insercion/tokens para
los endpoints de estado y vista previa (`insertion.py`). La composicion server-side del
mensaje con los adjuntos AL FINAL vive en `app/use_cases/chat/_attachments.py` (orquesta
sesion/mensaje, fuera de este paquete que es agnostico de chat). La persistencia con
dedup por sha256 (tarea 7.1) llega en una tarea posterior del mismo change.
"""

from __future__ import annotations

from resultarai.app.attachments.config import AttachmentsConfig
from resultarai.app.attachments.confirmation import (
    NoPendingConfirmationError,
    confirm_test_data,
)
from resultarai.app.attachments.data_scan import (
    PiiFinding,
    SecretFinding,
    is_sendable,
    scan_for_pii,
    scan_for_secrets,
)
from resultarai.app.attachments.dependency import get_attachments_config
from resultarai.app.attachments.errors import (
    AttachmentExtractionError,
    AttachmentExtractionMissingError,
    AttachmentRejectedError,
    CompressedNotAllowedError,
    ExecutableRejectedError,
    ExtractionFailedError,
    ExtractionTimeoutError,
    FileTooLargeError,
    ImageNotSupportedError,
    LegacyDocError,
    MacrosNotAllowedError,
    PdfPasswordError,
    TooManyAttachmentsError,
    TypeForgedError,
    TypeNotAllowedError,
    ZipBombSuspectedError,
)
from resultarai.app.attachments.extraction import (
    ExtractionOutcome,
    extract_attachment,
    run_extraction,
)
from resultarai.app.attachments.filetypes import FileCategory
from resultarai.app.attachments.insertion import (
    TokenUsageInfo,
    describe_token_usage,
    find_first_insertion,
    resolve_token_counter_model,
)
from resultarai.app.attachments.spotlight import wrap_extraction
from resultarai.app.attachments.truncation import (
    TruncationResult,
    find_section_body,
    truncate_for_insertion,
    truncate_fragment,
)
from resultarai.app.attachments.upload import UploadSource, create_attachment
from resultarai.app.attachments.worker import run_in_isolated_worker
from resultarai.app.attachments.zip_guard import inspect_ooxml_for_zip_bomb

__all__ = [
    "AttachmentExtractionError",
    "AttachmentExtractionMissingError",
    "AttachmentRejectedError",
    "AttachmentsConfig",
    "CompressedNotAllowedError",
    "ExecutableRejectedError",
    "ExtractionFailedError",
    "ExtractionOutcome",
    "ExtractionTimeoutError",
    "FileCategory",
    "FileTooLargeError",
    "ImageNotSupportedError",
    "LegacyDocError",
    "MacrosNotAllowedError",
    "NoPendingConfirmationError",
    "PdfPasswordError",
    "PiiFinding",
    "SecretFinding",
    "TokenUsageInfo",
    "TooManyAttachmentsError",
    "TruncationResult",
    "TypeForgedError",
    "TypeNotAllowedError",
    "UploadSource",
    "ZipBombSuspectedError",
    "confirm_test_data",
    "create_attachment",
    "describe_token_usage",
    "extract_attachment",
    "find_first_insertion",
    "find_section_body",
    "get_attachments_config",
    "inspect_ooxml_for_zip_bomb",
    "is_sendable",
    "resolve_token_counter_model",
    "run_extraction",
    "run_in_isolated_worker",
    "scan_for_pii",
    "scan_for_secrets",
    "truncate_for_insertion",
    "truncate_fragment",
    "wrap_extraction",
]
