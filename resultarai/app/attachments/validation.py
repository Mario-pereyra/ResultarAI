"""Validacion de seguridad OWASP de la subida de adjuntos (d14, tareas 2.2/2.3).

Pipeline de validacion del ANEXO §8 pasos [2] y [4], en orden:

1. **Sanitizar nombre** (§4.1): basename sin rutas, truncado en el primer byte NUL
   (defensa contra el truco `archivo.exe%00.pdf`), sin caracteres de control, <=255.
2. **Clasificar por extension** tras decodificar (doble extension = ultima gana):
   blocklist educativa (macros/comprimidos/ejecutables/`.doc`) ANTES que el allowlist.
3. **Limite de tamano por tipo** (matriz §9, config).
4. **Magic bytes** (§4.1): coherencia extension <-> firma binaria. El Content-Type del
   navegador NO se usa jamas para decidir.
5. **PDF con contrasena** (§4.2): detectado con `pypdf` (`is_encrypted`), sin reintentos.

Cualquier incoherencia levanta un `AttachmentRejectedError` tipado (ver ``errors.py``).
"""

from __future__ import annotations

import io
from dataclasses import dataclass

import pypdf

from resultarai.app.attachments.config import AttachmentsConfig
from resultarai.app.attachments.errors import (
    CompressedNotAllowedError,
    ExecutableRejectedError,
    FileTooLargeError,
    ImageNotSupportedError,
    LegacyDocError,
    MacrosNotAllowedError,
    PdfPasswordError,
    TypeForgedError,
    TypeNotAllowedError,
)
from resultarai.app.attachments.filetypes import (
    FileCategory,
    RejectionCategory,
    category_of,
    extension_of,
    rejection_of,
    signature_ok,
)

_MAX_NAME_LEN = 255


@dataclass
class ResolvedType:
    """Tipo resuelto de un adjunto aceptado por nombre (aun sin verificar contenido)."""

    category: FileCategory
    extension: str
    original_name: str


def sanitize_filename(raw: str | None) -> str:
    """Reduce un nombre subido a un metadato de display seguro.

    - Trunca en el primer byte NUL: `informe.exe\\x00.pdf` queda `informe.exe`, para que
      la extension peligrosa no se oculte tras el NUL (interpretacion tipo C-string).
    - Descarta cualquier componente de ruta (`/` y `\\`): solo el basename.
    - Elimina caracteres de control (salvo tab) que podrian usarse para smuggling.
    - Limita a 255 caracteres (ANEXO §4.1).
    """
    if not raw:
        return ""
    name = raw.split("\x00", 1)[0]
    name = name.replace("\\", "/").rsplit("/", 1)[-1]
    name = "".join(ch for ch in name if ch >= " " or ch == "\t").strip()
    return name[:_MAX_NAME_LEN]


def resolve_type(config: AttachmentsConfig, raw_filename: str | None) -> ResolvedType:
    """Resuelve el tipo de un adjunto por su nombre saneado.

    Evalua la blocklist educativa (macros/comprimidos/ejecutables/`.doc`) ANTES que el
    allowlist para que el rechazo eduque en vez de un "tipo no soportado" generico.
    Levanta el error tipado correspondiente si el nombre no supera la validacion.
    """
    original_name = sanitize_filename(raw_filename)
    extension = extension_of(original_name)

    rejection = rejection_of(extension)
    if rejection is not None:
        raise _rejection_error(rejection, extension)

    if extension not in config.allowed_extensions:
        raise TypeNotAllowedError(extension=extension)

    return ResolvedType(
        category=category_of(extension),
        extension=extension,
        original_name=original_name,
    )


def check_size(config: AttachmentsConfig, category: FileCategory, size_bytes: int) -> None:
    """Rechaza si `size_bytes` supera el limite configurado para la categoria."""
    limit = config.size_limit_for(category)
    if size_bytes > limit:
        raise FileTooLargeError(limit_bytes=limit, type_group=category.value)


def verify_content(extension: str, category: FileCategory, content: bytes) -> None:
    """Verifica coherencia de firma binaria y PDF sin contrasena.

    - Firma que no corresponde a la extension -> `TypeForgedError`.
    - PDF cifrado (`is_encrypted`) -> `PdfPasswordError`, sin reintentar abrirlo.

    Un PDF que pasa la firma `%PDF` pero es estructuralmente ilegible NO se rechaza aca:
    esa rama la maneja la extraccion en worker aislado (tareas 2.5/3.2), que lo deja en
    estado `error`.
    """
    if not signature_ok(extension, content):
        raise TypeForgedError(extension=extension)

    if category is FileCategory.PDF:
        _reject_encrypted_pdf(content)


def _reject_encrypted_pdf(content: bytes) -> None:
    """Rechaza un PDF protegido con contrasena (ANEXO §4.2), sin reintentos."""
    try:
        reader = pypdf.PdfReader(io.BytesIO(content))
    except Exception:
        # PDF con firma valida pero ilegible: no es competencia de la validacion de
        # subida. La extraccion aislada lo llevara a estado `error` con causa.
        return
    if reader.is_encrypted:
        raise PdfPasswordError()


def _rejection_error(
    rejection: RejectionCategory, extension: str
) -> (
    MacrosNotAllowedError
    | CompressedNotAllowedError
    | ExecutableRejectedError
    | LegacyDocError
    | ImageNotSupportedError
):
    """Traduce un motivo de la blocklist al error tipado especifico (ANEXO §10)."""
    if rejection is RejectionCategory.MACROS:
        return MacrosNotAllowedError(extension=extension)
    if rejection is RejectionCategory.COMPRESSED:
        return CompressedNotAllowedError(extension=extension)
    if rejection is RejectionCategory.EXECUTABLE:
        return ExecutableRejectedError(extension=extension)
    if rejection is RejectionCategory.IMAGE:
        return ImageNotSupportedError(extension=extension)
    return LegacyDocError(extension=extension)
