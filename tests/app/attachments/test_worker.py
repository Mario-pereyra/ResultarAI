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
from tests.app.attachments.heavy_baseline_fake import fake_extract_with_heavy_baseline

_MIB = 1024 * 1024
_MEMORY_LIMIT = 384 * _MIB  # holgado sobre el baseline del interprete; el fake alloca 2 GiB
# Mismo default que `_DEFAULT_EXTRACTION_MEMORY_LIMIT_BYTES` de `config.py` (produccion).
_DEFAULT_PRODUCTION_MEMORY_LIMIT = 512 * _MIB


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
    # Antes del fix del limite RELATIVO (worker.py::_apply_address_space_limit) esta
    # aserción aceptaba tambien `worker_died` (dano colateral de la fragilidad de
    # RLIMIT_AS/ASLR anotada en BACKLOG-DESCUBRIMIENTOS 2026-07-12): el hilo alimentador
    # de la Queue podia morir por `RuntimeError: can't start new thread` en vez de que el
    # extractor reportara `MemoryError` ordenado. Con el limite relativo al baseline, la
    # causa es siempre `memory` de forma determinista.
    assert exc_info.value.params["cause"] == "memory"


def test_worker_survives_heavy_baseline_with_default_production_limit() -> None:
    """Regresion del bug real: `worker_died`/`can't start new thread` bajo uvicorn.

    Reproduce el diagnostico confirmado: un hijo forkserver que desempaqueta (unpickle)
    un extractor real (p.ej. `SpreadsheetExtractor.extract`, que importa `openpyxl`/
    `python_calamine`) ya tiene un VmSize de ~800 MB ANTES de que se aplique el limite de
    memoria -- muy por encima del default de produccion (512 MiB). Con un tope ABSOLUTO
    (el mecanismo anterior al fix), CUALQUIER extraccion -- hasta una trivial -- moria al
    hacer `result_queue.put()`: el primer mmap nuevo tras el `setrlimit` (el stack del
    hilo alimentador de la `Queue`) se rechazaba con ENOMEM porque el baseline ya excedia
    el tope, sin importar cuan chico fuera el resultado. `fake_extract_with_heavy_baseline`
    simula ese mismo baseline pesado (modulo separado que infla ~600 MB de VmSize al
    importarse, ver `heavy_baseline_fake.py`) SIN depender de una libreria de formato
    real. Con el limite RELATIVO al baseline (fix), esto tiene que seguir funcionando
    incluso con el limite DEFAULT de produccion.
    """
    result = run_in_isolated_worker(
        fake_extract_with_heavy_baseline,
        _text_source(),
        timeout_seconds=15.0,
        memory_limit_bytes=_DEFAULT_PRODUCTION_MEMORY_LIMIT,
    )
    assert result.extractor_version == "fake-heavy-baseline@1.0"


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
