"""Adapter de extracción determinista para hojas de cálculo (`ExtractionPort`).

Implementa `ExtractionPort` para `.xlsx` / `.xls` / `.csv` / `.tsv`
(ANEXO-ATTACHMENTS §2.1, tarea `d14-attachments` 3.1).

**Reparto de responsabilidades entre librerías** (documentado según lo pedido
por la tarea):

- **`python-calamine`** es el lector principal de datos para `.xlsx`/`.xls`:
  está implementado en Rust y es robusto ante archivos hostiles/malformados;
  además ya entrega **valores calculados** para las celdas con fórmula (nunca
  la fórmula en sí) y expone el estado oculto/visible de cada hoja vía
  `sheets_metadata`.
- **`openpyxl`** se usa *solo* para `.xlsx` (no puede abrir el binario
  `.xls`) y *solo* para los dos datos que `python-calamine` no expone: la
  hoja activa (`Workbook.active`) y las columnas ocultas
  (`column_dimensions[...].hidden`). Si `openpyxl` no logra abrir un `.xlsx`
  hostil que `python-calamine` sí pudo leer, la extracción de datos igual se
  completa — se pierde solo la marca de hoja activa/columnas ocultas
  (degradación explícita, nunca un fallo total).
- **`csv` de la librería estándar** en modo streaming para `.csv`/`.tsv`:
  nunca se materializa el archivo completo como una lista en memoria; las
  estadísticas de esquema (tipo inferido, no-vacíos) se acumulan fila a fila
  y solo se retiene un buffer acotado (≤200 filas) para el detalle — el
  archivo puede ser arbitrariamente grande sin que la memoria del proceso
  crezca con él.

**Otras decisiones de diseño no fijadas explícitamente por la spec:**

- Se asume que la primera fila de cada hoja/archivo es la fila de
  encabezados (si la hoja tiene al menos una fila); una hoja vacía no tiene
  encabezado ni columnas.
- Celdas combinadas: se repite el valor de la celda superior-izquierda en
  todo el rango combinado (nunca se deja "en silencio": la posición de
  columna siempre está presente, vacía o repetida, pero nunca ausente).
- `ColumnType.FORMULA` no se infiere nunca en este adapter: `python-calamine`
  ya entrega el valor calculado y no conserva si la celda de origen tenía
  una fórmula, así que no hay forma determinista de distinguirlo del resto.
- Se muestra el detalle de datos (tabla) de las primeras 3 hojas en el orden
  en que aparecen en el archivo; el resto de las hojas solo aporta
  inventario + esquema. Las hojas ocultas participan del mismo orden (no se
  saltean ni se silencian).
- CSV/TSV se modela como una única "hoja" cuyo nombre es el `filename` de
  entrada, siempre activa y nunca oculta (el formato no tiene ese concepto).
- Lectura de `.xlsx`/`.xls` con `skip_empty_area=False` en `python-calamine`:
  la grilla resultante queda alineada 1:1 (fila/columna absolutas desde
  A1) con las coordenadas de `openpyxl` y con `merged_cell_ranges` (que
  `python-calamine` siempre reporta en coordenadas absolutas), evitando así
  tener que traducir índices entre ambas librerías.
"""

from __future__ import annotations

import csv
import io
from collections import Counter, deque
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date, datetime
from importlib.metadata import version as pkg_version
from pathlib import Path
from re import Pattern
from re import compile as re_compile
from typing import IO, Any

import openpyxl
import python_calamine as calamine

from resultarai.core.ports.extraction import (
    AttachmentKind,
    ColumnSchema,
    ColumnType,
    ExtractionInput,
    ExtractionResult,
    SheetMetadata,
    SpreadsheetStructure,
)

__all__ = ["SpreadsheetExtractor"]

_MAX_DETAIL_ROWS = 200
_HEAD_ROWS = 150
_TAIL_ROWS = 20
_MAX_DETAIL_SHEETS = 3
_MAX_MARKDOWN_COLUMNS = 30
_SNIFF_SAMPLE_BYTES = 65536

_NUMBER_RE: Pattern[str] = re_compile(r"^[+-]?(\d{1,3}(?:[.,]\d{3})+|\d+)([.,]\d+)?%?$")
_DATE_RE: Pattern[str] = re_compile(
    r"^\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2}(:\d{2})?)?$"
    r"|^\d{2}/\d{2}/\d{4}$"
    r"|^\d{2}-\d{2}-\d{4}$"
    r"|^\d{4}/\d{2}/\d{2}$"
)

_TYPE_PRIORITY: list[ColumnType] = [ColumnType.DATE, ColumnType.NUMBER, ColumnType.TEXT]


@dataclass
class _ScanResult:
    """Resultado de escanear una hoja/archivo fila a fila (streaming)."""

    header: list[Any] | None = None
    column_count: int = 0
    total_data_rows: int = 0
    non_empty_counts: list[int] = field(default_factory=list)
    type_counts: list[Counter[ColumnType]] = field(default_factory=list)
    detail_rows: list[list[Any]] = field(default_factory=list)
    omitted: int = 0


def _ensure_width(result: _ScanResult, width: int) -> None:
    while len(result.non_empty_counts) < width:
        result.non_empty_counts.append(0)
        result.type_counts.append(Counter())


def _looks_like_number(text: str) -> bool:
    return bool(_NUMBER_RE.match(text))


def _looks_like_date(text: str) -> bool:
    return bool(_DATE_RE.match(text))


def _classify(value: Any) -> ColumnType | None:
    """Clasifica un valor de celda; `None` si la celda está vacía."""
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if _looks_like_number(text):
            return ColumnType.NUMBER
        if _looks_like_date(text):
            return ColumnType.DATE
        return ColumnType.TEXT
    if isinstance(value, bool):
        # Sin tipo booleano dedicado en el port; se lo trata como texto.
        return ColumnType.TEXT
    if isinstance(value, int | float):
        return ColumnType.NUMBER
    if isinstance(value, date | datetime):
        return ColumnType.DATE
    return ColumnType.TEXT


def _majority_type(counter: Counter[ColumnType]) -> ColumnType:
    if not counter:
        return ColumnType.TEXT
    best_count = max(counter.values())
    for candidate in _TYPE_PRIORITY:
        if counter.get(candidate, 0) == best_count:
            return candidate
    return ColumnType.TEXT  # pragma: no cover - inalcanzable, _TYPE_PRIORITY cubre todo ColumnType


def _display(value: Any) -> str:
    """Representación textual de un valor de celda para tabla/TSV."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _header_text(header_row: list[Any] | None, idx: int) -> str | None:
    if header_row is None or idx >= len(header_row):
        return None
    value = header_row[idx]
    text = _display(value).strip()
    return text or None


def _scan_sheet(rows: Iterator[list[Any]]) -> _ScanResult:
    """Escanea una hoja/archivo fila a fila sin materializar todas las filas.

    Retiene como mucho `_MAX_DETAIL_ROWS` filas en memoria (más un buffer de
    cola acotado a `_TAIL_ROWS`); las estadísticas de esquema (no-vacíos,
    tipo inferido) se acumulan de forma incremental por columna.
    """
    result = _ScanResult()
    try:
        header_row = next(rows)
    except StopIteration:
        return result

    result.header = header_row
    result.column_count = len(header_row)
    _ensure_width(result, result.column_count)

    buffer: list[list[Any]] = []
    tail: deque[list[Any]] = deque(maxlen=_TAIL_ROWS)

    for row in rows:
        row_width = len(row)
        if row_width > result.column_count:
            result.column_count = row_width
            _ensure_width(result, result.column_count)
        result.total_data_rows += 1
        for idx in range(result.column_count):
            value = row[idx] if idx < row_width else None
            col_type = _classify(value)
            if col_type is not None:
                result.non_empty_counts[idx] += 1
                result.type_counts[idx][col_type] += 1
        if len(buffer) < _MAX_DETAIL_ROWS:
            buffer.append(row)
        tail.append(row)

    if result.total_data_rows <= _MAX_DETAIL_ROWS:
        result.detail_rows = buffer
        result.omitted = 0
    else:
        result.detail_rows = buffer[:_HEAD_ROWS] + list(tail)
        result.omitted = result.total_data_rows - _HEAD_ROWS - _TAIL_ROWS

    return result


def _apply_merges(
    grid: list[list[Any]], merges: list[tuple[tuple[int, int], tuple[int, int]]]
) -> None:
    """Repite el valor superior-izquierdo en todo el rango combinado.

    `merges` llega en coordenadas absolutas (fila, columna) 0-indexadas,
    igual que `grid` porque se lee con `skip_empty_area=False`.
    """
    for (r0, c0), (r1, c1) in merges:
        if r0 >= len(grid) or c0 >= len(grid[r0]):
            continue
        top_left = grid[r0][c0]
        for r in range(r0, r1 + 1):
            if r >= len(grid):
                continue
            row = grid[r]
            for c in range(c0, c1 + 1):
                if c >= len(row) or (r == r0 and c == c0):
                    continue
                row[c] = top_left


def _hidden_columns(ws: Any) -> set[int]:
    """Índices 0-based de columnas ocultas de una hoja `openpyxl`."""
    hidden: set[int] = set()
    for dim in ws.column_dimensions.values():
        if dim.hidden and dim.min is not None and dim.max is not None:
            hidden.update(range(dim.min - 1, dim.max))
    return hidden


def _mark(name: str, is_hidden: bool) -> str:
    return f"{name} [oculta]" if is_hidden else name


def _escape_markdown_cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def _escape_tsv_cell(text: str) -> str:
    return text.replace("\t", " ").replace("\n", " ").replace("\r", " ")


def _header_cells(
    header_row: list[Any] | None, column_count: int, hidden_column_idxs: set[int]
) -> list[str]:
    cells: list[str] = []
    for idx in range(column_count):
        text = _header_text(header_row, idx) or "(sin encabezado)"
        if idx in hidden_column_idxs:
            text = f"{text} [oculta]"
        cells.append(text)
    return cells


def _row_cells(row: list[Any], column_count: int) -> list[str]:
    return [_display(row[idx]) if idx < len(row) else "" for idx in range(column_count)]


def _render_inventory(sheets: list[SheetMetadata]) -> str:
    lines = [
        "## Inventario de hojas",
        "",
        "| Hoja | Filas × Columnas | Activa |",  # noqa: RUF001 - cita el texto literal de la spec
        "|---|---|---|",
    ]
    for sheet in sheets:
        name = _escape_markdown_cell(_mark(sheet.name, sheet.is_hidden))
        active = "Sí" if sheet.is_active else "No"
        dims = f"{sheet.row_count} × {sheet.column_count}"  # noqa: RUF001
        lines.append(f"| {name} | {dims} | {active} |")
    lines.append("")
    return "\n".join(lines)


def _render_schema_section(
    name: str, is_hidden: bool, columns: list[ColumnSchema], hidden_column_idxs: set[int]
) -> str:
    title = f"### Esquema — {_mark(name, is_hidden)}"
    if not columns:
        return f"{title}\n\n_(hoja vacía, sin columnas)_\n"
    lines = [title, "", "| Columna | Tipo | No vacíos |", "|---|---|---|"]
    for idx, column in enumerate(columns):
        header = column.header or "(sin encabezado)"
        if idx in hidden_column_idxs:
            header = f"{header} [oculta]"
        header = _escape_markdown_cell(header)
        lines.append(f"| {header} | {column.inferred_type.value} | {column.non_empty_count} |")
    lines.append("")
    return "\n".join(lines)


def _render_data_section(
    name: str,
    is_hidden: bool,
    header_row: list[Any] | None,
    column_count: int,
    detail_rows: list[list[Any]],
    omitted: int,
    hidden_column_idxs: set[int],
) -> str:
    title = f"### Datos — {_mark(name, is_hidden)}"
    if column_count == 0:
        return f"{title}\n\n_(hoja vacía, sin datos)_\n"

    header_cells = _header_cells(header_row, column_count, hidden_column_idxs)
    marker_text = f"… ({omitted} filas omitidas) …"
    marker_row = [marker_text, *([""] * (column_count - 1))] if omitted else None

    body: str
    if column_count <= _MAX_MARKDOWN_COLUMNS:
        lines = [
            "| " + " | ".join(_escape_markdown_cell(c) for c in header_cells) + " |",
            "|" + "---|" * column_count,
        ]
        head = detail_rows[:_HEAD_ROWS] if omitted else detail_rows
        tail = detail_rows[_HEAD_ROWS:] if omitted else []
        for row in head:
            cells = _row_cells(row, column_count)
            lines.append("| " + " | ".join(_escape_markdown_cell(c) for c in cells) + " |")
        if marker_row is not None:
            lines.append("| " + " | ".join(_escape_markdown_cell(c) for c in marker_row) + " |")
        for row in tail:
            cells = _row_cells(row, column_count)
            lines.append("| " + " | ".join(_escape_markdown_cell(c) for c in cells) + " |")
        body = "\n".join(lines)
    else:
        lines = ["\t".join(_escape_tsv_cell(c) for c in header_cells)]
        head = detail_rows[:_HEAD_ROWS] if omitted else detail_rows
        tail = detail_rows[_HEAD_ROWS:] if omitted else []
        for row in head:
            cells = _row_cells(row, column_count)
            lines.append("\t".join(_escape_tsv_cell(c) for c in cells))
        if marker_row is not None:
            lines.append(marker_text)
        for row in tail:
            cells = _row_cells(row, column_count)
            lines.append("\t".join(_escape_tsv_cell(c) for c in cells))
        body = "```tsv\n" + "\n".join(lines) + "\n```"

    return f"{title}\n\n{body}\n"


def _extension(filename: str) -> str:
    return Path(filename).suffix.lower()


def _read_all_bytes(source: ExtractionInput) -> bytes:
    if source.content is not None:
        return source.content
    assert source.source_path is not None  # garantizado por ExtractionInput
    return Path(source.source_path).read_bytes()


def _open_source_stream(source: ExtractionInput) -> IO[bytes]:
    if source.content is not None:
        return io.BytesIO(source.content)
    assert source.source_path is not None
    return Path(source.source_path).open("rb")


def _detect_encoding(sample: bytes) -> str:
    # Recortamos el final de la muestra: un corte a mitad de una secuencia
    # UTF-8 multibyte en el límite del buffer de sniffing no debe hacer
    # fallar la detección de un archivo que en realidad es UTF-8 válido.
    probe = sample[:-4] if len(sample) > 4 else sample
    for encoding in ("utf-8-sig", "utf-8"):
        try:
            probe.decode(encoding)
            return encoding
        except UnicodeDecodeError:
            continue
    try:
        probe.decode("cp1252")
        return "cp1252"
    except UnicodeDecodeError:
        return "latin-1"  # latin-1 mapea 1:1 los 256 valores de byte: nunca falla.


def _sniff_delimiter(sample: bytes, encoding: str, ext: str) -> str:
    """Sniffing de delimitador para `.csv`/`.tsv` (la tarea pide sniffing en ambos).

    La extensión solo decide el delimitador por *default* cuando el sniffer
    no logra inferir uno con confianza (muestra corta/ambigua) — no fuerza
    un delimitador fijo, para no fallar ante un `.tsv` mal nombrado o un
    `.csv` que en realidad usa `;` (común en configuraciones regionales).
    """
    text = sample.decode(encoding, errors="replace")
    default = "\t" if ext == ".tsv" else ","
    try:
        dialect = csv.Sniffer().sniff(text, delimiters=",;\t|")
        return dialect.delimiter
    except csv.Error:
        return default


def _extractor_version() -> str:
    return f"openpyxl@{pkg_version('openpyxl')}+python-calamine@{pkg_version('python-calamine')}"


@dataclass
class _SheetSource:
    name: str
    is_active: bool
    is_hidden: bool
    hidden_column_idxs: set[int]
    rows: list[list[Any]]


class SpreadsheetExtractor:
    """Adapter de `ExtractionPort` para `.xlsx` / `.xls` / `.csv` / `.tsv`."""

    def extract(self, source: ExtractionInput) -> ExtractionResult:
        if source.kind != AttachmentKind.SPREADSHEET:
            raise ValueError(
                "SpreadsheetExtractor solo procesa AttachmentKind.SPREADSHEET, "
                f"recibió {source.kind!r}."
            )
        ext = _extension(source.filename)
        if ext in (".csv", ".tsv"):
            return self._extract_delimited(source, ext)
        return self._extract_workbook(source)

    # -- hojas de cálculo (.xlsx/.xls) --------------------------------------

    def _extract_workbook(self, source: ExtractionInput) -> ExtractionResult:
        raw = _read_all_bytes(source)
        ext = _extension(source.filename)

        workbook = calamine.CalamineWorkbook.from_object(io.BytesIO(raw))
        visibility = {m.name: m.visible for m in workbook.sheets_metadata}
        types = {m.name: m.typ for m in workbook.sheets_metadata}
        worksheet_type = calamine.SheetTypeEnum.WorkSheet
        worksheet_names = [
            name for name in workbook.sheet_names if types.get(name) == worksheet_type
        ]

        openpyxl_wb = None
        if ext == ".xlsx":
            try:
                openpyxl_wb = openpyxl.load_workbook(io.BytesIO(raw), data_only=True)
            except Exception:
                # calamine ya es la lectura primaria y ya tuvo éxito; openpyxl aquí es
                # "best effort" solo para hoja activa/columnas ocultas (ver docstring).
                openpyxl_wb = None

        if openpyxl_wb is not None and openpyxl_wb.active is not None:
            active_name: str | None = openpyxl_wb.active.title
        else:
            active_name = worksheet_names[0] if worksheet_names else None

        sources: list[_SheetSource] = []
        for name in worksheet_names:
            sheet = workbook.get_sheet_by_name(name)
            grid = sheet.to_python(skip_empty_area=False)
            _apply_merges(grid, sheet.merged_cell_ranges or [])

            hidden_cols: set[int] = set()
            if openpyxl_wb is not None and name in openpyxl_wb.sheetnames:
                hidden_cols = _hidden_columns(openpyxl_wb[name])

            is_hidden = visibility.get(name) != calamine.SheetVisibleEnum.Visible
            sources.append(
                _SheetSource(
                    name=name,
                    is_active=(name == active_name),
                    is_hidden=is_hidden,
                    hidden_column_idxs=hidden_cols,
                    rows=grid,
                )
            )

        return self._build_result(source, sources)

    # -- CSV / TSV ------------------------------------------------------------

    def _extract_delimited(self, source: ExtractionInput, ext: str) -> ExtractionResult:
        stream = _open_source_stream(source)
        try:
            sample = stream.read(_SNIFF_SAMPLE_BYTES)
            stream.seek(0)
            encoding = _detect_encoding(sample)
            delimiter = _sniff_delimiter(sample, encoding, ext)
            text_stream = io.TextIOWrapper(stream, encoding=encoding, newline="")
            reader: Iterator[list[Any]] = csv.reader(text_stream, delimiter=delimiter)
            rows = list(reader)
        finally:
            stream.close()

        sheet_name = Path(source.filename).stem or source.filename
        sources = [
            _SheetSource(
                name=sheet_name,
                is_active=True,
                is_hidden=False,
                hidden_column_idxs=set(),
                rows=rows,
            )
        ]
        return self._build_result(source, sources)

    # -- ensamblado compartido -------------------------------------------------

    def _build_result(
        self, source: ExtractionInput, sources: list[_SheetSource]
    ) -> ExtractionResult:
        sheets_meta: list[SheetMetadata] = []
        sections: list[str] = []
        has_marked_hidden = False

        for idx, sheet_source in enumerate(sources):
            scan = _scan_sheet(iter(sheet_source.rows))
            columns = [
                ColumnSchema(
                    header=_header_text(scan.header, col_idx),
                    inferred_type=_majority_type(scan.type_counts[col_idx]),
                    non_empty_count=scan.non_empty_counts[col_idx],
                )
                for col_idx in range(scan.column_count)
            ]
            metadata = SheetMetadata(
                name=sheet_source.name,
                row_count=scan.total_data_rows,
                column_count=scan.column_count,
                is_active=sheet_source.is_active,
                is_hidden=sheet_source.is_hidden,
                columns=columns,
            )
            sheets_meta.append(metadata)

            if sheet_source.is_hidden or sheet_source.hidden_column_idxs:
                has_marked_hidden = True

            section = _render_schema_section(
                sheet_source.name, sheet_source.is_hidden, columns, sheet_source.hidden_column_idxs
            )
            if idx < _MAX_DETAIL_SHEETS:
                section += "\n" + _render_data_section(
                    sheet_source.name,
                    sheet_source.is_hidden,
                    scan.header,
                    scan.column_count,
                    scan.detail_rows,
                    scan.omitted,
                    sheet_source.hidden_column_idxs,
                )
            sections.append(section)

        full_text = _render_inventory(sheets_meta) + "\n" + "\n".join(sections)

        return ExtractionResult(
            kind=source.kind,
            full_text=full_text,
            extractor_version=_extractor_version(),
            has_marked_hidden_content=has_marked_hidden,
            spreadsheet=SpreadsheetStructure(sheets=sheets_meta),
        )
