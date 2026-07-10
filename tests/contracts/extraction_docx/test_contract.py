"""Contract tests del adapter `extraction_docx` (DocxExtractor / ExtractionPort)."""

from __future__ import annotations

from importlib.metadata import version as _package_version
from pathlib import Path

import pytest

from resultarai.adapters.extraction_docx import DocxExtractor
from resultarai.adapters.extraction_docx.html_to_markdown import html_to_markdown
from resultarai.core.ports.extraction import AttachmentKind, ExtractionInput, ExtractionPort
from tests.contracts.extraction_docx.docx_fixtures import (
    build_docx_with_headings_table_and_image,
)


def test_docx_extractor_satisfies_extraction_port_protocol() -> None:
    """Asignación tipada: DocxExtractor cumple el Protocol ExtractionPort."""
    port: ExtractionPort = DocxExtractor()
    assert isinstance(port, DocxExtractor)


def test_extract_docx_with_headings_table_and_image() -> None:
    """Escenario: DOCX con encabezados, tabla e imagen -- Markdown estructurado."""
    docx_bytes = build_docx_with_headings_table_and_image()

    result = DocxExtractor().extract(
        ExtractionInput(kind=AttachmentKind.DOCX, filename="informe.docx", content=docx_bytes)
    )

    assert result.kind is AttachmentKind.DOCX
    # Encabezados preservados como Markdown, con jerarquía h1/h2.
    assert "# 1. Titulo Principal" in result.full_text
    assert "## 1.1 Subtitulo" in result.full_text
    assert "Parrafo normal introductorio." in result.full_text
    # La tabla Word real se preserva como tabla Markdown (fila de encabezado +
    # separador + fila de datos), no como parrafos sueltos.
    assert "| Columna A | Columna B |" in result.full_text
    assert "| --- | --- |" in result.full_text
    assert "| dato1 | dato2 |" in result.full_text
    # La imagen embebida nunca llega como data URI: queda marcada y omitida.
    assert "[imagen omitida: Diagrama de flujo]" in result.full_text
    assert "data:image" not in result.full_text
    assert "base64" not in result.full_text
    # El encabezado principal precede a la tabla, que precede al marcador de imagen.
    assert result.full_text.index("# 1. Titulo Principal") < result.full_text.index(
        "| Columna A | Columna B |"
    )
    assert result.full_text.index("| dato1 | dato2 |") < result.full_text.index("[imagen omitida:")


def test_extract_docx_image_without_alt_text_gets_generated_name() -> None:
    """Sin alt text de Word, el marcador usa un nombre generado a partir del tipo de imagen."""
    docx_bytes = build_docx_with_headings_table_and_image(image_alt_text="")

    result = DocxExtractor().extract(
        ExtractionInput(kind=AttachmentKind.DOCX, filename="sin_alt.docx", content=docx_bytes)
    )

    assert "[imagen omitida: imagen_1.png]" in result.full_text


def test_extract_rejects_wrong_attachment_kind() -> None:
    """El adapter solo procesa AttachmentKind.DOCX."""
    with pytest.raises(ValueError, match=r"AttachmentKind\.DOCX"):
        DocxExtractor().extract(
            ExtractionInput(kind=AttachmentKind.TEXT, filename="nota.txt", content=b"hola")
        )


def test_extractor_version_reports_installed_mammoth_version() -> None:
    """`extractor_version` usa la version real instalada de mammoth (importlib.metadata)."""
    docx_bytes = build_docx_with_headings_table_and_image()

    result = DocxExtractor().extract(
        ExtractionInput(kind=AttachmentKind.DOCX, filename="uno.docx", content=docx_bytes)
    )

    assert result.extractor_version == f"mammoth@{_package_version('mammoth')}"


def test_extract_reads_from_source_path(tmp_path: Path) -> None:
    """El adapter tambien acepta la entrada via `source_path` (worker aislado)."""
    docx_bytes = build_docx_with_headings_table_and_image(heading1="Titulo en disco")
    docx_path = tmp_path / "adjunto.docx"
    docx_path.write_bytes(docx_bytes)

    result = DocxExtractor().extract(
        ExtractionInput(
            kind=AttachmentKind.DOCX, filename="adjunto.docx", source_path=str(docx_path)
        )
    )

    assert "Titulo en disco" in result.full_text


def test_html_to_markdown_preserves_nested_lists() -> None:
    """El conversor propio HTML->Markdown entiende listas anidadas ol/ul."""
    html = (
        "<h1>Titulo</h1>"
        "<ul><li>Uno</li><li>Dos<ul><li>Anidado</li></ul></li></ul>"
        "<ol><li>Primero</li><li>Segundo</li></ol>"
    )

    markdown = html_to_markdown(html)

    assert "# Titulo" in markdown
    assert "- Uno" in markdown
    assert "- Dos" in markdown
    assert "  - Anidado" in markdown
    assert "1. Primero" in markdown
    assert "2. Segundo" in markdown


def test_html_to_markdown_escapes_pipe_characters_in_table_cells() -> None:
    """Un `|` dentro de una celda no debe romper la sintaxis de tabla Markdown."""
    html = "<table><tr><td>a|b</td><td>c</td></tr></table>"

    markdown = html_to_markdown(html)

    assert "a\\|b" in markdown
