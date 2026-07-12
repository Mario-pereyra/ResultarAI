"""Errores tipados del rechazo de un adjunto (d14, tareas 2.1-2.3).

Cada rechazo lleva un ``error_code`` **estable** y un dict de ``params`` accionables
(el limite concreto, la extension detectada, etc.). El router los traduce a una
respuesta HTTP tipada; el frontend (tareas 8.2/8.4) reconstruye el texto exacto de
[ANEXO §10](../../../../design/ANEXO-ATTACHMENTS.md) en voseo a partir del codigo +
params via i18n. El backend NO renderiza el texto de §10: devuelve el contrato tipado.

Mapa error_code -> texto §10 que reconstruye el frontend:

- ``too_large``            -> "Demasiado grande" (usa ``limit_mb``/``type_group``)
- ``type_not_allowed``     -> "Tipo no soportado" (usa ``extension``)
- ``type_forged``          -> "Tipo falsificado" (usa ``extension``)
- ``macros_not_allowed``   -> "Con macros"
- ``compressed_not_allowed`` -> "Tipo no soportado" (comprimido; usa ``extension``)
- ``executable_rejected``  -> rechazo de plano de ejecutable/script
- ``legacy_doc``           -> "Word antiguo"
- ``image_not_supported``  -> "Imagen (V1)" (usa ``extension``)
- ``pdf_password``         -> "PDF protegido"
- ``too_many_attachments`` -> "Demasiados adjuntos" (usa ``limit``)

Errores de EXTRACCION (familia aparte: no son un rechazo 422 de subida, sino la causa de
que el adjunto quede en estado ``error`` tras pasar a ``extracting``; ver ANEXO §4.1 y §8
paso [4]). Se persisten en ``scan_result`` del adjunto para telemetria de Admin y el
frontend (tarea 8.2) los muestra como causa especifica del chip en estado ``error``:

- ``zip_bomb_suspected``  -> OOXML cuyo descomprimido/ratio supera el umbral (ANEXO §4.1);
                             el frontend puede reusar "Error generico de extraccion" §10.
- ``extraction_timeout``  -> el worker aislado supero el timeout (ANEXO §4.1 punto 5).
- ``extraction_failed``   -> el worker murio (crash/OOM) o el extractor fallo; el frontend
                             muestra "Error generico de extraccion" §10.

Error de DESCARGA (familia aparte, tarea 7.2, ANEXO §5): no es un rechazo de subida ni un
fallo de extraccion, sino el binario ya purgado por retencion al momento de descargar.

- ``attachment_binary_purged`` -> `GET /attachments/{id}/download` responde 409: el
                                   binario (y posiblemente el `full_text` compartido) ya
                                   fueron eliminados por `retention.py`.
"""

from __future__ import annotations

from typing import Any


class AttachmentRejectedError(Exception):
    """Base de todo rechazo de adjunto: expone ``error_code`` + ``params`` tipados."""

    error_code: str = "rejected"

    def __init__(self, message: str, params: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.params: dict[str, Any] = params or {}


class FileTooLargeError(AttachmentRejectedError):
    """El archivo supera el limite de tamano de su tipo (matriz §9, config)."""

    error_code = "too_large"

    def __init__(self, *, limit_bytes: int, type_group: str) -> None:
        limit_mb = round(limit_bytes / (1024 * 1024))
        super().__init__(
            f"el archivo supera el limite de {limit_mb} MB para {type_group}",
            {"limit_bytes": limit_bytes, "limit_mb": limit_mb, "type_group": type_group},
        )


class TypeNotAllowedError(AttachmentRejectedError):
    """La extension no esta en el allowlist de la instancia (ANEXO §4.1)."""

    error_code = "type_not_allowed"

    def __init__(self, *, extension: str) -> None:
        super().__init__(f"extension fuera del allowlist: {extension!r}", {"extension": extension})


class TypeForgedError(AttachmentRejectedError):
    """La firma binaria no corresponde a la extension declarada (ANEXO §4.1)."""

    error_code = "type_forged"

    def __init__(self, *, extension: str) -> None:
        super().__init__(
            f"la firma binaria no corresponde a {extension!r}", {"extension": extension}
        )


class MacrosNotAllowedError(AttachmentRejectedError):
    """Formato con macros (.xlsm/.docm/.pptm) rechazado (ANEXO §4.2)."""

    error_code = "macros_not_allowed"

    def __init__(self, *, extension: str) -> None:
        super().__init__(
            f"formato con macros no permitido: {extension!r}", {"extension": extension}
        )


class CompressedNotAllowedError(AttachmentRejectedError):
    """Archivo comprimido (.zip/.rar/.7z) rechazado (ANEXO §2.6)."""

    error_code = "compressed_not_allowed"

    def __init__(self, *, extension: str) -> None:
        super().__init__(
            f"archivo comprimido no permitido: {extension!r}", {"extension": extension}
        )


class ExecutableRejectedError(AttachmentRejectedError):
    """Ejecutable o script (.exe/.dll/.bat/.ps1/.sh) rechazado de plano (ANEXO §2.6)."""

    error_code = "executable_rejected"

    def __init__(self, *, extension: str) -> None:
        super().__init__(f"ejecutable/script no permitido: {extension!r}", {"extension": extension})


class LegacyDocError(AttachmentRejectedError):
    """Word binario antiguo (.doc) rechazado; pedir convertir a .docx (ANEXO §2.3)."""

    error_code = "legacy_doc"

    def __init__(self, *, extension: str) -> None:
        super().__init__(
            f"formato Word antiguo no soportado: {extension!r}", {"extension": extension}
        )


class ImageNotSupportedError(AttachmentRejectedError):
    """Imagen (.png/.jpg/.jpeg/.gif/.webp) rechazada en V1: sin vision (ANEXO §2.4, §10).

    ``error_code`` PROPIO (``image_not_supported``), distinto de ``type_not_allowed``,
    para que el frontend muestre el texto "Imagen (V1)" de §10 con su alternativa
    accionable (pegar el texto del error, o exportar el reporte a PDF/Excel) en vez del
    generico de tipo no soportado.
    """

    error_code = "image_not_supported"

    def __init__(self, *, extension: str) -> None:
        super().__init__(f"imagen no soportada en V1: {extension!r}", {"extension": extension})


class PdfPasswordError(AttachmentRejectedError):
    """PDF protegido con contrasena; no se reintenta abrirlo (ANEXO §2.2, §4.2)."""

    error_code = "pdf_password"

    def __init__(self) -> None:
        super().__init__("el PDF esta protegido con contrasena", {})


class TooManyAttachmentsError(AttachmentRejectedError):
    """Se supero el maximo de adjuntos por mensaje (config, default 5)."""

    error_code = "too_many_attachments"

    def __init__(self, *, limit: int) -> None:
        super().__init__(f"maximo {limit} adjuntos por mensaje", {"limit": limit})


class AttachmentExtractionError(Exception):
    """Base de los fallos de EXTRACCION que dejan el adjunto en estado ``error``.

    Familia distinta de ``AttachmentRejectedError`` (que es un rechazo 422 en la subida):
    estos ocurren despues, en el paso [4] del pipeline (ANEXO §8), cuando el adjunto ya
    esta persistido y pasa de ``extracting`` a ``error``. El pipeline (``extraction.py``)
    los traduce a ``status='error'`` y guarda ``error_code`` + ``params`` en
    ``scan_result`` para telemetria de Admin; nunca se propagan como 500 (la plataforma
    sigue operativa).
    """

    error_code: str = "extraction_failed"

    def __init__(self, message: str, params: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.params: dict[str, Any] = params or {}


class ZipBombSuspectedError(AttachmentExtractionError):
    """OOXML sospechoso de zip-bomb: descomprimido/ratio sobre el umbral (ANEXO §4.1).

    ``reason`` distingue por que se aborto: ``declared_size`` (el indice del ZIP declara
    un descomprimido total mayor al tope), ``declared_ratio`` (ratio comprimido:descomp.
    del indice sobre el tope) o ``expanded_size`` (la verificacion en streaming, con tope
    de bytes leidos, cruzo el limite antes de terminar).
    """

    error_code = "zip_bomb_suspected"

    def __init__(self, *, reason: str, **params: Any) -> None:
        super().__init__(
            f"OOXML sospechoso de zip-bomb ({reason})",
            {"reason": reason, **params},
        )


class ExtractionTimeoutError(AttachmentExtractionError):
    """El worker aislado supero el timeout configurado (ANEXO §4.1 punto 5, §8)."""

    error_code = "extraction_timeout"

    def __init__(self, *, timeout_seconds: float) -> None:
        super().__init__(
            f"la extraccion supero el timeout de {timeout_seconds} s",
            {"timeout_seconds": timeout_seconds},
        )


class ExtractionFailedError(AttachmentExtractionError):
    """El worker murio (crash/OOM) o el extractor fallo dentro del worker (ANEXO §4.1)."""

    error_code = "extraction_failed"

    def __init__(self, *, cause: str, **params: Any) -> None:
        super().__init__(f"la extraccion fallo: {cause}", {"cause": cause, **params})


class AttachmentBinaryPurgedError(Exception):
    """El binario del adjunto ya fue purgado por retencion (ANEXO §5, tarea 7.2).

    `retention.py` borra el binario de disco (y, si corresponde, la fila de `extractions`
    compartida) una vez vencido `retention_days`; `download.py` levanta este error tipado
    cuando el endpoint de descarga (`GET /attachments/{id}/download`) encuentra
    `storage_path IS NULL`. Nunca un 500: el router lo traduce a un 409 con `error_code`
    estable, mismo criterio que `extraction_not_ready` en la vista previa (8.3).
    """

    error_code = "attachment_binary_purged"

    def __init__(self, *, attachment_id: str) -> None:
        super().__init__(f"el binario del adjunto {attachment_id!r} ya fue purgado por retencion")
        self.attachment_id = attachment_id


class AttachmentExtractionMissingError(Exception):
    """El adjunto no tiene `Extraction` persistida todavia (`extraction_id IS NULL`).

    Desde la tarea `7.1` (`app/attachments/pipeline.py`) el endpoint de subida encola la
    extraccion real en `BackgroundTasks` DESPUES del 201, asi que esto ya no es un hueco
    de wiring sino una ventana de carrera legitima: el adjunto sigue `uploaded`/
    `extracting` porque la extraccion todavia no termino (ver el docstring de
    `app/use_cases/chat/_attachments.py` para el detalle). Se lanza en vez de fallar en
    silencio (P7) cuando la composicion del mensaje (tarea 6.3) o "pedir otra parte"
    (tarea 6.2) necesitan `full_text` y `Attachment.extraction` es `None`.
    """

    error_code = "attachment_extraction_missing"

    def __init__(self, *, attachment_id: str) -> None:
        super().__init__(f"adjunto sin extraccion persistida: {attachment_id!r}")
        self.attachment_id = attachment_id
