"""Fake que simula un hijo forkserver con baseline de memoria YA pesado (d14, worker).

Vive en un modulo SEPARADO de `fakes.py` (no en el): el hijo aloca este costo al
desempaquetar (unpickle) el extractor -- que requiere `import`ar el modulo que lo
define -- asi que SOLO el test que usa `fake_extract_with_heavy_baseline` paga este
costo; los demas tests que importan `fakes.py` no se ven afectados.

Reproduce, sin depender de una libreria de formato real (openpyxl/pypdf/mammoth), el
escenario detras del bug real reportado bajo uvicorn: un hijo forkserver, al
desempaquetar un extractor real (p.ej. `SpreadsheetExtractor.extract`, que importa
`openpyxl`/`python_calamine`), media ~800 MB de VmSize ANTES de que
`_apply_address_space_limit` (worker.py) llegue a aplicar el limite -- muy por encima del
default de 512 MiB. Este modulo infla el VmSize del proceso que lo importa en ~600 MB A
NIVEL DE MODULO (import time), simulando ese mismo costo de forma determinista y sin
dependencias pesadas reales.
"""

from __future__ import annotations

from resultarai.core.ports.extraction import ExtractionInput, ExtractionResult

# ~600 MB de VA, con cada pagina TOCADA (no solo reservada) para que cuente como VmSize
# real -- por encima del default de produccion (512 MiB, `_DEFAULT_EXTRACTION_MEMORY_LIMIT_BYTES`
# en `config.py`), igual que el baseline real de un hijo que desempaqueta un extractor
# real (ver diagnostico en `worker.py::_apply_address_space_limit`).
_BASELINE_PADDING_BYTES = 600 * 1024 * 1024
_PAGE_SIZE = 4096
_padding = bytearray(_BASELINE_PADDING_BYTES)
for _offset in range(0, len(_padding), _PAGE_SIZE):
    _padding[_offset] = 1


def fake_extract_with_heavy_baseline(source: ExtractionInput) -> ExtractionResult:
    """Extraccion exitosa y determinista, pero IMPORTADA desde un modulo que ya pesa
    ~600 MB de VmSize -- simula un hijo cuyo baseline ya excede el tope de memoria
    default ANTES de que `_worker_child` corra el extractor (ver docstring del modulo).
    """
    return ExtractionResult(
        kind=source.kind,
        full_text=f"contenido extraido de {source.filename}",
        extractor_version="fake-heavy-baseline@1.0",
    )
