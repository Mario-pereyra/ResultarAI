"""Clasificacion de tipos de archivo para la subida de adjuntos (d14, tareas 2.2/2.3).

Este modulo es la fuente unica de:

- **Allowlist de extensiones** (ANEXO §4.1, §9): las extensiones aceptables por defecto
  y su categoria de tratamiento. La allowlist REAL la fija la config de instancia
  (`AttachmentsConfig.allowed_extensions`); aca vive solo el default.
- **Blocklist educativa** (ANEXO §2.6, §4.2): extensiones que se rechazan con un motivo
  especifico (macros, comprimidos, ejecutables, `.doc` antiguo) para que el mensaje
  eduque en vez de un "tipo no soportado" generico.
- **Firmas binarias (magic bytes)** por extension (ANEXO §4.1): la coherencia
  extension <-> firma. El Content-Type del navegador NO se usa jamas para decidir
  (trivial de falsificar); solo los primeros bytes del archivo.

Sin dependencias nuevas: las firmas de estos formatos son pocas y estables, asi que se
verifican con comparaciones de prefijo de bytes en vez de una libreria de deteccion.
"""

from __future__ import annotations

import os
from enum import Enum

_MIB = 1024 * 1024


class FileCategory(Enum):
    """Categoria de tratamiento de un archivo aceptado (define limite y extractor)."""

    EXCEL = "excel"  # .xlsx .xls
    CSV = "csv"  # .csv .tsv
    PDF = "pdf"  # .pdf
    DOCX = "docx"  # .docx
    TEXT = "text"  # .txt .md
    CODE = "code"  # .prw .prx .tlpp .sql .json .xml .yml .yaml .ini
    LOG = "log"  # .log


class RejectionCategory(Enum):
    """Motivo por el que una extension se rechaza de plano con mensaje educativo."""

    MACROS = "macros"  # .xlsm .docm .pptm
    COMPRESSED = "compressed"  # .zip .rar .7z
    EXECUTABLE = "executable"  # .exe .dll .bat .ps1 .sh
    LEGACY_DOC = "legacy_doc"  # .doc (Word 97-2003 binario)
    IMAGE = "image"  # .png .jpg .jpeg .gif .webp (V1 sin vision, ANEXO §2.4)


# Extension -> categoria de tratamiento. Sus claves son la allowlist por defecto
# (ANEXO §9). La allowlist efectiva la decide la config; esta tabla mapea cada
# extension conocida a como se trata.
_EXTENSION_CATEGORY: dict[str, FileCategory] = {
    ".xlsx": FileCategory.EXCEL,
    ".xls": FileCategory.EXCEL,
    ".csv": FileCategory.CSV,
    ".tsv": FileCategory.CSV,
    ".pdf": FileCategory.PDF,
    ".docx": FileCategory.DOCX,
    ".txt": FileCategory.TEXT,
    ".md": FileCategory.TEXT,
    ".prw": FileCategory.CODE,
    ".prx": FileCategory.CODE,
    ".tlpp": FileCategory.CODE,
    ".sql": FileCategory.CODE,
    ".json": FileCategory.CODE,
    ".xml": FileCategory.CODE,
    ".yml": FileCategory.CODE,
    ".yaml": FileCategory.CODE,
    ".ini": FileCategory.CODE,
    ".log": FileCategory.LOG,
}

# Allowlist de extensiones por defecto (ANEXO §9, tarea 2.2).
DEFAULT_ALLOWED_EXTENSIONS: frozenset[str] = frozenset(_EXTENSION_CATEGORY)

# Limite de tamano por categoria (MB), defaults de la matriz ANEXO §9. Son CONFIG:
# `AttachmentsConfig` los expone y permite overridearlos por instancia.
DEFAULT_SIZE_LIMITS_MB: dict[FileCategory, int] = {
    FileCategory.EXCEL: 20,
    FileCategory.CSV: 50,
    FileCategory.PDF: 30,
    FileCategory.DOCX: 20,
    FileCategory.TEXT: 5,
    FileCategory.CODE: 5,
    FileCategory.LOG: 10,
}

DEFAULT_SIZE_LIMITS_BYTES: dict[FileCategory, int] = {
    category: mb * _MIB for category, mb in DEFAULT_SIZE_LIMITS_MB.items()
}

# Blocklist educativa: extension -> motivo de rechazo especifico (ANEXO §2.6, §4.2).
# Se evalua ANTES que la allowlist para que el mensaje eduque ("guardalo como .xlsx")
# en vez de un generico "tipo no soportado".
_REJECTED_EXTENSIONS: dict[str, RejectionCategory] = {
    ".xlsm": RejectionCategory.MACROS,
    ".docm": RejectionCategory.MACROS,
    ".pptm": RejectionCategory.MACROS,
    ".zip": RejectionCategory.COMPRESSED,
    ".rar": RejectionCategory.COMPRESSED,
    ".7z": RejectionCategory.COMPRESSED,
    ".exe": RejectionCategory.EXECUTABLE,
    ".dll": RejectionCategory.EXECUTABLE,
    ".bat": RejectionCategory.EXECUTABLE,
    ".ps1": RejectionCategory.EXECUTABLE,
    ".sh": RejectionCategory.EXECUTABLE,
    ".doc": RejectionCategory.LEGACY_DOC,
    # Imagenes: rechazo claro en V1 (sin vision), con alternativa accionable (ANEXO §2.4,
    # §10 "Imagen (V1)"). error_code PROPIO `image_not_supported`, distinguible de
    # `type_not_allowed`, para que el frontend muestre el texto especifico con su
    # alternativa (pegar el texto del error / exportar a PDF o Excel).
    ".png": RejectionCategory.IMAGE,
    ".jpg": RejectionCategory.IMAGE,
    ".jpeg": RejectionCategory.IMAGE,
    ".gif": RejectionCategory.IMAGE,
    ".webp": RejectionCategory.IMAGE,
}

# Firmas binarias por extension (ANEXO §4.1). Extensiones ausentes = formato de texto
# sin firma fiable (csv/tsv/txt/md/codigo/log): no se verifica magic byte.
_ZIP_MAGICS: tuple[bytes, ...] = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")
_OLE2_MAGIC: tuple[bytes, ...] = (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",)
_PDF_MAGIC: tuple[bytes, ...] = (b"%PDF-",)

_EXTENSION_SIGNATURES: dict[str, tuple[bytes, ...]] = {
    ".xlsx": _ZIP_MAGICS,  # OOXML = ZIP
    ".docx": _ZIP_MAGICS,  # OOXML = ZIP
    ".xls": _OLE2_MAGIC,  # BIFF/OLE2 compound file
    ".pdf": _PDF_MAGIC,
}

# Extensiones OOXML (contenedor ZIP): requieren proteccion zip-bomb al parsear (§4.1).
OOXML_ZIP_EXTENSIONS: frozenset[str] = frozenset({".xlsx", ".docx"})


def extension_of(name: str) -> str:
    """Devuelve la extension final (en minusculas) de un nombre ya saneado.

    Usa la ULTIMA extension a proposito: `informe.pdf.exe` clasifica como `.exe`
    (doble extension, ANEXO §4.1), no como `.pdf`.
    """
    return os.path.splitext(name)[1].lower()


def rejection_of(extension: str) -> RejectionCategory | None:
    """Motivo de rechazo educativo de una extension, o `None` si no esta en la blocklist."""
    return _REJECTED_EXTENSIONS.get(extension)


def is_ooxml(extension: str) -> bool:
    """`True` si la extension es un OOXML (contenedor ZIP) sujeto a proteccion zip-bomb."""
    return extension in OOXML_ZIP_EXTENSIONS


def category_of(extension: str) -> FileCategory:
    """Categoria de tratamiento de una extension del allowlist.

    Para una extension que la config habilito pero no esta mapeada aca (allowlist
    custom de instancia), cae a `TEXT` (limite conservador, sin firma binaria).
    """
    return _EXTENSION_CATEGORY.get(extension, FileCategory.TEXT)


def signature_ok(extension: str, content: bytes) -> bool:
    """Verifica que los primeros bytes de `content` correspondan a la extension.

    `True` si la extension no requiere firma (formatos de texto) o si el prefijo
    binario coincide con alguna firma conocida. Para PDF se admite la firma dentro
    de los primeros 1024 bytes (el estandar permite bytes previos a `%PDF-`).
    """
    signatures = _EXTENSION_SIGNATURES.get(extension)
    if signatures is None:
        return True
    if extension == ".pdf":
        head = content[:1024]
        return any(signature in head for signature in signatures)
    return any(content.startswith(signature) for signature in signatures)
