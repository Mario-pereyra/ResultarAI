"""Catalogo en memoria de un tipo de Manifest: unicidad de `id` y consulta por `id`.

`ManifestRegistry[M]` es una estructura pura de datos sobre Manifests ya validados por su
schema Pydantic (`BaseManifest` y subclases): no parsea YAML, no toca el filesystem ni la
red. El cargador (`loader.py`) es quien produce los Manifests y construye estas instancias.
Un unico generico cubre los 6 tipos (Agent/Skill/Tool/Policy/Routing/Eval) sin duplicar
codigo por tipo.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator

from resultarai.core.manifests import BaseManifest

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
    """Catalogo tipado de Manifests de un mismo tipo, consultable por `id`.

    Solo carga/valida-unicidad/cataloga/consulta: cero ejecucion, cero red, cero imports
    de adapters. El diseno de consultas por `status`, ciclo de vida y referencias cruzadas
    queda abierto para las tareas 2.2-2.4 (no implementado aqui).
    """

    def __init__(self, manifests: Iterable[M]) -> None:
        catalog: dict[str, M] = {}
        for manifest in manifests:
            if manifest.id in catalog:
                raise DuplicateManifestIdError(manifest.id, type(manifest))
            catalog[manifest.id] = manifest
        self._catalog = catalog

    def get(self, manifest_id: str) -> M | None:
        """Consulta pura por `id`; `None` si no esta catalogado."""
        return self._catalog.get(manifest_id)

    def __contains__(self, manifest_id: str) -> bool:
        return manifest_id in self._catalog

    def __iter__(self) -> Iterator[M]:
        return iter(self._catalog.values())

    def __len__(self) -> int:
        return len(self._catalog)
