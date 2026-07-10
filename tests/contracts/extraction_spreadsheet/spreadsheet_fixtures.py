"""Constructores de hojas de cálculo mínimas para los contract tests de
`extraction_spreadsheet`. Todo se genera en memoria con `openpyxl` (no se
versionan binarios de fixture).
"""

from __future__ import annotations

import io
from datetime import date

from openpyxl import Workbook
from openpyxl.worksheet.worksheet import Worksheet


def _active_sheet(wb: Workbook) -> Worksheet:
    """`Workbook.active` recién creado siempre trae una hoja; se lo tipa sin `| None`."""
    ws = wb.active
    assert ws is not None
    return ws


def build_workbook_with_row_overflow(row_count: int = 500) -> bytes:
    """Una sola hoja con encabezado + `row_count` filas de datos (> 200)."""
    wb = Workbook()
    ws = _active_sheet(wb)
    ws.title = "Movimientos"
    ws.append(["Fecha", "Monto", "Descripcion"])
    for i in range(1, row_count + 1):
        ws.append([date(2026, 1, 1), i * 1.5, f"Registro {i}"])
    return _to_bytes(wb)


def build_workbook_with_hidden_sheet_and_column() -> bytes:
    """Dos hojas: "Ventas" (activa, con una columna oculta) y "Detalle" (hoja oculta)."""
    wb = Workbook()
    ws_ventas = _active_sheet(wb)
    ws_ventas.title = "Ventas"
    ws_ventas.append(["Producto", "Costo interno", "Precio"])
    ws_ventas.append(["Notebook", 850.0, 1200.0])
    ws_ventas.append(["Monitor", 300.0, 450.0])
    ws_ventas.column_dimensions["B"].hidden = True  # "Costo interno" oculta

    ws_detalle = wb.create_sheet("Detalle")
    ws_detalle.append(["Nota"])
    ws_detalle.append(["Solo para auditoría interna"])
    ws_detalle.sheet_state = "hidden"

    wb.active = wb.sheetnames.index("Ventas")
    return _to_bytes(wb)


def build_workbook_with_second_sheet_active() -> bytes:
    """Dos hojas visibles; la hoja activa NO es la primera del archivo."""
    wb = Workbook()
    ws1 = _active_sheet(wb)
    ws1.title = "Enero"
    ws1.append(["Dia", "Ventas"])
    ws1.append([1, 100])

    ws2 = wb.create_sheet("Febrero")
    ws2.append(["Dia", "Ventas"])
    ws2.append([1, 200])

    wb.active = wb.sheetnames.index("Febrero")
    return _to_bytes(wb)


def build_workbook_with_merged_cells() -> bytes:
    """Encabezado limpio + una fila de datos con una celda combinada (2 columnas)."""
    wb = Workbook()
    ws = _active_sheet(wb)
    ws.title = "Combinadas"
    ws.append(["Región", "Sucursal", "Total"])
    ws.append(["Santa Cruz", "Equipetrol", 1000])
    ws.append(["Santa Cruz", "Norte", 500])
    ws.merge_cells("A2:A3")  # "Santa Cruz" abarca las dos filas de datos
    return _to_bytes(wb)


def build_workbook_with_formula() -> bytes:
    """Encabezado + fila con una celda de fórmula (sin valor cacheado real)."""
    wb = Workbook()
    ws = _active_sheet(wb)
    ws.title = "Calculo"
    ws.append(["A", "B", "Total"])
    ws.append([2, 3, "=A2+B2"])
    return _to_bytes(wb)


def build_wide_workbook(column_count: int = 35) -> bytes:
    """Hoja con más de 30 columnas -> el detalle se renderiza como TSV, no Markdown."""
    wb = Workbook()
    ws = _active_sheet(wb)
    ws.title = "Ancha"
    header = [f"Col{i}" for i in range(column_count)]
    ws.append(header)
    ws.append(list(range(column_count)))
    return _to_bytes(wb)


def build_empty_sheet_workbook() -> bytes:
    """Una hoja completamente vacía (sin encabezado ni datos)."""
    wb = Workbook()
    ws = _active_sheet(wb)
    ws.title = "Vacia"
    return _to_bytes(wb)


def build_csv_bytes(row_count: int = 5, delimiter: str = ",") -> bytes:
    lines = [delimiter.join(["id", "nombre", "monto"])]
    for i in range(1, row_count + 1):
        lines.append(delimiter.join([str(i), f"item {i}", f"{i * 1.1:.2f}"]))
    return ("\n".join(lines) + "\n").encode("utf-8")


def build_large_csv_bytes(row_count: int = 500) -> bytes:
    return build_csv_bytes(row_count=row_count, delimiter=",")


def build_semicolon_csv_bytes(row_count: int = 3) -> bytes:
    return build_csv_bytes(row_count=row_count, delimiter=";")


def build_tsv_bytes_with_commas_in_data() -> bytes:
    """TSV real (separado por tabs) cuyos datos contienen comas embebidas.

    Sirve para comprobar que el sniffing de delimitador no confunde las comas
    del contenido con el separador real cuando la extensión es `.tsv`.
    """
    lines = [
        "id\tnombre\tmonto",
        "1\tPerez, Juan\t100.00",
        "2\tGomez, Ana\t250.50",
    ]
    return ("\n".join(lines) + "\n").encode("utf-8")


def build_windows_1252_csv_bytes() -> bytes:
    """CSV con encoding Windows-1252 (acentos/ñ como bytes reales, no UTF-8)."""
    lines = ["id;descripcion", "1;Facturación región Cochabamba", "2;Créditos año 2026"]
    return ("\n".join(lines) + "\n").encode("cp1252")


def _to_bytes(wb: Workbook) -> bytes:
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
