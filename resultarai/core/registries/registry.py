"""Catalogo en memoria de un tipo de Manifest: unicidad de `id`, consulta y kill switch.

`ManifestRegistry[M]` es una estructura pura de datos sobre Manifests ya validados por su
schema Pydantic (`BaseManifest` y subclases): no parsea YAML, no toca el filesystem ni la
red. El cargador (`loader.py`) es quien produce los Manifests y construye estas instancias.
Un unico generico cubre los 6 tipos (Agent/Skill/Tool/Policy/Routing/Eval) sin duplicar
codigo por tipo.

**Catalogo vs. invocable (tarea 2.3, kill switch por `status`).** El catalogo cataloga
*todo* Manifest que cargue el loader, sin importar su `status`: `get()` devuelve un
Manifest `draft` o `deprecated` igual que uno `active`, porque la consulta por
trazabilidad ("un `deprecated` permanece catalogado y consultable", requirement de ciclo
de vida) no puede depender de si el Manifest es invocable. "Invocable" es una nocion mas
estrecha y explicita (`is_invocable`/`get_invocable`/`invocable`): solo los Manifests con
`status: active` lo son. Un `draft` esta en el catalogo (existe en `manifests/`, el loader
lo carga y lo valida) pero nunca es invocable; un `active` que pasa a `deprecated` en una
recarga posterior del YAML deja de ser invocable sin dejar de estar catalogado -- ese es
el kill switch: cambiar `status`, nunca borrar el Manifest ni sacarlo del catalogo.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator

from resultarai.core.manifests import BaseManifest, ManifestStatus

__all__ = ["DuplicateManifestIdError", "ManifestRegistry"]


class DuplicateManifestIdError(ValueError):
    """Dos manifiestos del mismo tipo declaran el mismo `id` (carga rechazada)."""

    def __init__(self, manifest_id: str, manifest_type: type[BaseManifest]) -> None:
        super().__init__(
            f"duplicate manifest id {manifest_id!r} for {manifest_type.__name__}: "
            "each id must be unique within its manifest type"
        )
        self.manifest_id = manifest_id
        self.manifest_type = manifest_type


class ManifestRegistry[M: BaseManifest]:
    """Catalogo tipado de Manifests de un mismo tipo, consultable por `id` y por invocabilidad.

    Solo carga/valida-unicidad/cataloga/consulta: cero ejecucion, cero red, cero imports
    de adapters. Las referencias cruzadas (tarea 2.2) viven en `cross_references.py`; el
    ciclo de vida y kill switch por `status` (tarea 2.3) vive aqui, como
    `is_invocable`/`get_invocable`/`invocable`; la consulta generica por `status` (tarea
    2.4, listar todos los `deprecated`, etc.) es `by_status`, sobre la que `invocable()`
    esta implementado como el caso particular `status: active`.
    """

    def __init__(self, manifests: Iterable[M]) -> None:
        catalog: dict[str, M] = {}
        for manifest in manifests:
            if manifest.id in catalog:
                raise DuplicateManifestIdError(manifest.id, type(manifest))
            catalog[manifest.id] = manifest
        self._catalog = catalog

    def get(self, manifest_id: str) -> M | None:
        """Consulta pura por `id`; `None` si no esta catalogado.

        Devuelve el Manifest sin importar su `status`: un `draft` o un `deprecated` se
        consultan igual que un `active` (catalogo por trazabilidad, ver docstring del
        modulo). Para saber si `manifest_id` es invocable ademas de estar catalogado, usa
        `is_invocable`/`get_invocable`.
        """
        return self._catalog.get(manifest_id)

    def is_invocable(self, manifest_id: str) -> bool:
        """True si `manifest_id` esta catalogado y su `status` es `active`.

        Kill switch: un Manifest que era `active` y pasa a `deprecated` en una recarga
        posterior del YAML deja de ser invocable (`is_invocable` pasa a `False`) sin dejar
        de estar catalogado (`get` lo sigue devolviendo, `manifest_id in registry` sigue
        siendo `True`). Un `draft` nunca es invocable, aunque exista en `manifests/` y
        este catalogado.
        """
        manifest = self._catalog.get(manifest_id)
        return manifest is not None and manifest.status == ManifestStatus.ACTIVE

    def get_invocable(self, manifest_id: str) -> M | None:
        """El Manifest `manifest_id` si es invocable (`status: active`); `None` si no.

        `None` cubre dos casos distintos que esta API deliberadamente no distingue para
        quien solo quiere invocar: `manifest_id` no esta catalogado, o si lo esta su
        `status` no es `active` (`draft`, `validated` o `deprecated`). Quien necesite
        distinguirlos usa `get` (catalogo) + `is_invocable` (invocabilidad) por separado.
        """
        manifest = self._catalog.get(manifest_id)
        if manifest is not None and manifest.status == ManifestStatus.ACTIVE:
            return manifest
        return None

    def by_status(self, status: ManifestStatus) -> tuple[M, ...]:
        """Todos los Manifests catalogados con ese `status`, en orden de insercion.

        Consulta generica del catalogo (tarea 2.4): sirve tanto para listar los
        invocables (`status: active`) como para trazabilidad sobre cualquier otro
        estado (p. ej. todos los `deprecated`, o todos los `draft`). Operacion pura de
        lectura -- nunca muta `self._catalog` ni marca nada como invocable; consultar un
        `deprecated` con `by_status` no lo reactiva. Si ningun Manifest catalogado tiene
        ese `status` devuelve una tupla vacia, nunca un error.
        """
        return tuple(manifest for manifest in self._catalog.values() if manifest.status == status)

    def invocable(self) -> tuple[M, ...]:
        """Todos los Manifests catalogados con `status: active`, en orden de insercion.

        Operacion pura de lectura (no muta el catalogo). Excluye `draft`, `validated` y
        `deprecated` -- el kill switch de un `active` a `deprecated` lo saca de esta
        coleccion en la siguiente construccion del Registry, aunque siga en `get()`.

        Implementado sobre `by_status` (tarea 2.4): `invocable()` es el caso particular
        `by_status(ManifestStatus.ACTIVE)`. Se mantiene como metodo propio (en vez de que
        el resto del codigo llame a `by_status(ACTIVE)` directamente) porque "invocable"
        es el nombre de dominio explicito que usan `is_invocable`/`get_invocable`, y no
        toda consulta por `status: active` es conceptualmente una consulta de
        invocabilidad -- mantener el nombre evita que quien lea el codigo tenga que saber
        que `ACTIVE` es sinonimo de invocable.
        """
        return self.by_status(ManifestStatus.ACTIVE)

    def __contains__(self, manifest_id: str) -> bool:
        return manifest_id in self._catalog

    def __iter__(self) -> Iterator[M]:
        return iter(self._catalog.values())

    def __len__(self) -> int:
        return len(self._catalog)
