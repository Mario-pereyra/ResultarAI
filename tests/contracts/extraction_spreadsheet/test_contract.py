"""Contract tests del adapter `extraction_spreadsheet` (SpreadsheetExtractor / ExtractionPort)."""

from __future__ import annotations

import io
from collections.abc import Iterator
from importlib.metadata import version as pkg_version
from pathlib import Path

import openpyxl
import pytest

from resultarai.adapters.extraction_spreadsheet import SpreadsheetExtractor
from resultarai.core.ports.extraction import (
    AttachmentKind,
    ExtractionInput,
    ExtractionPort,
    ExtractionResult,
    SheetMetadata,
)
from tests.contracts.extraction_spreadsheet.spreadsheet_fixtures import (
    build_csv_bytes,
    build_empty_sheet_workbook,
    build_large_csv_bytes,
    build_semicolon_csv_bytes,
    build_tsv_bytes_with_commas_in_data,
    build_wide_workbook,
    build_windows_1252_csv_bytes,
    build_workbook_with_formula,
    build_workbook_with_hidden_sheet_and_column,
    build_workbook_with_merged_cells,
    build_workbook_with_row_overflow,
    build_workbook_with_second_sheet_active,
)


def _sheet(result: ExtractionResult, name: str) -> SheetMetadata:
    assert result.spreadsheet is not None
    for sheet in result.spreadsheet.sheets:
        if sheet.name == name:
            return sheet
    raise AssertionError(f"hoja {name!r} no encontrada en {result.spreadsheet.sheets!r}")


def test_spreadsheet_extractor_satisfies_extraction_port_protocol() -> None:
    """Asignación tipada: SpreadsheetExtractor cumple el Protocol ExtractionPort."""
    port: ExtractionPort = SpreadsheetExtractor()
    assert isinstance(port, SpreadsheetExtractor)


def test_extractor_version_reports_installed_library_versions() -> None:
    """`extractor_version` usa las versiones reales instaladas (importlib.metadata)."""
    wb_bytes = build_empty_sheet_workbook()
    result = SpreadsheetExtractor().extract(
        ExtractionInput(kind=AttachmentKind.SPREADSHEET, filename="vacio.xlsx", content=wb_bytes)
    )
    expected = (
        f"openpyxl@{pkg_version('openpyxl')}+python-calamine@{pkg_version('python-calamine')}"
    )
    assert result.extractor_version == expected


def test_extract_rejects_wrong_attachment_kind() -> None:
    """El adapter solo procesa AttachmentKind.SPREADSHEET."""
    with pytest.raises(ValueError, match="SPREADSHEET"):
        SpreadsheetExtractor().extract(
            ExtractionInput(kind=AttachmentKind.TEXT, filename="nota.txt", content=b"hola")
        )


# -- Escenario de la spec: "XLSX que excede el límite de filas de detalle" ------------


def test_xlsx_row_overflow_keeps_full_inventory_and_schema_with_omission_marker() -> None:
    """500 filas de datos -> inventario/esquema completos + primeras 150 + últimas 20."""
    wb_bytes = build_workbook_with_row_overflow(row_count=500)

    result = SpreadsheetExtractor().extract(
        ExtractionInput(
            kind=AttachmentKind.SPREADSHEET, filename="movimientos.xlsx", content=wb_bytes
        )
    )

    sheet = _sheet(result, "Movimientos")
    # Inventario y esquema SIEMPRE completos, aunque el detalle se trunque.
    assert sheet.row_count == 500
    assert sheet.column_count == 3
    assert len(sheet.columns) == 3
    headers = [c.header for c in sheet.columns]
    assert headers == ["Fecha", "Monto", "Descripcion"]
    non_empty = [c.non_empty_count for c in sheet.columns]
    assert non_empty == [500, 500, 500]

    assert "500 × 3" in result.full_text  # noqa: RUF001 - cita el texto literal producido
    assert "… (330 filas omitidas) …" in result.full_text

    # Primeras 150 filas presentes, últimas 20 presentes, resto ausente.
    assert "Registro 1" in result.full_text
    assert "Registro 150" in result.full_text
    assert "Registro 151" not in result.full_text
    assert "Registro 480" not in result.full_text
    assert "Registro 481" in result.full_text
    assert "Registro 500" in result.full_text


def test_csv_row_overflow_same_truncation_rule_as_xlsx() -> None:
    """CSV/TSV usan el mismo límite de 200 filas (150 + 20) que las hojas Excel."""
    csv_bytes = build_large_csv_bytes(row_count=500)

    result = SpreadsheetExtractor().extract(
        ExtractionInput(kind=AttachmentKind.SPREADSHEET, filename="ventas.csv", content=csv_bytes)
    )

    sheet = _sheet(result, "ventas")
    assert sheet.row_count == 500
    assert sheet.is_active is True
    assert sheet.is_hidden is False

    assert "… (330 filas omitidas) …" in result.full_text
    assert "item 1" in result.full_text
    assert "item 150" in result.full_text
    assert "item 151" not in result.full_text
    assert "item 480" not in result.full_text
    assert "item 481" in result.full_text
    assert "item 500" in result.full_text


# -- Hojas/columnas ocultas: se extraen marcadas, nunca en silencio (ANEXO §4.3) -------


def test_hidden_sheet_and_hidden_column_are_extracted_and_marked() -> None:
    wb_bytes = build_workbook_with_hidden_sheet_and_column()

    result = SpreadsheetExtractor().extract(
        ExtractionInput(kind=AttachmentKind.SPREADSHEET, filename="ventas.xlsx", content=wb_bytes)
    )

    assert result.has_marked_hidden_content is True

    ventas = _sheet(result, "Ventas")
    assert ventas.is_hidden is False
    assert ventas.is_active is True

    detalle = _sheet(result, "Detalle")
    assert detalle.is_hidden is True

    # Marcadores textuales, y el contenido de la hoja oculta NO se silencia.
    assert "Detalle [oculta]" in result.full_text
    assert "Costo interno [oculta]" in result.full_text
    assert "Solo para auditoría interna" in result.full_text


def test_active_sheet_detection_is_not_hardcoded_to_first_sheet() -> None:
    wb_bytes = build_workbook_with_second_sheet_active()

    result = SpreadsheetExtractor().extract(
        ExtractionInput(
            kind=AttachmentKind.SPREADSHEET, filename="calendario.xlsx", content=wb_bytes
        )
    )

    assert _sheet(result, "Enero").is_active is False
    assert _sheet(result, "Febrero").is_active is True


# -- Celdas combinadas: valor repetido, nunca vacío silencioso (tarea 3.1) -------------


def test_merged_cells_repeat_the_top_left_value() -> None:
    wb_bytes = build_workbook_with_merged_cells()

    result = SpreadsheetExtractor().extract(
        ExtractionInput(
            kind=AttachmentKind.SPREADSHEET, filename="combinadas.xlsx", content=wb_bytes
        )
    )

    data_section = result.full_text.split("### Datos — Combinadas")[1]
    assert data_section.count("Santa Cruz") == 2
    assert "Equipetrol" in data_section
    assert "Norte" in data_section


# -- Fórmulas: valor calculado, nunca la fórmula (tarea 3.1) ---------------------------


def test_formula_cell_never_shows_raw_formula_text() -> None:
    wb_bytes = build_workbook_with_formula()

    result = SpreadsheetExtractor().extract(
        ExtractionInput(kind=AttachmentKind.SPREADSHEET, filename="calculo.xlsx", content=wb_bytes)
    )

    assert "=A2+B2" not in result.full_text
    assert "A2+B2" not in result.full_text


# -- Ancho: >30 columnas -> TSV en bloque de código; <=30 -> tabla Markdown ------------


def test_wide_sheet_renders_as_tsv_code_block() -> None:
    wb_bytes = build_wide_workbook(column_count=35)

    result = SpreadsheetExtractor().extract(
        ExtractionInput(kind=AttachmentKind.SPREADSHEET, filename="ancha.xlsx", content=wb_bytes)
    )

    sheet = _sheet(result, "Ancha")
    assert sheet.column_count == 35
    data_section = result.full_text.split("### Datos — Ancha")[1]
    assert "```tsv" in data_section


def test_narrow_sheet_renders_as_markdown_table() -> None:
    wb_bytes = build_workbook_with_merged_cells()  # 3 columnas

    result = SpreadsheetExtractor().extract(
        ExtractionInput(
            kind=AttachmentKind.SPREADSHEET, filename="combinadas.xlsx", content=wb_bytes
        )
    )

    data_section = result.full_text.split("### Datos — Combinadas")[1]
    assert "```tsv" not in data_section
    assert "| Región | Sucursal | Total |" in data_section


# -- Hoja vacía: sin excepciones, sin columnas -----------------------------------------


def test_empty_sheet_has_no_columns_and_no_error() -> None:
    wb_bytes = build_empty_sheet_workbook()

    result = SpreadsheetExtractor().extract(
        ExtractionInput(kind=AttachmentKind.SPREADSHEET, filename="vacio.xlsx", content=wb_bytes)
    )

    sheet = _sheet(result, "Vacia")
    assert sheet.row_count == 0
    assert sheet.column_count == 0
    assert sheet.columns == []


# -- Solo se muestra el detalle de datos para las primeras 3 hojas --------------------


def test_only_first_three_sheets_get_data_detail() -> None:
    wb = openpyxl.Workbook()
    first = wb.active
    assert first is not None
    first.title = "H1"
    first.append(["Col"])
    first.append(["valor-H1"])
    for name in ["H2", "H3", "H4"]:
        ws = wb.create_sheet(name)
        ws.append(["Col"])
        ws.append([f"valor-{name}"])

    buf = io.BytesIO()
    wb.save(buf)

    result = SpreadsheetExtractor().extract(
        ExtractionInput(
            kind=AttachmentKind.SPREADSHEET, filename="cuatro.xlsx", content=buf.getvalue()
        )
    )

    assert "### Datos — H1" in result.full_text
    assert "### Datos — H2" in result.full_text
    assert "### Datos — H3" in result.full_text
    assert "### Datos — H4" not in result.full_text
    # Pero el esquema de H4 sigue completo.
    assert "### Esquema — H4" in result.full_text
    assert _sheet(result, "H4").columns[0].header == "Col"


# -- CSV/TSV: sniffing de delimitador --------------------------------------------------


def test_csv_delimiter_sniffing_handles_semicolon() -> None:
    csv_bytes = build_semicolon_csv_bytes(row_count=3)

    result = SpreadsheetExtractor().extract(
        ExtractionInput(kind=AttachmentKind.SPREADSHEET, filename="regional.csv", content=csv_bytes)
    )

    sheet = _sheet(result, "regional")
    assert sheet.column_count == 3
    assert [c.header for c in sheet.columns] == ["id", "nombre", "monto"]


def test_tsv_delimiter_sniffing_not_confused_by_commas_in_data() -> None:
    tsv_bytes = build_tsv_bytes_with_commas_in_data()

    result = SpreadsheetExtractor().extract(
        ExtractionInput(kind=AttachmentKind.SPREADSHEET, filename="clientes.tsv", content=tsv_bytes)
    )

    sheet = _sheet(result, "clientes")
    assert sheet.column_count == 3
    assert [c.header for c in sheet.columns] == ["id", "nombre", "monto"]
    assert "Perez, Juan" in result.full_text


def test_csv_windows_1252_content_is_decoded_correctly() -> None:
    csv_bytes = build_windows_1252_csv_bytes()

    result = SpreadsheetExtractor().extract(
        ExtractionInput(kind=AttachmentKind.SPREADSHEET, filename="regional.csv", content=csv_bytes)
    )

    assert "Facturación región Cochabamba" in result.full_text
    assert "Créditos año 2026" in result.full_text


def test_scan_sheet_never_retains_more_than_bounded_rows_in_memory() -> None:
    """El escaneo streaming nunca retiene más de 150+20 filas de detalle, sea cual sea el total."""
    from resultarai.adapters.extraction_spreadsheet.adapter import _scan_sheet

    def rows() -> Iterator[list[object]]:
        yield ["id"]  # encabezado
        for i in range(5000):
            yield [i]

    scan = _scan_sheet(rows())

    assert scan.total_data_rows == 5000
    assert len(scan.detail_rows) == 170  # 150 + 20, nunca las 5000 filas reales
    assert scan.omitted == 5000 - 170


def test_csv_row_count_matches_a_large_file_without_loading_it_whole() -> None:
    """5000 filas de CSV: el conteo es exacto pero el detalle sigue acotado (150+20)."""
    csv_bytes = build_large_csv_bytes(row_count=5000)

    result = SpreadsheetExtractor().extract(
        ExtractionInput(kind=AttachmentKind.SPREADSHEET, filename="grande.csv", content=csv_bytes)
    )

    sheet = _sheet(result, "grande")
    assert sheet.row_count == 5000
    assert "… (4830 filas omitidas) …" in result.full_text


# -- Entrada por `source_path` (worker aislado) ----------------------------------------


def test_extract_reads_xlsx_from_source_path(tmp_path: Path) -> None:
    wb_bytes = build_workbook_with_merged_cells()
    xlsx_path = tmp_path / "adjunto.xlsx"
    xlsx_path.write_bytes(wb_bytes)

    result = SpreadsheetExtractor().extract(
        ExtractionInput(
            kind=AttachmentKind.SPREADSHEET, filename="adjunto.xlsx", source_path=str(xlsx_path)
        )
    )

    assert "Santa Cruz" in result.full_text


def test_extract_reads_csv_from_source_path(tmp_path: Path) -> None:
    csv_bytes = build_csv_bytes(row_count=3)
    csv_path = tmp_path / "adjunto.csv"
    csv_path.write_bytes(csv_bytes)

    result = SpreadsheetExtractor().extract(
        ExtractionInput(
            kind=AttachmentKind.SPREADSHEET, filename="adjunto.csv", source_path=str(csv_path)
        )
    )

    assert "item 1" in result.full_text
