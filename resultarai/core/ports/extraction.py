"""Port de extracción de adjuntos (ExtractionPort).

Define el contrato entre el pipeline de adjuntos y los extractores por tipo de
archivo. Cada tipo extractable (hojas de cálculo, PDF, DOCX, texto/código/logs)
es un adapter independiente que implementa el mismo `ExtractionPort`; `core/`
solo describe la forma de la entrada y de la salida, nunca cómo se parsea el
binario (ver ANEXO-ATTACHMENTS §2 y design.md, decisión 1).

Alcance del port: convertir un binario ya validado en su **extracción** de texto
determinista (`full_text`) más los metadatos estructurales que solo el extractor
conoce (inventario/esquema de hojas, páginas y detección de escaneado del PDF,
encoding del texto) y la `extractor_version` para trazabilidad (ANEXO §2 P2, §5).

Fuera del alcance del port (etapas posteriores del pipeline, no del extractor):
sanitización pre-inserción, escaneo de niveles de datos N2/N3, conteo de tokens y
truncado por relevancia. El extractor solo señala el hecho de haber marcado
contenido oculto (`[oculta]`); no decide política.
"""

from __future__ import annotations

import enum
from typing import Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

__all__ = [
    "AttachmentKind",
    "ColumnSchema",
    "ColumnType",
    "ExtractionInput",
    "ExtractionPort",
    "ExtractionResult",
    "PdfStructure",
    "SheetMetadata",
    "SpreadsheetStructure",
    "TextStructure",
]


class AttachmentKind(enum.StrEnum):
    """Familias de adjunto que el pipeline sabe extraer (ANEXO §9).

    Solo cubre tipos extractables: los tipos rechazados (imágenes en V1,
    comprimidos, ejecutables, formatos con macros) nunca llegan al extractor
    porque el adapter de subida no los admite.
    """

    SPREADSHEET = "spreadsheet"  # .xlsx / .xls / .csv / .tsv (ANEXO §2.1)
    PDF = "pdf"  # .pdf (ANEXO §2.2)
    DOCX = "docx"  # .docx (ANEXO §2.3)
    TEXT = "text"  # .txt / .md (ANEXO §2.5)
    CODE = "code"  # .prw / .prx / .tlpp / .sql / .json / .xml / .yml / .ini (ANEXO §2.5)
    LOG = "log"  # .log (ANEXO §2.5, truncado tail-first en etapa posterior)


class ColumnType(enum.StrEnum):
    """Tipo inferido por columna en el esquema de una hoja (ANEXO §2.1)."""

    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    FORMULA = "formula"


class ColumnSchema(BaseModel):
    """Esquema de una columna de hoja: encabezado + tipo inferido + no-vacíos.

    Es la representación esquema-primero que rinde más por token que volcar filas
    crudas (ANEXO §2.1). `header` puede ser `None` cuando no se detecta fila de
    encabezados.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    header: str | None
    inferred_type: ColumnType
    non_empty_count: int = Field(ge=0)


class SheetMetadata(BaseModel):
    """Inventario + esquema de una hoja de cálculo (ANEXO §2.1).

    El inventario (nombre, dimensiones, hoja activa) se conserva siempre completo
    aunque el detalle de filas se trunque en una etapa posterior. `is_hidden`
    señala hojas ocultas para que el pipeline las marque `[oculta]` (ANEXO §4.3).
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    name: str
    row_count: int = Field(ge=0)
    column_count: int = Field(ge=0)
    is_active: bool = False
    is_hidden: bool = False
    columns: list[ColumnSchema] = Field(default_factory=list)


class SpreadsheetStructure(BaseModel):
    """Metadatos estructurales de un adjunto de hojas de cálculo (ANEXO §2.1)."""

    model_config = ConfigDict(strict=True, extra="forbid")

    sheets: list[SheetMetadata] = Field(default_factory=list)


class PdfStructure(BaseModel):
    """Metadatos estructurales de un PDF (ANEXO §2.2).

    `avg_chars_per_page` es la señal cruda de escaneado: el pipeline la compara
    contra el umbral configurado por instancia (~50 chars/página). `is_scanned`
    es la clasificación que el extractor puede aportar cuando conoce el umbral;
    la ofrecemos aparte para no obligar al port a fijar el umbral como constante.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    page_count: int = Field(ge=0)
    avg_chars_per_page: float = Field(ge=0.0)
    is_scanned: bool = False


class TextStructure(BaseModel):
    """Metadatos estructurales de texto/código/logs (ANEXO §2.5).

    `source_encoding` es el encoding original detectado antes de convertir a
    UTF-8 (p. ej. `windows-1252` en fuentes AdvPL viejos y logs de Protheus).
    `code_fence_language` es el lenguaje del bloque de código con que se envolvió
    el contenido (`advpl`, `sql`, `log`, …).
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    source_encoding: str | None = None
    code_fence_language: str | None = None


class ExtractionInput(BaseModel):
    """Entrada del extractor: binario ya validado + su tipo detectado.

    El binario llega como `content` (bytes en memoria) **o** como `source_path`
    (ruta al archivo en el volumen, servido al worker aislado) — exactamente uno
    de los dos. `filename` es el nombre original, usado para inferir el lenguaje
    del bloque de código y para los marcadores de imagen omitida; no se confía
    como fuente de tipo (eso ya lo resolvió la validación de magic bytes).
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    kind: AttachmentKind
    filename: str
    content: bytes | None = None
    source_path: str | None = None

    @model_validator(mode="after")
    def _exactly_one_source(self) -> Self:
        if (self.content is None) == (self.source_path is None):
            raise ValueError("Se requiere exactamente uno de 'content' o 'source_path'.")
        return self


class ExtractionResult(BaseModel):
    """Extracción estructurada producida por un extractor (ANEXO §2, §5).

    `full_text` es el contenido completo extraído, determinista, que se almacena
    una sola vez (ANEXO §2 P2); las etapas posteriores del pipeline lo truncan
    para producir el `inserted_text` — el port no trunca. `extractor_version`
    identifica el extractor y su versión (p. ej. `pypdf@5.1.0`) para trazabilidad.
    Los metadatos estructurales son opcionales y dependen de `kind`: solo el campo
    correspondiente al tipo extraído viene poblado.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    kind: AttachmentKind
    full_text: str
    extractor_version: str
    has_marked_hidden_content: bool = False
    spreadsheet: SpreadsheetStructure | None = None
    pdf: PdfStructure | None = None
    text: TextStructure | None = None


class ExtractionPort(Protocol):
    """Protocolo de extracción de adjuntos por tipo de archivo.

    Cada tipo (hojas, PDF, DOCX, texto/código/logs) se implementa como un adapter
    independiente detrás de este mismo Protocol (design.md, decisión 1). El
    adapter traduce el binario a texto y metadatos estructurales; no decide
    política, no sanitiza, no trunca ni escanea N2/N3 (etapas posteriores).
    """

    def extract(self, source: ExtractionInput) -> ExtractionResult:
        """Extrae `source` a texto estructurado con su `extractor_version`."""
        ...
