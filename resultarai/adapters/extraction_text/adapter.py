"""Adapter de extracción determinista para texto, código y logs (`ExtractionPort`).

Implementa `ExtractionPort` para `.txt` / `.md`, código
(`.prw .prx .tlpp .sql .json .xml .yml .yaml .ini`) y `.log`
(ANEXO-ATTACHMENTS §2.5, tarea `d14-attachments` 3.4). Solo usa la librería
estándar: no hay parser de por medio, el "extractor" es encoding + envoltura.

**Pasos deterministas:**

1. **Encoding → UTF-8.** Se intenta `utf-8` (con o sin BOM); si falla, se
   prueba `windows-1252` (frecuente en fuentes AdvPL viejos y logs de
   Protheus generados en Windows); si también falla, `latin-1` como último
   recurso (mapea 1:1 los 256 valores de byte, nunca puede fallar, así que
   la extracción de texto SIEMPRE produce algo). `TextStructure.source_encoding`
   guarda el encoding realmente usado.
2. **Normalización de saltos de línea:** `\\r\\n` y `\\r` sueltos se
   normalizan a `\\n`.
3. **Envoltura en bloque de código** con lenguaje según la extensión
   (`TextStructure.code_fence_language`), salvo `.md` — ver decisión abajo.

**Decisión — `.md` sin fence:** un `.md` ya es Markdown; envolverlo en un
bloque de código lo convertiría en texto literal para el modelo (perdería
títulos, listas, tablas — exactamente la estructura que lo hace útil). Se
inserta tal cual, sin fence, y `code_fence_language` queda en `None`. El
resto de extensiones (incluido `.txt`) sí se envuelve: `.txt` con el
lenguaje explícito `text` (más informativo para el modelo que un fence sin
etiqueta) y las demás con su lenguaje correspondiente.

**Fences seguros:** si el contenido ya trae una racha de backticks (p. ej.
un `.md`... no, ese no lleva fence; pero un `.log`/`.sql` podría citar un
bloque de código de tres backticks), se usa una cerca más larga que la
racha más larga encontrada — técnica estándar de Markdown para que el
contenido nunca pueda "escapar" del bloque (relevante para la defensa
anti-prompt-injection de ANEXO §4.3: el contenido del adjunto es dato, no
instrucción, y no debe poder alterar la estructura del mensaje).

**Fuera de alcance (a propósito):** el truncado tail-first de logs es
responsabilidad de la etapa de presupuesto (tarea 6.1), no de este
extractor. Este adapter siempre produce el `full_text` COMPLETO; la señal
para que la etapa de presupuesto sepa que debe truncar tail-first es
`ExtractionResult.kind == AttachmentKind.LOG`, no algo que este módulo
decida.
"""

from __future__ import annotations

import re
from pathlib import Path
from platform import python_version

from resultarai.core.ports.extraction import (
    AttachmentKind,
    ExtractionInput,
    ExtractionResult,
    TextStructure,
)

__all__ = ["TextExtractor"]

_SUPPORTED_KINDS = frozenset({AttachmentKind.TEXT, AttachmentKind.CODE, AttachmentKind.LOG})

_FALLBACK_ENCODINGS: tuple[str, ...] = ("utf-8", "cp1252", "latin-1")

_FENCE_LANGUAGE_BY_EXTENSION: dict[str, str | None] = {
    ".prw": "advpl",
    ".prx": "advpl",
    ".tlpp": "advpl",
    ".sql": "sql",
    ".log": "log",
    ".json": "json",
    ".xml": "xml",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".ini": "ini",
    ".txt": "text",
    ".md": None,  # ya es Markdown: se inserta directo, sin fence (ver docstring).
}

_BACKTICK_RUN_RE = re.compile(r"`+")


def _decode(raw: bytes) -> tuple[str, str]:
    """Decodifica `raw` probando encodings en cascada; `latin-1` nunca falla.

    `utf-8` estricto no falla ante un BOM (`\\ufeff` es un carácter válido en
    UTF-8), así que se le quita aparte una vez decodificado, sin necesitar
    un encoding `utf-8-sig` separado.
    """
    last_encoding = _FALLBACK_ENCODINGS[-1]
    for encoding in _FALLBACK_ENCODINGS:
        try:
            return raw.decode(encoding).removeprefix("\ufeff"), encoding
        except UnicodeDecodeError:
            continue
    # Inalcanzable en la práctica: latin-1 mapea los 256 valores de byte.
    text = raw.decode(last_encoding, errors="replace").removeprefix("\ufeff")
    return text, last_encoding  # pragma: no cover


def _normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _extension(filename: str) -> str:
    return Path(filename).suffix.lower()


def _fence_language(filename: str) -> str | None:
    return _FENCE_LANGUAGE_BY_EXTENSION.get(_extension(filename), "text")


def _safe_fence(text: str) -> str:
    """Cerca de backticks más larga que la racha más larga presente en `text`."""
    longest = max((len(run) for run in _BACKTICK_RUN_RE.findall(text)), default=0)
    return "`" * max(3, longest + 1)


def _wrap(text: str, language: str | None) -> str:
    if language is None:
        return text
    fence = _safe_fence(text)
    body = text.strip("\n")
    return f"{fence}{language}\n{body}\n{fence}\n"


def _read_all_bytes(source: ExtractionInput) -> bytes:
    if source.content is not None:
        return source.content
    assert source.source_path is not None  # garantizado por ExtractionInput
    return Path(source.source_path).read_bytes()


def _extractor_version() -> str:
    return f"stdlib-codecs@python{python_version()}"


class TextExtractor:
    """Adapter de `ExtractionPort` para texto, código y logs (solo stdlib)."""

    def extract(self, source: ExtractionInput) -> ExtractionResult:
        if source.kind not in _SUPPORTED_KINDS:
            raise ValueError(
                f"TextExtractor solo procesa AttachmentKind.TEXT/CODE/LOG, recibió {source.kind!r}."
            )
        raw = _read_all_bytes(source)
        decoded, encoding = _decode(raw)
        normalized = _normalize_newlines(decoded)

        language = _fence_language(source.filename)
        full_text = _wrap(normalized, language)

        return ExtractionResult(
            kind=source.kind,
            full_text=full_text,
            extractor_version=_extractor_version(),
            has_marked_hidden_content=False,
            text=TextStructure(source_encoding=encoding, code_fence_language=language),
        )
