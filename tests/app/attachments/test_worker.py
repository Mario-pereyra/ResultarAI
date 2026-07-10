"""Tests del worker de parseo aislado (d14, tarea 2.5).

Cubre el requirement "Parseo en worker aislado con timeout y memoria acotada" de
`attachments-security`: la extraccion corre en un proceso separado; un extractor que
supera el timeout, uno que revienta la memoria y uno que lanza excepcion se contienen y se
traducen a excepciones tipadas, y el parent SIEMPRE se recupera (la plataforma sigue
operativa: puede correr otra extraccion despues).

Los extractores fake viven en ``tests/app/attachments/fakes.py`` (picklable, importable por
el proceso hijo). No se importa ningun adapter concreto de ``extraction_*``.
"""

from __future__ import annotations

import pytest

from resultarai.app.attachments.errors import ExtractionFailedError, ExtractionTimeoutError
from resultarai.app.attachments.worker import run_in_isolated_worker
from resultarai.core.ports.extraction import AttachmentKind, ExtractionInput
from tests.app.attachments.fakes import (
    fake_extract_ok,
    fake_extract_oom,
    fake_extract_raises,
    fake_extract_slow,
)

_MIB = 1024 * 1024
_MEMORY_LIMIT = 384 * _MIB  # holgado sobre el baseline del interprete; el fake alloca 2 GiB


def _text_source() -> ExtractionInput:
    return ExtractionInput(kind=AttachmentKind.TEXT, filename="notas.txt", content=b"hola mundo")


def test_worker_success_returns_result() -> None:
    """Un extractor que retorna bien produce el `ExtractionResult` (camino a `ready`)."""
    result = run_in_isolated_worker(
        fake_extract_ok, _text_source(), timeout_seconds=10.0, memory_limit_bytes=_MEMORY_LIMIT
    )
    assert result.kind is AttachmentKind.TEXT
    assert result.full_text == "contenido extraido de notas.txt"
    assert result.extractor_version == "fake@1.0"


def test_worker_timeout_raises_and_platform_stays_operative() -> None:
    """Un extractor que cuelga se aborta con timeout; la plataforma sigue respondiendo."""
    with pytest.raises(ExtractionTimeoutError) as exc_info:
        run_in_isolated_worker(
            fake_extract_slow,
            _text_source(),
            timeout_seconds=0.4,
            memory_limit_bytes=_MEMORY_LIMIT,
        )
    assert exc_info.value.error_code == "extraction_timeout"
    assert exc_info.value.params["timeout_seconds"] == 0.4

    # La plataforma sigue operativa: una extraccion posterior funciona sin quedar colgada.
    recovered = run_in_isolated_worker(
        fake_extract_ok, _text_source(), timeout_seconds=10.0, memory_limit_bytes=_MEMORY_LIMIT
    )
    assert recovered.full_text == "contenido extraido de notas.txt"


def test_worker_memory_limit_raises_failed() -> None:
    """Un extractor que revienta la memoria acotada se traduce a `ExtractionFailedError`."""
    with pytest.raises(ExtractionFailedError) as exc_info:
        run_in_isolated_worker(
            fake_extract_oom,
            _text_source(),
            timeout_seconds=15.0,
            memory_limit_bytes=_MEMORY_LIMIT,
        )
    assert exc_info.value.error_code == "extraction_failed"
    # El hijo reporta `memory` (MemoryError ordenado); si el interprete cayera duro,
    # el parent lo veria como `worker_died`. Cualquiera deja el adjunto en `error`.
    assert exc_info.value.params["cause"] in {"memory", "worker_died"}


def test_worker_extractor_exception_raises_failed() -> None:
    """Una excepcion del parser (binario corrupto) se contiene como `ExtractionFailedError`."""
    with pytest.raises(ExtractionFailedError) as exc_info:
        run_in_isolated_worker(
            fake_extract_raises,
            _text_source(),
            timeout_seconds=10.0,
            memory_limit_bytes=_MEMORY_LIMIT,
        )
    assert exc_info.value.params["cause"] == "extractor_exception"
