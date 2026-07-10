"""Constructor de un DOCX mínimo (ZIP OOXML a mano) para los contract tests
de `extraction_docx`. Sin dependencias nuevas (no usa `python-docx`).

El documento tiene: un título (Heading1), un párrafo, un subtítulo (Heading2),
una tabla 2x2 y una imagen embebida con texto alternativo.
"""

from __future__ import annotations

import io
import zipfile

_CONTENT_TYPES = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="png" ContentType="image/png"/>
  <Override PartName="/word/document.xml"
    ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""

_PACKAGE_RELS = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
    Target="word/document.xml"/>
</Relationships>"""

_DOCUMENT_RELS = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
    Target="media/image1.png"/>
</Relationships>"""

_DOCUMENT_TEMPLATE = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
            xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
            xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <w:body>
    <w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>{heading1}</w:t></w:r></w:p>
    <w:p><w:r><w:t>{paragraph}</w:t></w:r></w:p>
    <w:p><w:pPr><w:pStyle w:val="Heading2"/></w:pPr><w:r><w:t>{heading2}</w:t></w:r></w:p>
    <w:tbl>
      <w:tr>
        <w:tc><w:p><w:r><w:t>{cell_header_a}</w:t></w:r></w:p></w:tc>
        <w:tc><w:p><w:r><w:t>{cell_header_b}</w:t></w:r></w:p></w:tc>
      </w:tr>
      <w:tr>
        <w:tc><w:p><w:r><w:t>{cell_data_a}</w:t></w:r></w:p></w:tc>
        <w:tc><w:p><w:r><w:t>{cell_data_b}</w:t></w:r></w:p></w:tc>
      </w:tr>
    </w:tbl>
    <w:p>
      <w:r>
        <w:drawing>
          <wp:inline>
            <wp:docPr id="1" name="Imagen 1" descr="{image_alt_text}"/>
            <a:graphic>
              <a:graphicData>
                <pic:pic>
                  <pic:blipFill>
                    <a:blip r:embed="rId1"/>
                  </pic:blipFill>
                </pic:pic>
              </a:graphicData>
            </a:graphic>
          </wp:inline>
        </w:drawing>
      </w:r>
    </w:p>
  </w:body>
</w:document>"""

# PNG 1x1 valido (el contenido no importa: el adapter nunca decodifica la imagen).
_PNG_1PX = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108020000009077"
    "53de0000000c4944415478da6360000002000155038e02000000004945"
    "4e44ae426082"
)


def build_docx_with_headings_table_and_image(
    heading1: str = "1. Titulo Principal",
    paragraph: str = "Parrafo normal introductorio.",
    heading2: str = "1.1 Subtitulo",
    cell_header_a: str = "Columna A",
    cell_header_b: str = "Columna B",
    cell_data_a: str = "dato1",
    cell_data_b: str = "dato2",
    image_alt_text: str = "Diagrama de flujo",
) -> bytes:
    """Arma el ZIP OOXML minimo de un .docx con encabezados, tabla e imagen."""
    document_xml = _DOCUMENT_TEMPLATE.format(
        heading1=heading1,
        paragraph=paragraph,
        heading2=heading2,
        cell_header_a=cell_header_a,
        cell_header_b=cell_header_b,
        cell_data_a=cell_data_a,
        cell_data_b=cell_data_b,
        image_alt_text=image_alt_text,
    ).encode("utf-8")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _CONTENT_TYPES)
        archive.writestr("_rels/.rels", _PACKAGE_RELS)
        archive.writestr("word/document.xml", document_xml)
        archive.writestr("word/_rels/document.xml.rels", _DOCUMENT_RELS)
        archive.writestr("word/media/image1.png", _PNG_1PX)
    return buffer.getvalue()
