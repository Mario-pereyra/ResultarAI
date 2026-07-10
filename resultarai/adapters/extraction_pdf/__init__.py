"""Adapter de extracción de PDF (pypdf, texto nativo por página, ANEXO §2.2)."""

from resultarai.adapters.extraction_pdf.extractor import (
    DEFAULT_SCANNED_THRESHOLD_CHARS_PER_PAGE,
    PdfEncryptedError,
    PdfExtractor,
)

__all__ = [
    "DEFAULT_SCANNED_THRESHOLD_CHARS_PER_PAGE",
    "PdfEncryptedError",
    "PdfExtractor",
]
