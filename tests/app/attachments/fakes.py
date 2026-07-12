"""Extractores fake para los tests del worker aislado (d14, tarea 2.5).

Deben ser **picklable** (funciones a nivel de modulo): el worker los cruza a un proceso
hijo via `forkserver`/`spawn`, que reimporta ESTE modulo por su nombre. Por eso viven en un
modulo liviano aparte (no en el modulo de test, que arrastra TestClient/DB en su import):
asi el hijo solo importa el port de `core`, no toda la suite.

Cada fake implementa la forma de `ExtractionPort.extract` (`ExtractionInput -> ExtractionResult`):

- `fake_extract_ok`           exito determinista -> `ready`.
- `fake_extract_slow`         duerme mucho mas que cualquier timeout de test -> el parent lo mata.
- `fake_extract_oom`          intenta allocar muy por encima del `RLIMIT_AS` -> `MemoryError`.
- `fake_extract_passthrough`  devuelve `source.content` decodificado tal cual, marcando
                              contenido oculto: los tests de sanitizacion/heuristica (4.1/4.3)
                              inyectan el texto "sucio" que quieran a traves del worker real.
- `fake_extract_with_secret`  extraccion determinista con un secreto N3 (`sk-...`)
                              embebido: usada por `tests/app/attachments/test_pipeline.py`
                              (tarea 7.1) para forzar `blocked` a traves del worker real
                              sin depender de contenido en memoria.
"""

from __future__ import annotations

import time

from resultarai.core.ports.extraction import ExtractionInput, ExtractionResult

# Muy por encima del limite de memoria de cualquier test (2 GiB de espacio de direcciones).
_HUGE_ALLOCATION_BYTES = 2 * 1024 * 1024 * 1024
# Muy por encima de cualquier timeout de test: el parent lo aborta antes de que retorne.
_SLEEP_SECONDS = 120.0


def fake_extract_ok(source: ExtractionInput) -> ExtractionResult:
    """Extraccion exitosa y determinista."""
    return ExtractionResult(
        kind=source.kind,
        full_text=f"contenido extraido de {source.filename}",
        extractor_version="fake@1.0",
    )


def fake_extract_slow(source: ExtractionInput) -> ExtractionResult:
    """Bloquea mas que el timeout: fuerza el camino de `ExtractionTimeoutError`."""
    time.sleep(_SLEEP_SECONDS)
    return fake_extract_ok(source)


def fake_extract_oom(source: ExtractionInput) -> ExtractionResult:
    """Intenta allocar por encima del `RLIMIT_AS`: fuerza `MemoryError` en el hijo."""
    buffer = bytearray(_HUGE_ALLOCATION_BYTES)
    buffer[0] = 1
    return fake_extract_ok(source)


def fake_extract_raises(source: ExtractionInput) -> ExtractionResult:
    """Lanza una excepcion del parser (binario corrupto): fuerza `extractor_exception`."""
    raise ValueError("binario corrupto")


def fake_extract_passthrough(source: ExtractionInput) -> ExtractionResult:
    """Extrae `source.content` como UTF-8 tal cual (como un extractor de texto real).

    `has_marked_hidden_content=True` emula un extractor que marco `[oculta]` contenido
    oculto estructural; el texto en si lo decide cada test (via `content`).
    """
    assert source.content is not None, "el passthrough requiere content en memoria"
    return ExtractionResult(
        kind=source.kind,
        full_text=source.content.decode("utf-8"),
        extractor_version="fake-passthrough@1.0",
        has_marked_hidden_content=True,
    )


# Secreto deterministico (patron `sk-...` de `data_scan._SECRET_PATTERNS`) para forzar un
# hallazgo N3 sin depender de `source.content`/`source.source_path` (funciona igual via
# `process_attachment`, que siempre arma `ExtractionInput` con `source_path`).
SECRET_TEXT = "API_KEY=sk-abcdEFGH1234ijklMNOP5678qrst"


def fake_extract_with_secret(source: ExtractionInput) -> ExtractionResult:
    """Extraccion determinista cuyo `full_text` contiene un secreto N3 (`sk-...`).

    Ignora `source.content`/`source.source_path`: no necesita que el binario exista en
    disco, solo que `ExtractionInput` sea valido (tests de dedup de `pipeline.py`).
    """
    return ExtractionResult(
        kind=source.kind,
        full_text=SECRET_TEXT,
        extractor_version="fake-secret@1.0",
    )
