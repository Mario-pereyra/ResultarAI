"""Contract tests del adapter `extraction_pdf` (PdfExtractor / ExtractionPort)."""

from __future__ import annotations

from pathlib import Path

import pytest

from resultarai.adapters.extraction_pdf import PdfEncryptedError, PdfExtractor
from resultarai.core.ports.extraction import AttachmentKind, ExtractionInput, ExtractionPort
from tests.contracts.extraction_pdf.pdf_fixtures import (
    build_blank_pages_pdf,
    build_encrypted_pdf,
    build_native_text_pdf,
)


def test_pdf_extractor_satisfies_extraction_port_protocol() -> None:
    """Asignación tipada: PdfExtractor cumple el Protocol ExtractionPort."""
    port: ExtractionPort = PdfExtractor()
    assert isinstance(port, PdfExtractor)


def test_extract_native_text_pdf_includes_page_markers() -> None:
    """Escenario: PDF con texto nativo -- extraccion con marcadores por pagina."""
    page_texts = [
        f"Contenido de la pagina {i + 1} con texto de prueba suficiente." for i in range(8)
    ]
    pdf_bytes = build_native_text_pdf(page_texts)

    result = PdfExtractor().extract(
        ExtractionInput(kind=AttachmentKind.PDF, filename="reporte.pdf", content=pdf_bytes)
    )

    assert result.kind is AttachmentKind.PDF
    assert result.pdf is not None
    assert result.pdf.page_count == 8
    assert result.pdf.is_scanned is False
    for page_number in range(1, 9):
        assert f"--- página {page_number} ---" in result.full_text
    assert "Contenido de la pagina 1" in result.full_text
    assert "Contenido de la pagina 8" in result.full_text
    # El marcador de la página 1 debe preceder al texto de la página 1.
    assert result.full_text.index("--- página 1 ---") < result.full_text.index(
        "Contenido de la pagina 1"
    )


def test_extract_scanned_pdf_is_classified_as_scanned() -> None:
    """Escenario: PDF escaneado -- 0 chars/pagina clasifica is_scanned=True, sin OCR."""
    pdf_bytes = build_blank_pages_pdf(page_count=3)

    result = PdfExtractor().extract(
        ExtractionInput(kind=AttachmentKind.PDF, filename="escaneo.pdf", content=pdf_bytes)
    )

    assert result.pdf is not None
    assert result.pdf.page_count == 3
    assert result.pdf.avg_chars_per_page == 0.0
    assert result.pdf.is_scanned is True
    # El adapter solo clasifica: no debe insertar ningun marcador de OCR.
    assert "OCR" not in result.full_text


def test_scanned_threshold_is_a_constructor_parameter_not_a_buried_constant() -> None:
    """El umbral de escaneado es configurable por instancia del adapter."""
    page_texts = ["12345678901234567890"]  # 21 chars en 1 pagina
    pdf_bytes = build_native_text_pdf(page_texts)
    source = ExtractionInput(kind=AttachmentKind.PDF, filename="borde.pdf", content=pdf_bytes)

    default_result = PdfExtractor().extract(source)
    assert default_result.pdf is not None
    assert default_result.pdf.is_scanned is True  # 21 < 50 (default)

    lenient_result = PdfExtractor(scanned_threshold_chars_per_page=10.0).extract(source)
    assert lenient_result.pdf is not None
    assert lenient_result.pdf.is_scanned is False  # 21 >= 10 (umbral relajado)


def test_extract_rejects_encrypted_pdf_with_clear_error() -> None:
    """Defensa: si pypdf reporta cifrado, error claro (aunque no deberia llegar acá)."""
    pdf_bytes = build_encrypted_pdf()

    with pytest.raises(PdfEncryptedError) as exc_info:
        PdfExtractor().extract(
            ExtractionInput(kind=AttachmentKind.PDF, filename="protegido.pdf", content=pdf_bytes)
        )

    assert "protegido.pdf" in str(exc_info.value)


def test_extract_rejects_wrong_attachment_kind() -> None:
    """El adapter solo procesa AttachmentKind.PDF."""
    with pytest.raises(ValueError, match=r"AttachmentKind\.PDF"):
        PdfExtractor().extract(
            ExtractionInput(kind=AttachmentKind.TEXT, filename="nota.txt", content=b"hola")
        )


def test_extractor_version_reports_installed_pypdf_version() -> None:
    """`extractor_version` usa la version real instalada de pypdf (importlib.metadata)."""
    import pypdf

    pdf_bytes = build_native_text_pdf(["una sola pagina"])
    result = PdfExtractor().extract(
        ExtractionInput(kind=AttachmentKind.PDF, filename="uno.pdf", content=pdf_bytes)
    )

    assert result.extractor_version == f"pypdf@{pypdf.__version__}"


def test_extract_reads_from_source_path(tmp_path: Path) -> None:
    """El adapter tambien acepta la entrada via `source_path` (worker aislado)."""
    pdf_bytes = build_native_text_pdf(["contenido en disco"])
    pdf_path = tmp_path / "adjunto.pdf"
    pdf_path.write_bytes(pdf_bytes)

    result = PdfExtractor().extract(
        ExtractionInput(kind=AttachmentKind.PDF, filename="adjunto.pdf", source_path=str(pdf_path))
    )

    assert "contenido en disco" in result.full_text
