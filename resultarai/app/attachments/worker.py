"""Worker de parseo aislado para la extraccion de adjuntos (d14, tarea 2.5).

La extraccion de un binario no confiable (un XLSX/PDF/DOCX potencialmente malformado)
NO puede correr en el proceso de la plataforma: un parser que entra en bucle o intenta
allocar gigabytes tumbaria `apps/platform`. El ANEXO §4.1 punto 5 (y §8 paso [4]) exige
correrla en un **worker aislado** con **timeout** (default 30 s) y **memoria acotada**.

Diseno y por que NO se deadlockea:

- **Proceso separado con `forkserver`** (no `fork`, no `spawn` directo): `fork` heredaria
  los hilos y locks del proceso multihilo de FastAPI/SQLAlchemy (deadlock clasico del fork
  con hilos). `forkserver` lanza, la PRIMERA vez que se usa, un proceso servidor persistente
  que se bootstrapea con la MISMA preparacion que `spawn` -- que SI re-importa el modulo
  `__main__` (`multiprocessing.spawn._fixup_main_from_path`); esto corrige una afirmacion
  previa de este docstring que decia lo contrario (Fix n5 del review final de
  d14-attachments: "no re-corre `__main__`" era empiricamente falso). La diferencia real
  con `spawn` puro es CUANDO y CUANTAS veces pasa: cada extraccion nueva NO relanza ese
  bootstrap, solo hace `fork()` desde el servidor ya inicializado (rapido, sin re-importar
  nada) -- por eso sigue sin heredar los hilos/locks del proceso multihilo de la plataforma
  (arranca desde el servidor limpio, no desde ese proceso) y por eso funciona bajo pytest:
  el `__main__` que se re-importa, UNA sola vez al levantar el servidor, es el entrypoint de
  pytest, que es seguro de importar (no relanza la coleccion de tests como efecto
  secundario). (Fallback a `spawn` si `forkserver` no estuviera disponible; ese camino SI
  re-ejecuta `__main__` en cada hijo, no solo una vez.)
- **Memoria** acotada en el HIJO con `resource.setrlimit(RLIMIT_AS)` antes de parsear,
  RELATIVO al VmSize que el hijo ya tiene mapeado en ese instante (no un techo absoluto
  -- ver el diagnostico completo en el docstring de `_apply_address_space_limit`: un
  techo absoluto revienta SIEMPRE bajo uvicorn, incluso para una extraccion trivial,
  porque desempaquetar el extractor real ya deja el VmSize del hijo por encima de
  cualquier techo razonable antes de aplicarlo). Una alloc que cruza el tope (baseline +
  `limit_bytes`) levanta `MemoryError` en el hijo (no un SIGKILL), que se reporta como
  fallo ordenado; si aun asi el interprete cae, el parent lo detecta por el `exitcode`.
  Estamos en Linux/WSL (RLIMIT_AS y `/proc/self/status` disponibles); el limite es config.
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

El worker recibe QUE callable correr de forma **inyectable** y GENERICO:
`run_in_isolated_worker` no esta atado a `ExtractionPort.extract` ni a
`ExtractionInput`/`ExtractionResult` (tipos parametrizados via `TypeVar`) -- cualquier
`Callable[[S], T]` picklable puede cruzar al worker con la misma proteccion de
timeout/memoria. El uso principal sigue siendo la extraccion de adjuntos (este modulo NO
importa ningun adapter concreto de `resultarai/adapters/extraction_*`; la composicion real
vive en `pipeline.py::resolve_extractor`), pero `validation.py::_reject_encrypted_pdf` (Fix
M2 del review final de d14-attachments) reutiliza el MISMO worker para aislar
`pypdf.PdfReader` del chequeo de PDF cifrado, que antes corria sin timeout en el thread
sincrono del request handler. El callable inyectado debe ser **picklable**
(funcion/metodo a nivel de modulo), porque cruza la frontera de proceso.
"""

from __future__ import annotations

import multiprocessing
import queue
import resource
import time
from collections.abc import Callable
from typing import Any, cast

from resultarai.app.attachments.errors import ExtractionFailedError, ExtractionTimeoutError
from resultarai.core.ports.extraction import ExtractionInput, ExtractionResult

__all__ = ["run_in_isolated_worker"]

Extractor = Callable[[ExtractionInput], ExtractionResult]

# `run_in_isolated_worker`/`_worker_child` son genericos (parametros de tipo PEP 695
# `[SourceT, ResultT]` en su propia firma): cualquier callable picklable -- no solo
# `Extractor` -- puede cruzar al worker aislado. Ver la nota de reutilizacion en el
# docstring del modulo (Fix M2 del review final de d14-attachments).

# Cadencia con que el parent sondea la cola mientras espera (s).
_POLL_INTERVAL_SECONDS = 0.05
# Margen para que un hijo que salio recien termine de volcar un resultado ya encolado (s).
_DRAIN_GRACE_SECONDS = 0.25
# Margen para que el hijo muera tras SIGTERM antes de escalar a SIGKILL, y tras SIGKILL (s).
_TERM_GRACE_SECONDS = 2.0
_KILL_GRACE_SECONDS = 2.0


def run_in_isolated_worker[SourceT, ResultT](
    extract_fn: Callable[[SourceT], ResultT],
    source: SourceT,
    *,
    timeout_seconds: float,
    memory_limit_bytes: int | None,
) -> ResultT:
    """Corre `extract_fn(source)` en un proceso aislado con timeout y memoria acotada.

    Generico sobre `SourceT`/`ResultT` (ver docstring del modulo): `extract_fn` puede ser
    cualquier callable picklable, no solo un `Extractor` de `ExtractionPort`. Devuelve lo
    que `extract_fn` retorne en caso de exito. Levanta `ExtractionTimeoutError` si supera
    `timeout_seconds`, o `ExtractionFailedError` si el worker muere (crash/OOM) o el
    callable lanza una excepcion. En cualquier caso el proceso hijo queda finalizado y el
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
        return cast(ResultT, data)
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
    multihilo (a diferencia de `fork`) lanzando un servidor persistente aparte. Ese
    servidor SI se bootstrapea como `spawn` -- re-importa `__main__` una vez, al
    arrancar (correccion del Fix n5 del review final: este docstring antes decia lo
    contrario) -- pero cada extraccion nueva solo hace `fork()` desde el servidor ya
    inicializado, sin repetir esa re-importacion (a diferencia de `spawn` puro, que la
    repite en cada hijo).
    """
    available = multiprocessing.get_all_start_methods()
    if "forkserver" in available:
        return multiprocessing.get_context("forkserver")
    if "spawn" in available:
        return multiprocessing.get_context("spawn")
    return multiprocessing.get_context()


def _worker_child[SourceT, ResultT](
    extract_fn: Callable[[SourceT], ResultT],
    source: SourceT,
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
    """Acota el espacio de direcciones del hijo (best-effort) con `RLIMIT_AS`, RELATIVO al
    VmSize que el hijo YA tiene mapeado en este instante (no un techo absoluto).

    Diagnostico (bug "worker_died"/"can't start new thread" reproducible al 100% bajo
    uvicorn, BACKLOG-DESCUBRIMIENTOS 2026-07-12 sobre fragilidad de RLIMIT_AS): un techo
    ABSOLUTO de 512 MiB (el default) revienta SIEMPRE, incluso para un CSV de 879 bytes,
    porque desempaquetar (unpickle) el extractor REAL en el hijo -- p.ej.
    `SpreadsheetExtractor.extract`, que importa `openpyxl`/`python_calamine` -- ya deja el
    VmSize del hijo en ~800 MB, MUY por encima del techo, ANTES de aplicar el limite
    siquiera (medido con `/proc/self/status`; confirmado que bajo pytest el baseline es
    mucho mas chico, por eso ahi "pasaba casi siempre"). Linux permite bajar el limite
    blando aunque el uso actual ya lo supere (no hay enforcement retroactivo sobre mapeos
    YA existentes), pero CUALQUIER mmap NUEVO se rechaza de inmediato con ENOMEM -- y el
    primer mmap nuevo que el hijo pide tras el setrlimit es, casi siempre, el stack del
    hilo alimentador de `multiprocessing.Queue` en el primer `put()` (`_worker_child`),
    que Python reporta como `RuntimeError: can't start new thread` (exactamente el
    traceback reportado). Confirmado tambien que cambiar a `RLIMIT_DATA` NO alcanza: el
    kernel moderno (`is_data_mapping()` en `mm/mmap.c`) cuenta los mapeos anonimos
    privados escribibles -- que es lo que es el stack de un thread -- tambien contra
    `RLIMIT_DATA`, asi que el mismo problema reproduce igual.

    La correccion real es que el techo sea RELATIVO al baseline, no absoluto: mantiene el
    espiritu del ANEXO §4.1 (memoria acotada DE VERDAD) porque un extractor no puede
    consumir mas de `limit_bytes` ADICIONALES sobre lo que ya costaba tenerlo importado --
    en vez de que el costo fijo de la libreria del formato se coma el presupuesto entero
    antes de arrancar. Si no se puede leer el baseline (entorno sin `/proc`), cae al
    comportamiento absoluto anterior como fallback defensivo (peor, pero no rompe nada
    nuevo). Solo baja el limite blando (subir el duro requiere privilegios); una alloc por
    encima del tope levanta `MemoryError` dentro del hijo, que se reporta como fallo
    ordenado; si el interprete cayera igual, el parent lo detecta por el `exitcode`.
    """
    try:
        baseline = _current_address_space_bytes()
        target = limit_bytes if baseline is None else baseline + limit_bytes
        _soft, hard = resource.getrlimit(resource.RLIMIT_AS)
        if hard != resource.RLIM_INFINITY:
            target = min(target, hard)
        resource.setrlimit(resource.RLIMIT_AS, (target, hard))
    except (ValueError, OSError):
        return


def _current_address_space_bytes() -> int | None:
    """VmSize actual del proceso (bytes), leido de `/proc/self/status`; `None` si falla.

    Estamos en Linux/WSL (mismo supuesto que el resto del modulo, ver docstring de
    arriba): `/proc/self/status` siempre expone `VmSize` en este entorno. Solo devuelve
    `None` de forma defensiva si el archivo no existe o el formato no es el esperado.
    """
    try:
        with open("/proc/self/status", encoding="ascii") as f:
            for line in f:
                if line.startswith("VmSize:"):
                    return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        return None
    return None
