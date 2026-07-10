"""Contract tests del adapter `extraction_text` (TextExtractor / ExtractionPort)."""

from __future__ import annotations

from pathlib import Path

import pytest

from resultarai.adapters.extraction_text import TextExtractor
from resultarai.core.ports.extraction import AttachmentKind, ExtractionInput, ExtractionPort


def test_text_extractor_satisfies_extraction_port_protocol() -> None:
    """Asignación tipada: TextExtractor cumple el Protocol ExtractionPort."""
    port: ExtractionPort = TextExtractor()
    assert isinstance(port, TextExtractor)


def test_extract_utf8_txt_wraps_in_text_fence() -> None:
    """.txt en UTF-8: se envuelve en fence explícito ```text y se detecta el encoding."""
    content = "Nota de prueba con acentuación: café, niño.".encode()

    result = TextExtractor().extract(
        ExtractionInput(kind=AttachmentKind.TEXT, filename="nota.txt", content=content)
    )

    assert result.kind is AttachmentKind.TEXT
    assert result.text is not None
    assert result.text.source_encoding == "utf-8"
    assert result.text.code_fence_language == "text"
    assert result.full_text.startswith("```text\n")
    assert result.full_text.rstrip().endswith("```")
    assert "café, niño" in result.full_text


def test_extract_log_windows_1252_normalizes_to_utf8_and_fences_as_log() -> None:
    """Escenario spec: log en Windows-1252 se normaliza a UTF-8 y se envuelve en ```log.

    El truncado tail-first es responsabilidad de la etapa de presupuesto (6.1);
    este adapter siempre entrega el `full_text` completo, sin truncar.
    """
    original_text = (
        "10:00:01 ERRO Falha ao gravar registro: código inválido "
        "para o município de São Paulo — sessão encerrada.\n"
        "10:00:02 INFO Reintentando operación número 2, así continúa."
    )
    # bytes reales en Windows-1252 (no simplemente el texto re-codificado a ASCII)
    raw_bytes = original_text.encode("cp1252")
    assert b"\xf3" in raw_bytes or b"\xe3" in raw_bytes  # confirma que hay bytes altos reales

    result = TextExtractor().extract(
        ExtractionInput(kind=AttachmentKind.LOG, filename="protheus.log", content=raw_bytes)
    )

    assert result.kind is AttachmentKind.LOG
    assert result.text is not None
    assert result.text.source_encoding == "cp1252"
    assert result.text.code_fence_language == "log"
    assert result.full_text.startswith("```log\n")
    # El contenido decodificado aparece completo, íntegro y en UTF-8 (str nativo de Python).
    assert "código inválido" in result.full_text
    assert "São Paulo" in result.full_text
    assert "sessão encerrada" in result.full_text
    assert original_text in result.full_text  # full_text completo: nada truncado por este adapter


def test_extract_normalizes_crlf_and_lone_cr_to_lf() -> None:
    """Saltos de línea CRLF y CR sueltos se normalizan a LF."""
    content = b"linea1\r\nlinea2\rlinea3\n"

    result = TextExtractor().extract(
        ExtractionInput(kind=AttachmentKind.TEXT, filename="mixto.txt", content=content)
    )

    inner = result.full_text.removeprefix("```text\n").rstrip("`\n")
    assert "\r" not in inner
    assert "linea1\nlinea2\nlinea3" in inner


@pytest.mark.parametrize(
    ("filename", "expected_language"),
    [
        ("rotina.prw", "advpl"),
        ("rotina.prx", "advpl"),
        ("rotina.tlpp", "advpl"),
        ("consulta.sql", "sql"),
        ("salida.log", "log"),
        ("config.json", "json"),
        ("datos.xml", "xml"),
        ("pipeline.yml", "yaml"),
        ("pipeline.yaml", "yaml"),
        ("ajustes.ini", "ini"),
        ("notas.txt", "text"),
    ],
)
def test_code_fence_language_by_extension(filename: str, expected_language: str) -> None:
    """El lenguaje del bloque de código se infiere de la extensión (ANEXO §2.5)."""
    kind = AttachmentKind.LOG if filename.endswith(".log") else AttachmentKind.CODE
    if filename.endswith(".txt"):
        kind = AttachmentKind.TEXT

    result = TextExtractor().extract(
        ExtractionInput(kind=kind, filename=filename, content=b"contenido")
    )

    assert result.text is not None
    assert result.text.code_fence_language == expected_language
    assert result.full_text.startswith(f"```{expected_language}\n")


def test_extract_markdown_is_inserted_without_fence() -> None:
    """Decisión: `.md` ya es Markdown, se inserta directo (sin fence) para no perder estructura."""
    content = b"# Titulo\n\n- item uno\n- item dos\n"

    result = TextExtractor().extract(
        ExtractionInput(kind=AttachmentKind.TEXT, filename="notas.md", content=content)
    )

    assert result.text is not None
    assert result.text.code_fence_language is None
    assert "```" not in result.full_text
    assert result.full_text.strip() == "# Titulo\n\n- item uno\n- item dos"


def test_extract_content_with_embedded_triple_backticks_uses_a_longer_fence() -> None:
    """Un adjunto con ``` embebido no puede escapar del bloque de código (spotlighting)."""
    content = b"antes\n```\ncodigo embebido\n```\ndespues"

    result = TextExtractor().extract(
        ExtractionInput(kind=AttachmentKind.CODE, filename="notas.sql", content=content)
    )

    lines = result.full_text.splitlines()
    opening_fence = lines[0]
    closing_fence = [line for line in lines if line.startswith("`")][-1]
    assert opening_fence.startswith("````")  # más larga que la racha interna de 3
    assert closing_fence == opening_fence.removesuffix("sql")
    assert "```\ncodigo embebido\n```" in result.full_text


def test_extractor_version_reports_stdlib_and_python_version() -> None:
    """`extractor_version` no depende de librerías externas (solo stdlib)."""
    import platform

    result = TextExtractor().extract(
        ExtractionInput(kind=AttachmentKind.TEXT, filename="a.txt", content=b"x")
    )

    assert result.extractor_version == f"stdlib-codecs@python{platform.python_version()}"


def test_extract_rejects_wrong_attachment_kind() -> None:
    """El adapter solo procesa AttachmentKind.TEXT/CODE/LOG."""
    with pytest.raises(ValueError, match="TEXT/CODE/LOG"):
        TextExtractor().extract(
            ExtractionInput(kind=AttachmentKind.SPREADSHEET, filename="datos.xlsx", content=b"x")
        )


def test_extract_reads_from_source_path(tmp_path: Path) -> None:
    """El adapter también acepta la entrada vía `source_path` (worker aislado)."""
    file_path = tmp_path / "adjunto.txt"
    file_path.write_bytes(b"contenido en disco")

    result = TextExtractor().extract(
        ExtractionInput(
            kind=AttachmentKind.TEXT, filename="adjunto.txt", source_path=str(file_path)
        )
    )

    assert "contenido en disco" in result.full_text


def test_extract_has_marked_hidden_content_always_false() -> None:
    """Texto/código/logs no tienen concepto de contenido oculto (ANEXO §4.3 aplica a xlsx/docx)."""
    result = TextExtractor().extract(
        ExtractionInput(kind=AttachmentKind.TEXT, filename="a.txt", content=b"x")
    )
    assert result.has_marked_hidden_content is False
