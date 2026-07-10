"""Tests de presupuesto de tokens y truncado por relevancia UNA VEZ (d14, tarea 6.1).

Cubre los escenarios de `attachments-pipeline` bajo el requirement "Presupuesto de
tokens y truncado por relevancia una sola vez": "DOCX que excede el presupuesto se
trunca consciente de estructura" (títulos conservados, marcadores, % registrado) y la
localización de secciones que usa "pedir otra parte" (tarea 6.2,
`find_section_body`). También cubre las otras dos estrategias del ANEXO §3.2
(esquema-primero para hojas, head+tail genérico/invertido para texto/logs) y el caso
sin truncado (la extracción cabe entera).

Puro: no toca la base de datos ni HTTP -- `truncate_for_insertion` es una función de
`str` a `TruncationResult`. Usa el modelo `gpt-4o-mini` (tokenizer tiktoken conocido de
LiteLLM, determinista y sin red) con presupuestos chicos para forzar el truncado sin
documentos gigantes.
"""

from __future__ import annotations

import re

from resultarai.app.attachments.truncation import find_section_body, truncate_for_insertion
from resultarai.core.ports.extraction import AttachmentKind

_MODEL = "gpt-4o-mini"


def test_extraction_that_fits_is_not_truncated() -> None:
    """Si la extracción cabe entera, `inserted_text` == `full_text` y % es 100."""
    text = "# Título\n\nUn documento chico que entra entero en el presupuesto."
    result = truncate_for_insertion(
        text, kind=AttachmentKind.DOCX, budget_tokens=10_000, user_text="", model=_MODEL
    )
    assert result.text == text
    assert result.truncated is False
    assert result.included_percent == 100
    assert result.token_count > 0


# --- Estrategia 1: consciente de estructura (DOCX/MD/PDF con headings) -----------------


def _structured_docx(relevant_word: str) -> str:
    """Documento con 3 secciones tituladas; una de ellas repite `relevant_word`."""
    filler = " ".join(f"palabraderelleno{n}" for n in range(40))
    return (
        "# Manual de Instrucciones de Trabajo\n\n"
        "Texto introductorio del documento, antes de cualquier título.\n\n"
        "## Sección Alfa\n\n"
        f"Contenido de la sección alfa, sin relación con la consulta. {filler}\n\n"
        "## Sección Beta\n\n"
        f"Esta sección habla específicamente de {relevant_word} {relevant_word} "
        f"{relevant_word}, el tema exacto de la consulta del usuario. {filler}\n\n"
        "## Sección Gamma\n\n"
        f"Otra sección sin relación con la consulta del usuario. {filler}\n"
    )


def test_docx_over_budget_truncates_structure_aware_keeping_titles_and_relevant_section() -> None:
    """Escenario de la spec: DOCX que excede el presupuesto se trunca consciente de
    estructura -- todos los títulos se conservan, la sección más relacionada con el
    texto del usuario sobrevive completa, las demás quedan con el marcador exacto del
    ANEXO §3.2, y `truncated`/`included_percent` quedan registrados.
    """
    full_text = _structured_docx("facturación electrónica")
    user_text = "¿Cómo funciona la facturación electrónica en este proceso?"

    # Presupuesto calibrado (medido empíricamente sobre este documento): alcanza para
    # el esqueleto completo (títulos + preámbulo + marcadores de lo que quede afuera)
    # más la sección "Sección Beta" (la de mayor solapamiento léxico con `user_text`),
    # pero NO alcanza para sumarle además "Sección Alfa" o "Sección Gamma" -- fuerza
    # que se elija exactamente la sección más relevante y se omitan las otras dos.
    budget = 380

    result = truncate_for_insertion(
        full_text,
        kind=AttachmentKind.DOCX,
        budget_tokens=budget,
        user_text=user_text,
        model=_MODEL,
    )

    assert result.truncated is True
    assert 0 < result.included_percent < 100
    assert result.token_count <= budget

    # El "esqueleto" -- TODOS los títulos -- se conserva siempre (ANEXO §3.2 punto 1).
    assert "# Manual de Instrucciones de Trabajo" in result.text
    assert "## Sección Alfa" in result.text
    assert "## Sección Beta" in result.text
    assert "## Sección Gamma" in result.text

    # La sección más relacionada con el texto del usuario sobrevive con su contenido.
    assert "el tema exacto de la consulta del usuario" in result.text

    # Las secciones NO relacionadas quedan con el marcador EXACTO del ANEXO §3.2.
    assert (
        '[… sección "Sección Alfa" omitida por límite de espacio — pedila '
        "explícitamente si la necesitás …]" in result.text
    )
    assert (
        '[… sección "Sección Gamma" omitida por límite de espacio — pedila '
        "explícitamente si la necesitás …]" in result.text
    )


def test_find_section_body_locates_omitted_section_for_fragment_request() -> None:
    """`find_section_body` (soporte de "pedir otra parte", tarea 6.2) localiza por
    título EXACTO -- el mismo que aparece en el marcador de omisión -- sin re-parsear
    nada: opera directamente sobre `full_text`.
    """
    full_text = _structured_docx("facturación electrónica")

    body = find_section_body(full_text, "Sección Alfa")
    assert body is not None
    assert body.startswith("## Sección Alfa")
    assert "Contenido de la sección alfa" in body

    assert find_section_body(full_text, "Sección Inexistente") is None


# --- Estrategia 2: esquema-primero (hojas de cálculo) -----------------------------------


def _spreadsheet_full_text(row_count: int) -> str:
    # El signo de multiplicacion imita el texto literal que emite el extractor real
    # (mismo criterio que `extraction_spreadsheet/adapter.py::_render_inventory`).
    header = "## Inventario de hojas\n\n| Hoja | Filas × Columnas | Activa |\n|---|---|---|\n"  # noqa: RUF001
    header += f"| Hoja1 | {row_count} × 3 | Sí |\n\n"  # noqa: RUF001
    schema = (
        "### Esquema — Hoja1\n\n"
        "| Columna | Tipo | No vacíos |\n|---|---|---|\n"
        f"| Nombre | text | {row_count} |\n"
        f"| Monto | number | {row_count} |\n"
        f"| Fecha | date | {row_count} |\n\n"
    )
    data_lines = [
        "### Datos — Hoja1",
        "",
        "| Nombre | Monto | Fecha |",
        "|---|---|---|",
    ]
    for i in range(row_count):
        data_lines.append(f"| fila_{i} | 100 | 2024-01-01 |")
    return header + schema + "\n".join(data_lines) + "\n"


def test_spreadsheet_over_budget_never_truncates_inventory_or_schema() -> None:
    """Esquema-primero (ANEXO §3.2 punto 2): el inventario y el esquema NUNCA se
    truncan; solo se recortan filas de datos, con marcador y % registrado.
    """
    full_text = _spreadsheet_full_text(row_count=300)
    result = truncate_for_insertion(
        full_text,
        kind=AttachmentKind.SPREADSHEET,
        budget_tokens=400,
        user_text="",
        model=_MODEL,
    )

    assert result.truncated is True
    assert result.token_count <= 400
    # Inventario y esquema COMPLETOS, byte a byte.
    assert "## Inventario de hojas" in result.text
    assert "| Hoja1 | 300 × 3 | Sí |" in result.text  # noqa: RUF001
    assert "### Esquema — Hoja1" in result.text
    assert "| Monto | number | 300 |" in result.text
    # Se omitieron filas de datos, con marcador explícito.
    assert "filas omitidas por límite de espacio" in result.text
    kept_rows = re.findall(r"fila_\d+", result.text)
    assert 0 < len(kept_rows) < 300


# --- Estrategia 3: head+tail genérico (y log invertido) --------------------------------


def _plain_text(prefix: str, n: int) -> str:
    return "\n".join(f"{prefix}_{i} contenido de relleno para la línea {i}" for i in range(n))


def test_generic_text_truncation_biases_toward_head() -> None:
    """Texto plano sin headings: 70% del presupuesto al inicio, 25% al final."""
    text = _plain_text("LINEA", 300)
    result = truncate_for_insertion(
        text, kind=AttachmentKind.TEXT, budget_tokens=200, user_text="", model=_MODEL
    )
    assert result.truncated is True
    assert result.token_count <= 200
    assert "[… contenido omitido por límite de espacio" in result.text

    lines = re.findall(r"LINEA_(\d+)", result.text)
    assert lines, "se esperaba conservar algunas líneas"
    numbers = [int(n) for n in lines]
    # El grueso de lo conservado es del INICIO (bias 70/25): la mayoría de los números
    # conservados son bajos (líneas tempranas), no altos (líneas tardías).
    low = sum(1 for n in numbers if n < 150)
    high = sum(1 for n in numbers if n >= 150)
    assert low > high


def test_log_truncation_biases_toward_tail() -> None:
    """`.log` invierte el sesgo (25% inicio / 70% final, ANEXO §3.2 punto 3): en un log
    el final suele ser lo relevante.
    """
    text = _plain_text("LOG", 300)
    result = truncate_for_insertion(
        text, kind=AttachmentKind.LOG, budget_tokens=200, user_text="", model=_MODEL
    )
    assert result.truncated is True
    assert result.token_count <= 200

    lines = re.findall(r"LOG_(\d+)", result.text)
    assert lines
    numbers = [int(n) for n in lines]
    low = sum(1 for n in numbers if n < 150)
    high = sum(1 for n in numbers if n >= 150)
    assert high > low
