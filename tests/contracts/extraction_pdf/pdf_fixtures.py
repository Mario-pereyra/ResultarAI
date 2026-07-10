"""Constructores de PDFs mínimos para los contract tests de `extraction_pdf`.

Sin dependencias nuevas: los PDFs de texto nativo se arman a mano (header +
objetos + xref), y los "escaneados" se arman con `pypdf.PdfWriter` (páginas en
blanco, 0 chars/página).
"""

from __future__ import annotations

import io

from pypdf import PdfWriter


def build_native_text_pdf(page_texts: list[str]) -> bytes:
    """Arma un PDF válido a mano, un content stream de texto simple por página."""
    object_count = len(page_texts)
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        _pages_object(object_count),
    ]

    font_object_number = 3 + object_count
    objects.extend(_page_object(index, font_object_number) for index in range(object_count))
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    objects.extend(_content_stream_object(text) for text in page_texts)

    return _assemble_pdf(objects)


def build_blank_pages_pdf(page_count: int, width: float = 200.0, height: float = 200.0) -> bytes:
    """PDF con `page_count` páginas en blanco (0 chars extraíbles por página)."""
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=width, height=height)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def build_encrypted_pdf() -> bytes:
    """PDF de una página protegido con contraseña de usuario."""
    writer = PdfWriter()
    writer.add_blank_page(width=200.0, height=200.0)
    writer.encrypt(user_password="secreto", owner_password="secreto-dueno")
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def _pages_object(page_count: int) -> bytes:
    kids = " ".join(f"{3 + index} 0 R" for index in range(page_count))
    return f"<< /Type /Pages /Kids [{kids}] /Count {page_count} >>".encode("latin-1")


def _page_object(index: int, font_object_number: int) -> bytes:
    content_object_number = font_object_number + 1 + index
    page_dict = (
        f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 300] "
        f"/Resources << /Font << /F1 {font_object_number} 0 R >> >> "
        f"/Contents {content_object_number} 0 R >>"
    )
    return page_dict.encode("latin-1")


def _content_stream_object(text: str) -> bytes:
    escaped = text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
    stream_body = f"BT /F1 12 Tf 20 250 Td ({escaped}) Tj ET".encode("latin-1")
    return (
        f"<< /Length {len(stream_body)} >>\nstream\n".encode("latin-1")
        + stream_body
        + b"\nendstream"
    )


def _assemble_pdf(objects: list[bytes]) -> bytes:
    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode("latin-1")
        out += obj
        out += b"\nendobj\n"

    xref_offset = len(out)
    total_objects = len(objects) + 1
    out += f"xref\n0 {total_objects}\n".encode("latin-1")
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode("latin-1")
    out += b"trailer\n"
    out += f"<< /Size {total_objects} /Root 1 0 R >>\n".encode("latin-1")
    out += b"startxref\n"
    out += f"{xref_offset}\n".encode("latin-1")
    out += b"%%EOF"
    return bytes(out)
