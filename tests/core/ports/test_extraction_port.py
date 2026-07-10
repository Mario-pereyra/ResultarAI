"""Tests for ExtractionPort protocol conformance and contract shape."""

import pytest
from pydantic import ValidationError

from resultarai.core.ports import (
    AttachmentKind,
    ColumnSchema,
    ColumnType,
    ExtractionInput,
    ExtractionPort,
    ExtractionResult,
    PdfStructure,
    SheetMetadata,
    SpreadsheetStructure,
    TextStructure,
)


class FakeSpreadsheetExtractor:
    """Fake extractor de hojas que conforma ExtractionPort."""

    def extract(self, source: ExtractionInput) -> ExtractionResult:
        return ExtractionResult(
            kind=source.kind,
            full_text="Hoja1\nA\tB\n1\t2\n",
            extractor_version="python-calamine@0.2.0",
            has_marked_hidden_content=True,
            spreadsheet=SpreadsheetStructure(
                sheets=[
                    SheetMetadata(
                        name="Hoja1",
                        row_count=200,
                        column_count=2,
                        is_active=True,
                        is_hidden=False,
                        columns=[
                            ColumnSchema(
                                header="A",
                                inferred_type=ColumnType.NUMBER,
                                non_empty_count=200,
                            ),
                        ],
                    ),
                    SheetMetadata(name="Oculta", row_count=1, column_count=1, is_hidden=True),
                ],
            ),
        )


def test_extraction_port_conformance() -> None:
    """FakeSpreadsheetExtractor conforma estructuralmente al Protocol."""
    extractor: ExtractionPort = FakeSpreadsheetExtractor()

    result = extractor.extract(
        ExtractionInput(
            kind=AttachmentKind.SPREADSHEET,
            filename="balance_marzo.xlsx",
            content=b"PK\x03\x04...",
        )
    )

    assert isinstance(result, ExtractionResult)
    assert result.kind is AttachmentKind.SPREADSHEET
    assert result.extractor_version == "python-calamine@0.2.0"
    assert result.has_marked_hidden_content is True
    assert result.spreadsheet is not None
    assert result.spreadsheet.sheets[0].is_active is True
    assert result.spreadsheet.sheets[1].is_hidden is True
    assert result.pdf is None
    assert result.text is None


def test_extraction_input_accepts_source_path() -> None:
    """La entrada acepta una ruta al binario en vez de bytes."""
    source = ExtractionInput(
        kind=AttachmentKind.PDF,
        filename="reporte.pdf",
        source_path="/var/attachments/8f2a.bin",
    )
    assert source.content is None
    assert source.source_path == "/var/attachments/8f2a.bin"


def test_extraction_input_requires_exactly_one_source() -> None:
    """Ni ambos ni ninguno: exactamente uno de content/source_path."""
    with pytest.raises(ValidationError):
        ExtractionInput(kind=AttachmentKind.LOG, filename="app.log")

    with pytest.raises(ValidationError):
        ExtractionInput(
            kind=AttachmentKind.LOG,
            filename="app.log",
            content=b"x",
            source_path="/var/attachments/x.bin",
        )


def test_pdf_and_text_structures_are_type_specific() -> None:
    """Cada tipo puebla solo su metadato estructural."""
    pdf_result = ExtractionResult(
        kind=AttachmentKind.PDF,
        full_text="--- página 1 ---\n(sin texto)\n",
        extractor_version="pypdf@5.1.0",
        pdf=PdfStructure(page_count=20, avg_chars_per_page=3.0, is_scanned=True),
    )
    assert pdf_result.pdf is not None
    assert pdf_result.pdf.is_scanned is True
    assert pdf_result.spreadsheet is None

    text_result = ExtractionResult(
        kind=AttachmentKind.LOG,
        full_text="```log\n...\n```",
        extractor_version="builtin-text@1",
        text=TextStructure(source_encoding="windows-1252", code_fence_language="log"),
    )
    assert text_result.text is not None
    assert text_result.text.source_encoding == "windows-1252"
