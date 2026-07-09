"""Arranque fail-fast de la plataforma (a02-core-manifiestos, tarea 4.2).

Transporte para `load_registries` (`core/registries/loader.py`): el mismo "un solo camino
de validacion, tres disparadores" (decision 7 de `design.md`) que ya usan el desarrollador
local y CI (`app/cli.py`, tarea 4.1) lo usa ahora el arranque de la plataforma. Este modulo
NO monta FastAPI ni ningun server: es la funcion de arranque pura (`bootstrap`) que un
futuro `app/main.py` (b06+) invocara antes de levantar cualquier adapter, e inyectara los
`Registries` resultantes al resto de la composicion.

**Decision -- `StartupError` propia con causa encadenada, no dejar propagar el error de
`core/` desnudo.** `load_registries` ya lanza `ManifestLoadError`, `DuplicateManifestIdError`
o `DanglingReferenceError` (los mismos tres que consume `cli.py`), cada uno nombrando el
Manifest o la referencia culpable en su propio mensaje. `bootstrap` los captura y los
re-lanza envueltos en `StartupError` (`raise StartupError(...) from exc`, causa encadenada
via `__cause__`, nunca silenciada) por una razon de capa, no de contenido: quien arranca la
plataforma (`app/`) no deberia tener que conocer ni importar los tres tipos de excepcion de
`core/registries` para saber que "el arranque fallo por un Manifest invalido" -- un unico
tipo de error en la frontera de `app/` es la superficie que el resto del arranque (y quien
lo invoque, p. ej. un proceso `main` futuro) necesita manejar. El mensaje de `StartupError`
incluye el mensaje original (que ya nombra archivo/referencia) mas el propio
`manifests_dir`, y `__cause__` preserva el traceback completo para debugging. Nunca se hace
`except Exception` generico: solo los tres tipos que `core/registries` documenta como
resultado posible de `load_registries` se traducen; cualquier otro error (p. ej. un bug de
programacion) se propaga tal cual, sin disfrazarse de fallo de arranque.

**Decision -- `bootstrap` no resuelve un default de `manifests_dir`.** A diferencia de
`cli.py` (que por comodidad de invocacion humana default-ea a `Path.cwd() / "manifests"`),
`bootstrap` exige `manifests_dir` explicito: la resolucion de la ruta de produccion (p. ej.
relativa a la raiz del deployable, o via variable de entorno) es responsabilidad del
composition root que invoque `bootstrap` (el futuro `app/main.py` de `b06+`), no de esta
funcion. Mantiene `bootstrap` puro y facil de testear con `tmp_path`, sin acoplarlo al cwd
del proceso.

**Decision -- un `draft` valido no aborta el arranque.** No hace falta ninguna logica
adicional aqui: `load_registries` ya cataloga un Manifest `draft` sin objetar (el ciclo de
vida -- tarea 2.3 -- lo excluye de `invocable()`/`is_invocable()` pero lo mantiene en el
catalogo), asi que un `draft` que valida contra su schema simplemente entra en los
`Registries` que `bootstrap` devuelve, catalogado y no invocable. `bootstrap` no necesita
distinguir este caso: es el comportamiento por defecto de los Registries, no algo que el
arranque deba reimplementar.
"""

from __future__ import annotations

from pathlib import Path

from resultarai.core.registries import (
    DanglingReferenceError,
    DuplicateManifestIdError,
    ManifestLoadError,
    Registries,
    load_registries,
)

__all__ = ["StartupError", "bootstrap"]


class StartupError(Exception):
    """El arranque de la plataforma se abortó porque un Manifest no validó.

    Envuelve (con causa encadenada, `__cause__`) el `ManifestLoadError`,
    `DuplicateManifestIdError` o `DanglingReferenceError` original que `load_registries`
    lanzó; su mensaje incluye el `manifests_dir` inspeccionado y el mensaje original, que ya
    identifica el archivo o la referencia cruzada culpable. La plataforma NO queda "en
    servicio" cuando esto se lanza: `bootstrap` no captura `StartupError` internamente, así
    que se propaga hasta quien lo invoque (el composition root), abortando el arranque.
    """


def bootstrap(manifests_dir: Path) -> Registries:
    """Valida todos los manifiestos de `manifests_dir` y construye los Registries.

    Fail-fast: si algún Manifest viola su schema Pydantic, hay un `id` duplicado dentro de
    un mismo tipo, o alguna referencia cruzada cuelga (Agent -> Skill inexistente/no
    `active`, Skill -> Tool inexistente/no `active`, etc.), esta función lanza
    `StartupError` en vez de devolver — la plataforma nunca queda en servicio con
    manifiestos inválidos. Si todo valida, devuelve los 6 `Registries` construidos para que
    el resto del arranque los consuma (los futuros changes `b06+` los inyectarán en el
    runtime, el Policy Gate y el Skill Router).

    Un Manifest `draft` válido no aborta el arranque: queda catalogado (consultable via
    `Registries.<tipo>.get`) pero no invocable (`is_invocable` es `False`), tal como ya
    garantizan los Registries — ver la decisión correspondiente en el docstring del módulo.
    """
    try:
        return load_registries(manifests_dir)
    except (ManifestLoadError, DuplicateManifestIdError, DanglingReferenceError) as exc:
        raise StartupError(
            f"arranque abortado: validación de manifiestos falló en {manifests_dir}: {exc}"
        ) from exc
