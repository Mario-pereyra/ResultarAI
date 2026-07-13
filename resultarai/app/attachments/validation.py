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
   El chequeo corre DENTRO del worker aislado de `worker.py` (Fix M2 del review final de
   d14-attachments), no en el thread sincrono del request handler -- ver
   `_reject_encrypted_pdf` mas abajo.

Cualquier incoherencia levanta un `AttachmentRejectedError` tipado (ver ``errors.py``).
"""

from __future__ import annotations

import io
from collections.abc import Callable
from dataclasses import dataclass

import pypdf

from resultarai.app.attachments.config import AttachmentsConfig
from resultarai.app.attachments.errors import (
    CompressedNotAllowedError,
    ExecutableRejectedError,
    ExtractionFailedError,
    ExtractionTimeoutError,
    FileTooLargeError,
    ImageNotSupportedError,
    LegacyDocError,
    MacrosNotAllowedError,
    PdfPasswordError,
    PdfUnreadableError,
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
from resultarai.app.attachments.worker import run_in_isolated_worker

_MAX_NAME_LEN = 255

# Callable de chequeo de cifrado que cruza al worker aislado: inyectable SOLO para tests
# (mismo patron que `ExtractorResolver` de `pipeline.py::process_attachment`), produccion
# siempre usa `_pdf_is_encrypted` (default implicito, ver `_reject_encrypted_pdf`).
EncryptionChecker = Callable[[bytes], bool]

# Timeout PROPIO y corto del chequeo de cifrado (Fix M2 del review final de
# d14-attachments): separado del timeout largo de extraccion real
# (`AttachmentsConfig.extraction_timeout_seconds`, pensado para parsear documentos
# completos, no solo leer el header de cifrado de un PDF). Leer `PdfReader.is_encrypted`
# nunca deberia tardar mas de milisegundos; 5 s da margen generoso sin exponer el request
# handler a un xref patologico sin cota.
_ENCRYPTION_CHECK_TIMEOUT_SECONDS = 5.0
# La MEMORIA, en cambio, NO se achica respecto del default de extraccion real
# (`AttachmentsConfig`, 512 MiB): un proceso hijo de `multiprocessing` ya reserva bastante
# espacio de direcciones solo para inicializarse (interprete + hilo alimentador de la
# `Queue` + las extensiones nativas de `pypdf`/`cryptography` que resuelven PDFs cifrados)
# ANTES de tocar el contenido -- un tope mas chico (p. ej. 256 MiB) hacia fallar ese
# arranque interno (`RuntimeError: can't start new thread` / alloc de la extension Rust
# de `cryptography`) incluso para un PDF chico, verificado empiricamente en los tests.
_ENCRYPTION_CHECK_MEMORY_LIMIT_BYTES = 512 * 1024 * 1024  # 512 MiB


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


def verify_content(
    extension: str,
    category: FileCategory,
    content: bytes,
    *,
    encryption_checker: EncryptionChecker | None = None,
) -> None:
    """Verifica coherencia de firma binaria y PDF sin contrasena.

    - Firma que no corresponde a la extension -> `TypeForgedError`.
    - PDF cifrado (`is_encrypted`) -> `PdfPasswordError`, sin reintentar abrirlo.
    - Chequeo de cifrado que agota su timeout o crashea (worker aislado) -> rechazo
      fail-closed con `PdfUnreadableError` (ver `_reject_encrypted_pdf`).

    Un PDF que pasa la firma `%PDF` pero es estructuralmente ilegible (y NO esta cifrado)
    no se rechaza aca: esa rama la maneja la extraccion en worker aislado (tareas 2.5/3.2),
    que lo deja en estado `error`. `encryption_checker` es inyectable SOLO para tests
    (worker con un chequeador que cuelga/lanza); produccion nunca lo pasa.
    """
    if not signature_ok(extension, content):
        raise TypeForgedError(extension=extension)

    if category is FileCategory.PDF:
        _reject_encrypted_pdf(content, checker=encryption_checker)


def _pdf_is_encrypted(content: bytes) -> bool:
    """Callable picklable: abre `content` con `pypdf` y devuelve si esta cifrado.

    Corre DENTRO del worker aislado (`_reject_encrypted_pdf`, Fix M2 del review final de
    d14-attachments): antes `pypdf.PdfReader` corria en el thread sincrono del request
    handler, sin timeout -- un PDF hostil (xref/objetos patologicos; `pypdf` tiene CVEs
    historicos de bucles infinitos) podia colgarlo indefinidamente, contradiciendo el
    ANEXO §4.1 punto 5 (parseo en aislamiento) que el resto del pipeline ya cumple. Debe
    ser una funcion a nivel de modulo (picklable) para cruzar al proceso hijo -- mismo
    criterio que `pipeline.py::resolve_extractor`.
    """
    reader = pypdf.PdfReader(io.BytesIO(content))
    return reader.is_encrypted


def _reject_encrypted_pdf(content: bytes, *, checker: EncryptionChecker | None = None) -> None:
    """Rechaza un PDF protegido con contrasena (ANEXO §4.2), sin reintentos.

    El chequeo (`checker`, default `_pdf_is_encrypted`) corre en el worker aislado de
    `worker.py` (proceso `forkserver`/`spawn`, memoria acotada) con un timeout PROPIO y
    corto (`_ENCRYPTION_CHECK_TIMEOUT_SECONDS`) -- Fix M2 del review final de
    d14-attachments (ver docstring del modulo).

    Timeout o crash del chequeo se tratan FAIL-CLOSED: `PdfUnreadableError` (422 generico,
    "no se pudo procesar"), nunca se deja pasar un PDF sin verificar contrasena. El
    extractor real conserva su propia `PdfEncryptedError`
    (`extraction_pdf/extractor.py`) como segunda defensa, sin tocar.
    """
    try:
        is_encrypted = run_in_isolated_worker(
            checker or _pdf_is_encrypted,
            content,
            timeout_seconds=_ENCRYPTION_CHECK_TIMEOUT_SECONDS,
            memory_limit_bytes=_ENCRYPTION_CHECK_MEMORY_LIMIT_BYTES,
        )
    except ExtractionTimeoutError:
        raise PdfUnreadableError(cause="timeout") from None
    except ExtractionFailedError as exc:
        raise PdfUnreadableError(cause=str(exc.params.get("cause", "unknown"))) from None
    if is_encrypted:
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
