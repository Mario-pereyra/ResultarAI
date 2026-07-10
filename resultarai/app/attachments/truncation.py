"""Presupuesto de tokens y truncado por relevancia, UNA VEZ al insertar (d14, tarea 6.1).

Implementa el paso [7] del pipeline (ANEXO §8) y ANEXO §3.1-§3.2: cuenta tokens de una
extraccion con el tokenizer del proveedor (`adapters/llm_litellm/tokens.py`) y, si supera
el presupuesto, aplica UNA de tres estrategias segun el tipo de adjunto, siempre con
marcadores EXPLICITOS en cada hueco (nunca silencio, P7):

1. **Consciente de estructura** (DOCX/MD/PDF con headings `#`-`######`): conserva TODOS
   los titulos (el "esqueleto") + las secciones con mayor solapamiento lexico con el
   texto que el usuario escribio en ese mensaje; cada seccion omitida deja el marcador
   exacto del ANEXO §3.2 (`[… sección "X" omitida por límite de espacio…]`).
2. **Esquema-primero** (`AttachmentKind.SPREADSHEET`): nunca toca el inventario ni el
   esquema (se identifican por las secciones `### Datos — …` que emite
   `adapters/extraction_spreadsheet/adapter.py`: todo lo que NO esta dentro de una de
   esas secciones es intocable); solo recorta filas de datos, con sesgo hacia el inicio
   (mismo criterio "head+tail" que el propio extractor usa para su tope de 200 filas).
3. **Head+tail generico** (todo lo demas: TXT/codigo/PDF sin headings): 70% del
   presupuesto al inicio + 25% al final, marcador en el medio; para `.log`
   (`AttachmentKind.LOG`) se invierte a 25%/70% porque en un log el final suele ser lo
   relevante (ANEXO §3.2 punto 3).

Este modulo es PURO respecto de la base de datos (no importa SQLAlchemy ni modelos):
recibe `full_text` como `str` y devuelve `TruncationResult`. Quien la invoca al componer
el mensaje (`app/use_cases/chat/_attachments.py`, tarea 6.3) es quien decide CUANDO correr
esto (una sola vez, al insertar por primera vez un adjunto en un mensaje) y persiste el
resultado en `message_attachments` (`inserted_text`/`token_count`/`truncated`). Esta
funcion NUNCA debe volver a correr sobre una extraccion ya insertada (P4: re-truncar
reescribiria historia) -- esa garantia la sostiene el llamador, no este modulo.

`find_section_body` (usado por la operacion "pedir otra parte", tarea 6.2) reutiliza el
mismo particionado en secciones que la estrategia consciente de estructura, para que
"la seccion que se omitio" sea localizable por su titulo EXACTO sin re-parsear nada.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from resultarai.adapters.llm_litellm.tokens import count_tokens
from resultarai.core.ports.extraction import AttachmentKind

__all__ = [
    "TruncationResult",
    "find_section_body",
    "truncate_for_insertion",
    "truncate_fragment",
]

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_DATA_SECTION_RE = re.compile(r"^### Datos — (.+)$")
_SECTION_BOUNDARY_RE = re.compile(r"^#{2,3}\s")

# Palabras vacias ES/EN de alta frecuencia: se excluyen del solapamiento lexico para que
# el ranking de relevancia no se decida por "que"/"con"/"the" (ANEXO §3.2 punto 1).
_STOPWORDS = frozenset(
    {
        "de",
        "la",
        "el",
        "en",
        "un",
        "una",
        "que",
        "con",
        "para",
        "los",
        "las",
        "del",
        "por",
        "se",
        "su",
        "sus",
        "es",
        "al",
        "lo",
        "como",
        "más",
        "pero",
        "sin",
        "sobre",
        "entre",
        "esta",
        "este",
        "esto",
        "esos",
        "esas",
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "from",
        "are",
        "was",
        "were",
        "has",
        "have",
        "not",
    }
)
_MIN_WORD_LEN = 4
_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)

_GENERIC_MARKER = (
    "\n\n[… contenido omitido por límite de espacio — pedilo explícitamente si lo necesitás …]\n\n"
)


@dataclass(frozen=True)
class TruncationResult:
    """Resultado del truncado por relevancia: texto final + metadatos (ANEXO §3.1-§3.2).

    `included_percent` es el % de TOKENS incluidos respecto del total de la extraccion
    original (redondeado, 0-100) -- la magnitud que muestra la vista previa (ANEXO §3.4).
    """

    text: str
    token_count: int
    truncated: bool
    included_percent: int


def truncate_for_insertion(
    full_text: str,
    *,
    kind: AttachmentKind,
    budget_tokens: int,
    user_text: str,
    model: str,
) -> TruncationResult:
    """Cuenta tokens de `full_text` y trunca por relevancia si excede `budget_tokens`.

    Si la extraccion cabe entera, `text` == `full_text` y `truncated=False` con
    `included_percent=100` (ANEXO §3.1: "si la extraccion cabe entera, inserted_text =
    full_text"). `model` es el `ModelProfile.model` de LiteLLM (ver
    `insertion.py::resolve_token_counter_model`), NUNCA el `id` del perfil.
    """
    total_tokens = count_tokens(full_text, model=model)
    if total_tokens <= budget_tokens:
        return TruncationResult(full_text, total_tokens, False, 100)

    if kind is AttachmentKind.SPREADSHEET:
        return _truncate_schema_first(full_text, budget_tokens, model, total_tokens)
    if kind is AttachmentKind.LOG:
        return _truncate_head_tail(
            full_text, budget_tokens, model, total_tokens, head_ratio=0.25, tail_ratio=0.70
        )
    if _has_headings(full_text):
        return _truncate_structure_aware(full_text, budget_tokens, user_text, model, total_tokens)
    return _truncate_head_tail(
        full_text, budget_tokens, model, total_tokens, head_ratio=0.70, tail_ratio=0.25
    )


def truncate_fragment(text: str, *, budget_tokens: int, model: str) -> TruncationResult:
    """Trunca un fragmento YA ELEGIDO explícitamente (tarea 6.2, "pedir otra parte").

    Usa SIEMPRE head+tail genérico (70/25), nunca consciente-de-estructura: `text` es
    el cuerpo de UNA seccion que el usuario ya pidió por título (`find_section_body`),
    así que no tiene sentido volver a decidir "qué sección incluir" dentro de ella
    misma -- si se aplicara `truncate_for_insertion` con su heading propio, un
    fragmento que por sí solo excede el presupuesto terminaría enteramente detrás de
    su propio marcador de omisión (auto-omitiéndose), en vez de mostrar una porción
    útil (P7: nunca fallar en silencio). Si `text` cabe entero, se devuelve intacto.
    """
    total_tokens = count_tokens(text, model=model)
    if total_tokens <= budget_tokens:
        return TruncationResult(text, total_tokens, False, 100)
    return _truncate_head_tail(
        text, budget_tokens, model, total_tokens, head_ratio=0.70, tail_ratio=0.25
    )


# ---------------------------------------------------------------------------------------
# Estrategia 1: consciente de estructura (DOCX/MD/PDF con headings)
# ---------------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Section:
    """Una seccion del documento: `heading_line` es `None` para el preambulo (antes del
    primer heading), que siempre viaja completo (parte del "esqueleto").
    """

    heading_line: str | None
    title: str
    body: str


def _has_headings(text: str) -> bool:
    return any(_HEADING_RE.match(line) is not None for line in text.split("\n"))


def _split_sections(text: str) -> list[_Section]:
    lines = text.split("\n")
    sections: list[_Section] = []
    heading_line: str | None = None
    title = ""
    body_lines: list[str] = []
    for line in lines:
        match = _HEADING_RE.match(line)
        if match is not None:
            sections.append(_Section(heading_line, title, "\n".join(body_lines)))
            heading_line = line
            title = match.group(2).strip()
            body_lines = []
        else:
            body_lines.append(line)
    sections.append(_Section(heading_line, title, "\n".join(body_lines)))
    return sections


def _significant_words(text: str) -> set[str]:
    words = _WORD_RE.findall(text.lower())
    return {w for w in words if len(w) >= _MIN_WORD_LEN and w not in _STOPWORDS}


def _relevance_score(body: str, keywords: set[str]) -> int:
    if not keywords:
        return 0
    words = _WORD_RE.findall(body.lower())
    return sum(1 for w in words if w in keywords)


def _omission_marker(title: str) -> str:
    return (
        f'[… sección "{title}" omitida por límite de espacio — pedila explícitamente '
        "si la necesitás …]"
    )


def _render_sections(sections: list[_Section], included: set[int]) -> str:
    parts: list[str] = []
    for idx, section in enumerate(sections):
        if section.heading_line is not None:
            parts.append(section.heading_line)
        if section.heading_line is None or idx in included:
            if section.body:
                parts.append(section.body)
        else:
            parts.append(_omission_marker(section.title))
    return "\n".join(parts)


def _truncate_structure_aware(
    full_text: str, budget_tokens: int, user_text: str, model: str, total_tokens: int
) -> TruncationResult:
    sections = _split_sections(full_text)
    keywords = _significant_words(user_text)

    # El preambulo (sin heading) y el esqueleto de titulos siempre estan incluidos; solo
    # se rankean y greedy-incluyen los CUERPOS de las secciones con heading.
    headed_indexes = [i for i, s in enumerate(sections) if s.heading_line is not None]
    ranked = sorted(headed_indexes, key=lambda i: -_relevance_score(sections[i].body, keywords))

    included: set[int] = {i for i, s in enumerate(sections) if s.heading_line is None}
    best_text = _render_sections(sections, included)
    best_tokens = count_tokens(best_text, model=model)

    for idx in ranked:
        trial_included = included | {idx}
        trial_text = _render_sections(sections, trial_included)
        trial_tokens = count_tokens(trial_text, model=model)
        if trial_tokens <= budget_tokens:
            included = trial_included
            best_text = trial_text
            best_tokens = trial_tokens

    included_percent = _percent(best_tokens, total_tokens)
    return TruncationResult(best_text, best_tokens, True, included_percent)


def find_section_body(full_text: str, title: str) -> str | None:
    """Devuelve el heading + cuerpo COMPLETO (sin truncar) de la seccion `title`.

    Uso: operacion "pedir otra parte" (tarea 6.2) -- corta un fragmento NUEVO del
    `full_text` YA ALMACENADO (sin re-parsear el binario ni tocar ninguna insercion
    previa). `title` se compara EXACTO contra el texto que aparece en el marcador de
    omision de `_omission_marker` (mismo titulo que el usuario ve en el mensaje
    truncado), asi que "pedir la seccion omitida" es un lookup directo. `None` si no
    hay ninguna seccion con ese titulo.
    """
    for section in _split_sections(full_text):
        if section.heading_line is not None and section.title == title:
            body = section.body.strip("\n")
            return f"{section.heading_line}\n{body}" if body else section.heading_line
    return None


# ---------------------------------------------------------------------------------------
# Estrategia 2: esquema-primero (hojas de calculo)
# ---------------------------------------------------------------------------------------


@dataclass(frozen=True)
class _RowBlock:
    """Rango de lineas `[start, end)` de una seccion `### Datos — X` dentro del texto.

    `protected_end` protege el heading + hasta 2 lineas de preambulo (encabezado de
    tabla Markdown + delimitador, o la apertura ```tsv``` + su encabezado). `suffix_start`
    protege el cierre ``` de un bloque TSV si lo hay. Solo `[protected_end, suffix_start)`
    es recortable (filas de datos).
    """

    start: int
    protected_end: int
    suffix_start: int
    end: int


def _find_data_row_blocks(lines: list[str]) -> list[_RowBlock]:
    blocks: list[_RowBlock] = []
    i = 0
    n = len(lines)
    while i < n:
        if _DATA_SECTION_RE.match(lines[i]) is not None:
            start = i
            j = i + 1
            while j < n and _SECTION_BOUNDARY_RE.match(lines[j]) is None:
                j += 1
            protected_end = min(start + 3, j)
            suffix_start = j
            if j > protected_end and lines[j - 1].strip() == "```":
                suffix_start = j - 1
            blocks.append(_RowBlock(start, protected_end, suffix_start, j))
            i = j
        else:
            i += 1
    return blocks


def _head_tail_rows(rows: list[str], keep_fraction: float) -> list[str]:
    if keep_fraction >= 1.0 or not rows:
        return rows
    keep_count = max(0, round(len(rows) * keep_fraction))
    if keep_count >= len(rows):
        return rows
    head_count = round(keep_count * 0.88)
    tail_count = keep_count - head_count
    omitted = len(rows) - head_count - tail_count
    marker = [f"… ({omitted} filas omitidas por límite de espacio) …"] if omitted > 0 else []
    head = rows[:head_count] if head_count else []
    tail = rows[len(rows) - tail_count :] if tail_count else []
    return head + marker + tail


def _render_with_fraction(lines: list[str], blocks: list[_RowBlock], fraction: float) -> str:
    out: list[str] = []
    cursor = 0
    for block in blocks:
        out.extend(lines[cursor : block.protected_end])
        row_lines = lines[block.protected_end : block.suffix_start]
        out.extend(_head_tail_rows(row_lines, fraction))
        out.extend(lines[block.suffix_start : block.end])
        cursor = block.end
    out.extend(lines[cursor:])
    return "\n".join(out)


_SCHEMA_FIRST_SEARCH_ITERATIONS = 12


def _truncate_schema_first(
    full_text: str, budget_tokens: int, model: str, total_tokens: int
) -> TruncationResult:
    lines = full_text.split("\n")
    blocks = _find_data_row_blocks(lines)
    if not blocks:
        # Sin seccion de datos identificable (hoja vacia o formato atipico): no hay
        # inventario/esquema que proteger de forma especifica -- cae al head+tail
        # generico con sesgo fuerte al inicio, ultimo recurso documentado.
        return _truncate_head_tail(
            full_text, budget_tokens, model, total_tokens, head_ratio=0.88, tail_ratio=0.12
        )

    low, high = 0.0, 1.0
    best_text = full_text
    best_tokens = total_tokens
    for _ in range(_SCHEMA_FIRST_SEARCH_ITERATIONS):
        mid = (low + high) / 2
        candidate = _render_with_fraction(lines, blocks, mid)
        candidate_tokens = count_tokens(candidate, model=model)
        if candidate_tokens <= budget_tokens:
            low = mid
            best_text = candidate
            best_tokens = candidate_tokens
        else:
            high = mid

    if best_tokens > budget_tokens:
        # El inventario/esquema por si solos ya exceden el presupuesto (documento
        # degenerado, muchas hojas/columnas): se acepta el exceso antes que truncar lo
        # protegido (ANEXO §3.2 punto 2: "nunca truncar el inventario ni el esquema").
        best_text = _render_with_fraction(lines, blocks, 0.0)
        best_tokens = count_tokens(best_text, model=model)

    included_percent = _percent(best_tokens, total_tokens)
    return TruncationResult(best_text, best_tokens, True, included_percent)


# ---------------------------------------------------------------------------------------
# Estrategia 3: head+tail generico (y log invertido)
# ---------------------------------------------------------------------------------------


# Ventana (en caracteres) dentro de la cual vale la pena alinear un corte a un salto de
# linea completo: si el salto mas cercano queda MAS ALLA de esta ventana, alinearse a el
# descartaria la mayor parte del contenido (texto esencialmente un parrafo largo sin
# saltos de linea internos, p. ej. el cuerpo de una sola seccion "pedida" por
# `truncate_fragment`) -- preferible un corte a mitad de linea que perder casi todo.
_LINE_SNAP_WINDOW_CHARS = 200


def _take_tokens_from_start(text: str, budget: int, model: str) -> str:
    if budget <= 0 or not text:
        return ""
    if count_tokens(text, model=model) <= budget:
        return text
    low, high = 0, len(text)
    while low < high:
        mid = (low + high + 1) // 2
        if count_tokens(text[:mid], model=model) <= budget:
            low = mid
        else:
            high = mid - 1
    cut = text[:low]
    last_newline = cut.rfind("\n")
    if last_newline > 0 and last_newline >= len(cut) - _LINE_SNAP_WINDOW_CHARS:
        cut = cut[:last_newline]
    return cut


def _take_tokens_from_end(text: str, budget: int, model: str) -> str:
    if budget <= 0 or not text:
        return ""
    if count_tokens(text, model=model) <= budget:
        return text
    low, high = 0, len(text)
    while low < high:
        mid = (low + high + 1) // 2
        if count_tokens(text[-mid:], model=model) <= budget:
            low = mid
        else:
            high = mid - 1
    cut = text[-low:] if low > 0 else ""
    first_newline = cut.find("\n")
    if 0 <= first_newline < min(len(cut) - 1, _LINE_SNAP_WINDOW_CHARS):
        cut = cut[first_newline + 1 :]
    return cut


def _truncate_head_tail(
    full_text: str,
    budget_tokens: int,
    model: str,
    total_tokens: int,
    *,
    head_ratio: float,
    tail_ratio: float,
) -> TruncationResult:
    marker_tokens = count_tokens(_GENERIC_MARKER, model=model)
    available = max(budget_tokens - marker_tokens, 0)
    head_budget = int(available * head_ratio)
    tail_budget = available - head_budget

    head_text = _take_tokens_from_start(full_text, head_budget, model)
    tail_text = _take_tokens_from_end(full_text, tail_budget, model)
    combined = head_text + _GENERIC_MARKER + tail_text
    combined_tokens = count_tokens(combined, model=model)

    included_percent = _percent(combined_tokens, total_tokens)
    return TruncationResult(combined, combined_tokens, True, included_percent)


def _percent(part_tokens: int, total_tokens: int) -> int:
    if total_tokens <= 0:
        return 100
    return max(0, min(100, round(part_tokens / total_tokens * 100)))
