"""Worker de parseo aislado para la extraccion de adjuntos (d14, tarea 2.5).

La extraccion de un binario no confiable (un XLSX/PDF/DOCX potencialmente malformado)
NO puede correr en el proceso de la plataforma: un parser que entra en bucle o intenta
allocar gigabytes tumbaria `apps/platform`. El ANEXO §4.1 punto 5 (y §8 paso [4]) exige
correrla en un **worker aislado** con **timeout** (default 30 s) y **memoria acotada**.

Diseno y por que NO se deadlockea:

- **Proceso separado con `forkserver`** (no `fork`, no `spawn`): `fork` heredaria los hilos
  y locks del proceso multihilo de FastAPI/SQLAlchemy (deadlock clasico del fork con
  hilos); `spawn` re-ejecuta el modulo `__main__` (bajo pytest eso re-lanzaria pytest).
  `forkserver` bifurca desde un servidor limpio y minimo: ni hereda locks ni re-corre
  `__main__`. (Fallback a `spawn` si `forkserver` no estuviera disponible.)
- **Memoria** acotada en el HIJO con `resource.setrlimit(RLIMIT_AS)` antes de parsear:
  una alloc que cruza el tope levanta `MemoryError` en el hijo (no un SIGKILL), que se
  reporta como fallo ordenado; si aun asi el interprete cae, el parent lo detecta por el
  `exitcode`. Estamos en Linux/WSL (RLIMIT_AS disponible); el limite es config.
- **Resultado via `multiprocessing.Queue`**: el hijo hace `put()` (que retorna enseguida;
  un hilo alimentador vuelca al pipe) y el PARENT lee con `get()` **antes** de hacer
  `join()`. Ese orden es lo que evita el deadlock clasico "el hijo bloquea al salir
  esperando que el parent drene un resultado grande que el parent nunca lee": el parent
  siempre drena primero.
- **Recuperacion SIEMPRE**: el parent espera con un *deadline*; si vence, mata el hijo
  (`terminate` -> `kill`) y levanta `ExtractionTimeoutError` sin esperar indefinidamente.
  Si el hijo muere sin dejar resultado (OOM/crash), lo detecta por `is_alive()`/`exitcode`
  y levanta `ExtractionFailedError`. En ningun camino el parent queda colgado: la
  plataforma sigue operativa.

El worker recibe QUE extractor correr de forma **inyectable** (`ExtractionPort.extract` o
cualquier `Callable[[ExtractionInput], ExtractionResult]`); este modulo NO importa ningun
adapter concreto de `resultarai/adapters/extraction_*` (los terminan otros agentes en
paralelo; la composicion real llega en una tarea posterior). El callable inyectado debe
ser **picklable** (funcion/metodo a nivel de modulo), porque cruza la frontera de proceso.
"""

from __future__ import annotations

import multiprocessing
import queue
import resource
import time
from collections.abc import Callable
from typing import Any

from resultarai.app.attachments.errors import ExtractionFailedError, ExtractionTimeoutError
from resultarai.core.ports.extraction import ExtractionInput, ExtractionResult

__all__ = ["run_in_isolated_worker"]

Extractor = Callable[[ExtractionInput], ExtractionResult]

# Cadencia con que el parent sondea la cola mientras espera (s).
_POLL_INTERVAL_SECONDS = 0.05
# Margen para que un hijo que salio recien termine de volcar un resultado ya encolado (s).
_DRAIN_GRACE_SECONDS = 0.25
# Margen para que el hijo muera tras SIGTERM antes de escalar a SIGKILL, y tras SIGKILL (s).
_TERM_GRACE_SECONDS = 2.0
_KILL_GRACE_SECONDS = 2.0


def run_in_isolated_worker(
    extract_fn: Extractor,
    source: ExtractionInput,
    *,
    timeout_seconds: float,
    memory_limit_bytes: int | None,
) -> ExtractionResult:
    """Corre `extract_fn(source)` en un proceso aislado con timeout y memoria acotada.

    Devuelve el `ExtractionResult` en caso de exito. Levanta `ExtractionTimeoutError` si
    supera `timeout_seconds`, o `ExtractionFailedError` si el worker muere (crash/OOM) o el
    extractor lanza una excepcion. En cualquier caso el proceso hijo queda finalizado y el
    parent nunca se bloquea indefinidamente.
    """
    ctx = _mp_context()
    result_queue: multiprocessing.Queue[tuple[str, Any]] = ctx.Queue()
    proc = ctx.Process(
        target=_worker_child,
        args=(extract_fn, source, memory_limit_bytes, result_queue),
        daemon=True,
    )
    proc.start()
    try:
        status, data = _await_payload(proc, result_queue, timeout_seconds)
    finally:
        _reap(proc)
        result_queue.close()

    if status == "ok":
        assert isinstance(data, ExtractionResult), "el hijo debe devolver un ExtractionResult"
        return data
    cause = data.get("cause", "unknown") if isinstance(data, dict) else "unknown"
    extra = {k: v for k, v in data.items() if k != "cause"} if isinstance(data, dict) else {}
    raise ExtractionFailedError(cause=cause, **extra)


def _await_payload(
    proc: multiprocessing.process.BaseProcess,
    result_queue: multiprocessing.Queue[tuple[str, Any]],
    timeout_seconds: float,
) -> tuple[str, Any]:
    """Espera el payload del hijo hasta el deadline; mata y levanta si vence o si crashea.

    Drena la cola ANTES de cualquier `join` (ver docstring del modulo): asi el hilo
    alimentador del hijo nunca queda bloqueado esperando que el parent lea.
    """
    deadline = time.monotonic() + timeout_seconds
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            _reap(proc)
            raise ExtractionTimeoutError(timeout_seconds=timeout_seconds)
        try:
            return result_queue.get(timeout=min(remaining, _POLL_INTERVAL_SECONDS))
        except queue.Empty:
            if not proc.is_alive():
                # El hijo salio: puede haber encolado el resultado justo antes de morir.
                # Le damos un instante al alimentador para volcarlo; si no hay nada, crasheo.
                try:
                    return result_queue.get(timeout=_DRAIN_GRACE_SECONDS)
                except queue.Empty:
                    raise ExtractionFailedError(
                        cause="worker_died", exitcode=proc.exitcode
                    ) from None
            # Sigue vivo: reintentar hasta agotar el deadline.


def _reap(proc: multiprocessing.process.BaseProcess) -> None:
    """Asegura que el hijo quede muerto y unido, escalando SIGTERM -> SIGKILL. Idempotente."""
    if proc.is_alive():
        proc.terminate()
        proc.join(_TERM_GRACE_SECONDS)
    if proc.is_alive():
        proc.kill()
        proc.join(_KILL_GRACE_SECONDS)


def _mp_context() -> (
    multiprocessing.context.ForkServerContext
    | multiprocessing.context.SpawnContext
    | multiprocessing.context.DefaultContext
):
    """Contexto de multiprocessing: `forkserver` preferido, `spawn` como fallback.

    Se seleccionan con literales (no una variable) para que el tipo concreto del contexto
    exponga `.Process`/`.Queue`; `forkserver` evita heredar los hilos/locks del proceso
    multihilo (a diferencia de `fork`) y no re-ejecuta `__main__` (a diferencia de `spawn`).
    """
    available = multiprocessing.get_all_start_methods()
    if "forkserver" in available:
        return multiprocessing.get_context("forkserver")
    if "spawn" in available:
        return multiprocessing.get_context("spawn")
    return multiprocessing.get_context()


def _worker_child(
    extract_fn: Extractor,
    source: ExtractionInput,
    memory_limit_bytes: int | None,
    result_queue: multiprocessing.Queue[tuple[str, Any]],
) -> None:
    """Entrada del proceso hijo: acota memoria, corre el extractor y reporta el resultado.

    Contiene TODO (incluido `MemoryError` y cualquier `BaseException`): el hijo nunca debe
    propagar una traza; siempre deja un payload en la cola para que el parent decida.
    """
    if memory_limit_bytes is not None:
        _apply_address_space_limit(memory_limit_bytes)
    try:
        result = extract_fn(source)
    except MemoryError:
        result_queue.put(("error", {"cause": "memory"}))
        return
    except BaseException as exc:  # contener el binario no confiable es justamente el punto
        result_queue.put(("error", {"cause": "extractor_exception", "detail": repr(exc)[:500]}))
        return
    result_queue.put(("ok", result))


def _apply_address_space_limit(limit_bytes: int) -> None:
    """Acota el espacio de direcciones del hijo (best-effort) con `RLIMIT_AS`.

    Solo baja el limite blando (subir el duro requiere privilegios); si no se puede acotar,
    el timeout sigue acotando el tiempo de corrida. Una alloc por encima del tope levantara
    `MemoryError` dentro del hijo, que se reporta como fallo ordenado.
    """
    try:
        _soft, hard = resource.getrlimit(resource.RLIMIT_AS)
        target = limit_bytes
        if hard != resource.RLIM_INFINITY:
            target = min(target, hard)
        resource.setrlimit(resource.RLIMIT_AS, (target, hard))
    except (ValueError, OSError):
        return
