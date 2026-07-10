"""Extractores fake para los tests del worker aislado (d14, tarea 2.5).

Deben ser **picklable** (funciones a nivel de modulo): el worker los cruza a un proceso
hijo via `forkserver`/`spawn`, que reimporta ESTE modulo por su nombre. Por eso viven en un
modulo liviano aparte (no en el modulo de test, que arrastra TestClient/DB en su import):
asi el hijo solo importa el port de `core`, no toda la suite.

Cada fake implementa la forma de `ExtractionPort.extract` (`ExtractionInput -> ExtractionResult`):

- `fake_extract_ok`      exito determinista -> `ready`.
- `fake_extract_slow`    duerme mucho mas que cualquier timeout de test -> el parent lo mata.
- `fake_extract_oom`     intenta allocar muy por encima del `RLIMIT_AS` -> `MemoryError`.
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
