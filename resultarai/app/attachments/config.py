"""Configuracion de instancia para la subida de adjuntos (d14, tareas 2.1-2.3).

Todos los limites de la matriz ANEXO §9 son **defaults de configuracion**, no
constantes de codigo (regla explicita del ANEXO y de la spec `attachments-pipeline`).
Este modulo los centraliza en un dataclass leido de variables de entorno `RESULTARAI_*`,
mismo patron que `SessionConfig.from_env()` (identidad) y los `RESULTARAI_SSE_*` del
streaming de chat.

Variables reconocidas:

- ``RESULTARAI_ATTACHMENTS_STORAGE_DIR``  directorio del binario en disco (fuera del
  webroot). Default ``var/attachments`` relativo a la raiz del deployable.
- ``RESULTARAI_ATTACHMENTS_MAX_PER_MESSAGE``  maximo de adjuntos por mensaje (default 5).
- ``RESULTARAI_ATTACHMENTS_ALLOWED_EXTENSIONS``  allowlist separada por comas
  (default: la matriz §9).
- ``RESULTARAI_ATTACHMENTS_MAX_MB_<CATEGORIA>``  limite de tamano en MB por categoria
  (``EXCEL``/``CSV``/``PDF``/``DOCX``/``TEXT``/``CODE``/``LOG``); default de la matriz §9.
- ``RESULTARAI_ATTACHMENTS_ZIPBOMB_MAX_MB``  tope de tamano DESCOMPRIMIDO de un OOXML
  (proteccion zip-bomb ANEXO §4.1); default 100 MB.
- ``RESULTARAI_ATTACHMENTS_ZIPBOMB_MAX_RATIO``  ratio maximo comprimido:descomprimido de
  un OOXML antes de considerarlo zip-bomb (ANEXO §4.1); default 50.
- ``RESULTARAI_ATTACHMENTS_EXTRACTION_TIMEOUT_SECONDS``  timeout del worker aislado de
  extraccion (ANEXO §4.1 punto 5, §8 paso [4]); default 30 s.
- ``RESULTARAI_ATTACHMENTS_EXTRACTION_MEMORY_MB``  memoria (espacio de direcciones) tope
  del worker aislado, aplicada con ``RLIMIT_AS`` en el hijo; default 512 MB.
- ``RESULTARAI_ATTACHMENTS_EXTRA_SECRET_PATTERNS``  regex adicionales para el escaneo N3
  de secretos (ANEXO §4.4: la LISTA de patrones extra es configurable por instancia; los
  de fabrica van en codigo, ``data_scan.py``). **Una regex por linea** (no por comas: las
  regex suelen contener comas). Sus coincidencias se guardan totalmente redactadas.
- ``RESULTARAI_TENANT``  tenant al que se atribuyen los adjuntos (default ``default``;
  la derivacion multi-tenant real es Etapa P).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import overload

from resultarai.app.attachments.filetypes import (
    DEFAULT_ALLOWED_EXTENSIONS,
    DEFAULT_SIZE_LIMITS_BYTES,
    FileCategory,
)

_MIB = 1024 * 1024
_DEFAULT_STORAGE_DIR = "var/attachments"
_DEFAULT_MAX_PER_MESSAGE = 5
_DEFAULT_TENANT = "default"

# Proteccion zip-bomb OOXML (ANEXO §4.1): tope de descomprimido y ratio, ambos config.
_DEFAULT_ZIPBOMB_MAX_UNCOMPRESSED_BYTES = 100 * _MIB
_DEFAULT_ZIPBOMB_MAX_RATIO = 50.0

# Worker aislado de extraccion (ANEXO §4.1 punto 5, §8 paso [4]): timeout y memoria tope.
_DEFAULT_EXTRACTION_TIMEOUT_SECONDS = 30.0
_DEFAULT_EXTRACTION_MEMORY_LIMIT_BYTES = 512 * _MIB


@dataclass
class AttachmentsConfig:
    """Limites y ubicacion de almacenamiento de adjuntos, todos configurables."""

    storage_dir: Path
    tenant: str = _DEFAULT_TENANT
    max_attachments_per_message: int = _DEFAULT_MAX_PER_MESSAGE
    allowed_extensions: frozenset[str] = DEFAULT_ALLOWED_EXTENSIONS
    size_limits_bytes: dict[FileCategory, int] = field(
        default_factory=lambda: dict(DEFAULT_SIZE_LIMITS_BYTES)
    )
    zip_bomb_max_uncompressed_bytes: int = _DEFAULT_ZIPBOMB_MAX_UNCOMPRESSED_BYTES
    zip_bomb_max_ratio: float = _DEFAULT_ZIPBOMB_MAX_RATIO
    extraction_timeout_seconds: float = _DEFAULT_EXTRACTION_TIMEOUT_SECONDS
    extraction_memory_limit_bytes: int = _DEFAULT_EXTRACTION_MEMORY_LIMIT_BYTES
    # Regex extra para el escaneo N3 (ANEXO §4.4); los patrones de fabrica van en codigo.
    extra_secret_patterns: tuple[str, ...] = ()

    def size_limit_for(self, category: FileCategory) -> int:
        """Limite de tamano (bytes) para una categoria; cae al default si falta."""
        return self.size_limits_bytes.get(category, DEFAULT_SIZE_LIMITS_BYTES[category])

    @classmethod
    def from_env(cls) -> AttachmentsConfig:
        """Construye la config leyendo variables de entorno, con los defaults §9."""
        storage_dir = Path(
            os.environ.get("RESULTARAI_ATTACHMENTS_STORAGE_DIR", _DEFAULT_STORAGE_DIR)
        )
        tenant = os.environ.get("RESULTARAI_TENANT", _DEFAULT_TENANT)

        max_per_message = _int_env(
            "RESULTARAI_ATTACHMENTS_MAX_PER_MESSAGE", _DEFAULT_MAX_PER_MESSAGE
        )

        raw_allowlist = os.environ.get("RESULTARAI_ATTACHMENTS_ALLOWED_EXTENSIONS")
        if raw_allowlist:
            allowed = frozenset(
                _normalize_extension(part) for part in raw_allowlist.split(",") if part.strip()
            )
        else:
            allowed = DEFAULT_ALLOWED_EXTENSIONS

        size_limits = dict(DEFAULT_SIZE_LIMITS_BYTES)
        for category in FileCategory:
            override_mb = _int_env(f"RESULTARAI_ATTACHMENTS_MAX_MB_{category.name}", default=None)
            if override_mb is not None:
                size_limits[category] = override_mb * _MIB

        zip_bomb_max_uncompressed = (
            _int_env(
                "RESULTARAI_ATTACHMENTS_ZIPBOMB_MAX_MB",
                _DEFAULT_ZIPBOMB_MAX_UNCOMPRESSED_BYTES // _MIB,
            )
            * _MIB
        )
        zip_bomb_max_ratio = _float_env(
            "RESULTARAI_ATTACHMENTS_ZIPBOMB_MAX_RATIO", _DEFAULT_ZIPBOMB_MAX_RATIO
        )
        extraction_timeout = _float_env(
            "RESULTARAI_ATTACHMENTS_EXTRACTION_TIMEOUT_SECONDS",
            _DEFAULT_EXTRACTION_TIMEOUT_SECONDS,
        )
        extraction_memory = (
            _int_env(
                "RESULTARAI_ATTACHMENTS_EXTRACTION_MEMORY_MB",
                _DEFAULT_EXTRACTION_MEMORY_LIMIT_BYTES // _MIB,
            )
            * _MIB
        )

        raw_secret_patterns = os.environ.get("RESULTARAI_ATTACHMENTS_EXTRA_SECRET_PATTERNS", "")
        extra_secret_patterns = tuple(
            line.strip() for line in raw_secret_patterns.splitlines() if line.strip()
        )

        return cls(
            storage_dir=storage_dir,
            tenant=tenant,
            max_attachments_per_message=max_per_message,
            allowed_extensions=allowed,
            size_limits_bytes=size_limits,
            zip_bomb_max_uncompressed_bytes=zip_bomb_max_uncompressed,
            zip_bomb_max_ratio=zip_bomb_max_ratio,
            extraction_timeout_seconds=extraction_timeout,
            extraction_memory_limit_bytes=extraction_memory,
            extra_secret_patterns=extra_secret_patterns,
        )


def _normalize_extension(raw: str) -> str:
    """Normaliza una extension de la allowlist: minuscula, con punto inicial."""
    ext = raw.strip().lower()
    if ext and not ext.startswith("."):
        ext = f".{ext}"
    return ext


@overload
def _int_env(name: str, default: int) -> int: ...


@overload
def _int_env(name: str, default: None) -> int | None: ...


def _int_env(name: str, default: int | None) -> int | None:
    """Lee un entero de entorno; cae al default si falta o no parsea."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _float_env(name: str, default: float) -> float:
    """Lee un flotante de entorno; cae al default si falta o no parsea."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default
