"""Adapter de extracción de PDF (`pypdf`) detrás de `ExtractionPort`.

Extrae texto nativo por página, conservando marcadores `--- página N ---`
(ANEXO-ATTACHMENTS §2.2). Clasifica el PDF como escaneado cuando el promedio
de caracteres extraídos por página cae por debajo de un umbral configurable
(el umbral es un parámetro del adapter, no una constante enterrada). El
adapter solo clasifica: no decide qué hacer con un PDF escaneado (la oferta
de OCR diferida a V1.1 es responsabilidad del pipeline, no del extractor).
"""

from __future__ import annotations

import io
from importlib.metadata import version as _package_version

import pypdf

from resultarai.core.ports.extraction import (
    AttachmentKind,
    ExtractionInput,
    ExtractionResult,
    PdfStructure,
)

__all__ = ["DEFAULT_SCANNED_THRESHOLD_CHARS_PER_PAGE", "PdfEncryptedError", "PdfExtractor"]

# Valor por defecto del umbral de detección de escaneado (ANEXO §2.2: "~50
# chars/página"). Se expone como default del parámetro del constructor, no
# como constante fija usada internamente sin posibilidad de override.
DEFAULT_SCANNED_THRESHOLD_CHARS_PER_PAGE = 50.0


class PdfEncryptedError(RuntimeError):
    """El PDF está protegido con contraseña y `pypdf` lo reporta cifrado.

    La validación de subida (ANEXO §4.1) ya debería rechazar PDFs con
    contraseña antes de que lleguen a este adapter; este error es una
    defensa adicional para ese caso: un error claro, sin reintentos.
    """

    def __init__(self, filename: str) -> None:
        super().__init__(f"El PDF '{filename}' está protegido con contraseña y no puede extraerse.")
        self.filename = filename


class PdfExtractor:
    """Extrae texto nativo de PDFs página por página usando `pypdf`."""

    def __init__(
        self,
        scanned_threshold_chars_per_page: float = DEFAULT_SCANNED_THRESHOLD_CHARS_PER_PAGE,
    ) -> None:
        """Configura el umbral de chars/página que clasifica un PDF como escaneado."""
        self._scanned_threshold_chars_per_page = scanned_threshold_chars_per_page

    def extract(self, source: ExtractionInput) -> ExtractionResult:
        """Extrae `source` a texto por página con detección de escaneado."""
        if source.kind is not AttachmentKind.PDF:
            raise ValueError(
                f"PdfExtractor solo procesa AttachmentKind.PDF, recibió {source.kind!r}."
            )

        reader = self._open_reader(source)
        if reader.is_encrypted:
            raise PdfEncryptedError(source.filename)

        page_texts = [page.extract_text() or "" for page in reader.pages]
        page_count = len(page_texts)
        total_chars = sum(len(text) for text in page_texts)
        avg_chars_per_page = (total_chars / page_count) if page_count else 0.0
        is_scanned = avg_chars_per_page < self._scanned_threshold_chars_per_page

        return ExtractionResult(
            kind=AttachmentKind.PDF,
            full_text=self._build_full_text(page_texts),
            extractor_version=f"pypdf@{_package_version('pypdf')}",
            pdf=PdfStructure(
                page_count=page_count,
                avg_chars_per_page=avg_chars_per_page,
                is_scanned=is_scanned,
            ),
        )

    @staticmethod
    def _open_reader(source: ExtractionInput) -> pypdf.PdfReader:
        if source.content is not None:
            return pypdf.PdfReader(io.BytesIO(source.content))
        if source.source_path is not None:
            return pypdf.PdfReader(source.source_path)
        raise ValueError("ExtractionInput sin 'content' ni 'source_path'.")

    @staticmethod
    def _build_full_text(page_texts: list[str]) -> str:
        blocks = [
            f"--- página {page_number} ---\n{text.strip()}"
            for page_number, text in enumerate(page_texts, start=1)
        ]
        return "\n\n".join(blocks)
