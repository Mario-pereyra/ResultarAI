"""Conversor mínimo de HTML a Markdown, stdlib-only.

Existe porque `mammoth.convert_to_markdown()` (el modo Markdown integrado del
puerto Python de mammoth) no traduce tablas: su escritor Markdown
(`mammoth/writers/markdown.py`) no tiene handler para `table`/`tr`/`td`/`th`,
así que una tabla Word real se aplana a párrafos sueltos, uno por celda, sin
ninguna estructura de filas/columnas. `mammoth.convert_to_html()`, en cambio,
sí preserva `<table><tr><td>...` intacto (verificado empíricamente). Este
módulo toma esa salida HTML (siempre bien formada porque la genera mammoth,
nunca HTML arbitrario de la web) y la convierte a Markdown, cubriendo
exactamente lo que el pipeline de adjuntos necesita: encabezados, listas,
tablas y párrafos. Todo lo demás (spans, enlaces, negrita/cursiva, anclas de
mammoth) se trata como contenedor transparente y solo aporta su texto.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser

__all__ = ["html_to_markdown"]

_HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
_LIST_TAGS = {"ul", "ol"}
_WHITESPACE_RE = re.compile(r"\s+")


@dataclass
class _Node:
    """Nodo mínimo de árbol HTML: nombre de tag + hijos (texto u otro nodo)."""

    tag: str
    children: list[_Node | str] = field(default_factory=list)


class _TreeBuilder(HTMLParser):
    """Arma un árbol mínimo a partir del HTML plano que emite mammoth."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _Node(tag="root")
        self._stack: list[_Node] = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = _Node(tag=tag)
        self._stack[-1].children.append(node)
        self._stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self._stack) - 1, 0, -1):
            if self._stack[index].tag == tag:
                del self._stack[index:]
                return

    def handle_data(self, data: str) -> None:
        if data:
            self._stack[-1].children.append(data)


def html_to_markdown(html_fragment: str) -> str:
    """Convierte HTML estructurado (salida de `mammoth.convert_to_html`) a Markdown."""
    builder = _TreeBuilder()
    builder.feed(html_fragment)
    builder.close()
    return _render_nodes(builder.root.children).strip()


def _render_nodes(nodes: list[_Node | str]) -> str:
    return "".join(_render_node(node) for node in nodes)


def _render_node(node: _Node | str) -> str:
    if isinstance(node, str):
        return _collapse_whitespace(node)

    if node.tag in _HEADING_TAGS:
        level = int(node.tag[1])
        text = _inline_text(node.children)
        return f"{'#' * level} {text}\n\n" if text else ""

    if node.tag == "p":
        text = _inline_text(node.children)
        return f"{text}\n\n" if text else ""

    if node.tag in _LIST_TAGS:
        return _render_list(node, depth=0) + "\n"

    if node.tag == "table":
        return _render_table(node) + "\n"

    if node.tag == "br":
        return "  \n"

    # Contenedores transparentes: span, a, strong, em, root, anclas de mammoth,
    # thead/tbody/tr/td/th sueltos fuera de <table> -- solo interesa su texto.
    return _render_nodes(node.children)


def _inline_text(nodes: list[_Node | str]) -> str:
    return _render_nodes(nodes).replace("\n", " ").strip()


def _collapse_whitespace(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text)


def _render_list(node: _Node, depth: int) -> str:
    ordered = node.tag == "ol"
    indent = "  " * depth
    lines: list[str] = []
    counter = 0
    for item in node.children:
        if not isinstance(item, _Node) or item.tag != "li":
            continue
        counter += 1
        bullet = f"{counter}." if ordered else "-"
        inline_children = [
            child
            for child in item.children
            if not (isinstance(child, _Node) and child.tag in _LIST_TAGS)
        ]
        nested_lists = [
            child for child in item.children if isinstance(child, _Node) and child.tag in _LIST_TAGS
        ]
        item_text = _inline_text(inline_children)
        lines.append(f"{indent}{bullet} {item_text}")
        for nested in nested_lists:
            lines.append(_render_list(nested, depth + 1).rstrip("\n"))
    return "\n".join(lines) + "\n"


def _render_table(node: _Node) -> str:
    rows: list[list[str]] = []
    header_row_index: int | None = None

    def visit(container: _Node, in_thead: bool) -> None:
        nonlocal header_row_index
        for child in container.children:
            if not isinstance(child, _Node):
                continue
            if child.tag == "thead":
                visit(child, True)
            elif child.tag == "tbody":
                visit(child, False)
            elif child.tag == "tr":
                is_header_row = in_thead
                cells: list[str] = []
                for cell in child.children:
                    if isinstance(cell, _Node) and cell.tag in {"td", "th"}:
                        if cell.tag == "th":
                            is_header_row = True
                        cells.append(_inline_text(cell.children).replace("|", "\\|"))
                if cells:
                    rows.append(cells)
                    if is_header_row and header_row_index is None:
                        header_row_index = len(rows) - 1

    visit(node, False)
    if not rows:
        return ""

    column_count = max(len(row) for row in rows)

    def pad(row: list[str]) -> list[str]:
        return [*row, *([""] * (column_count - len(row)))]

    header_index = header_row_index if header_row_index is not None else 0
    header = pad(rows[header_index])
    body_rows = [pad(row) for index, row in enumerate(rows) if index != header_index]

    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---"] * column_count) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in body_rows)
    return "\n".join(lines) + "\n"
