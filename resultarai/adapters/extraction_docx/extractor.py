"""Adapter de extracción de DOCX (`mammoth`) detrás de `ExtractionPort`.

Decisión sobre la API de mammoth (evidencia empírica, ver también
`html_to_markdown.py`): el puerto Python de mammoth SÍ tiene
`convert_to_markdown()` (a diferencia del modo Markdown de mammoth.js, que el
ANEXO-ATTACHMENTS §2.3 describe como deprecado en el ecosistema Node). Pero su
escritor Markdown no sabe de tablas -- probado con un DOCX de 2x2 con
`convert_to_markdown()`: la tabla se aplana a 4 párrafos sueltos ("Columna A",
"Columna B", "dato1", "dato2"), sin ninguna marca de fila/columna. El mismo
DOCX con `convert_to_html()` produce `<table><tr><td><p>Columna A</p>...`
intacto. Como el ANEXO exige preservar "tablas Word reales", este adapter usa
`convert_to_html()` + un conversor HTML→Markdown propio y mínimo
(`html_to_markdown.py`, stdlib-only) que sí entiende `table`/`tr`/`td`/`th`.

Imágenes embebidas: se interceptan con `convert_image` (opción de mammoth)
para que nunca lleguen como `data:` URI al texto extraído (sin visión, ANEXO
§2.3) -- cada una se reemplaza por `[imagen omitida: nombre]`. La API pública
de mammoth solo expone `alt_text` y `content_type` para una imagen (no el
nombre de archivo original dentro del .docx), así que "nombre" es el alt text
de Word cuando existe, o un nombre generado (`imagen_N.<ext>`) si no.
"""

from __future__ import annotations

import io
from importlib.metadata import version as _package_version
from itertools import count
from typing import Any

import mammoth
from mammoth import html as mammoth_html

from resultarai.adapters.extraction_docx.html_to_markdown import html_to_markdown
from resultarai.core.ports.extraction import AttachmentKind, ExtractionInput, ExtractionResult

__all__ = ["DocxExtractor"]

_EXTENSION_BY_CONTENT_TYPE = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/gif": "gif",
    "image/bmp": "bmp",
    "image/tiff": "tiff",
    "image/svg+xml": "svg",
    "image/x-emf": "emf",
    "image/x-wmf": "wmf",
}


class DocxExtractor:
    """Extrae DOCX a Markdown estructurado usando `mammoth` (Python)."""

    def extract(self, source: ExtractionInput) -> ExtractionResult:
        """Extrae `source` a Markdown, preservando títulos, listas y tablas."""
        if source.kind is not AttachmentKind.DOCX:
            raise ValueError(
                f"DocxExtractor solo procesa AttachmentKind.DOCX, recibió {source.kind!r}."
            )

        image_sequence = count(1)

        def convert_image(image: Any) -> list[Any]:
            name = _image_marker_name(image, next(image_sequence))
            marker = f"[imagen omitida: {name}]"
            return [mammoth_html.element("span", {}, [mammoth_html.text(marker)])]

        result = mammoth.convert_to_html(self._open_fileobj(source), convert_image=convert_image)
        html_fragment: str = result.value

        return ExtractionResult(
            kind=AttachmentKind.DOCX,
            full_text=html_to_markdown(html_fragment),
            extractor_version=f"mammoth@{_package_version('mammoth')}",
        )

    @staticmethod
    def _open_fileobj(source: ExtractionInput) -> str | io.BytesIO:
        if source.content is not None:
            return io.BytesIO(source.content)
        if source.source_path is not None:
            return source.source_path
        raise ValueError("ExtractionInput sin 'content' ni 'source_path'.")


def _image_marker_name(image: Any, sequence_number: int) -> str:
    alt_text = getattr(image, "alt_text", None)
    if isinstance(alt_text, str) and alt_text.strip():
        return alt_text.strip()
    content_type = getattr(image, "content_type", None)
    extension = "bin"
    if isinstance(content_type, str):
        extension = _EXTENSION_BY_CONTENT_TYPE.get(content_type, "bin")
    return f"imagen_{sequence_number}.{extension}"
