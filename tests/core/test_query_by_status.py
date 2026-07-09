"""Tests de la consulta pura por `status` en los Registries (a02-core-manifiestos, 2.4).

Cubre los 4 escenarios exactos del requirement "Consulta de Manifests por status"
(`openspec/changes/a02-core-manifiestos/specs/manifest-registries/spec.md`):

1. Consultar por `status: active` -> devuelve solo los activos (excluye draft y
   deprecated).
2. Consultar por `status: deprecated` -> devuelve los deprecados sin marcarlos como
   invocables.
3. La consulta no muta el catalogo (operacion pura de lectura).
4. Consulta por un status sin manifests -> coleccion vacia sin error.

Construye `ManifestRegistry` directamente sobre objetos `RoutingManifest` (el Manifest mas
simple del set: solo `id`/`status`/`version`/`rules`), sin pasar por YAML ni por
`load_registries` -- `ManifestRegistry.by_status` no valida referencias cruzadas ni toca el
filesystem, asi que ejercitarlo con manifiestos construidos a mano prueba la API real sin
depender de fixtures de carga.
"""

from __future__ import annotations

from resultarai.core.manifests import ManifestStatus, RoutingManifest
from resultarai.core.registries import ManifestRegistry


def _routing(manifest_id: str, status: ManifestStatus) -> RoutingManifest:
    return RoutingManifest(id=manifest_id, status=status, version="1.0.0", rules=[])


# 1. Consultar por status: active -> devuelve solo los activos, excluye draft y deprecated.


def test_by_status_active_excludes_draft_and_deprecated() -> None:
    registry = ManifestRegistry(
        [
            _routing("routing_active", ManifestStatus.ACTIVE),
            _routing("routing_draft", ManifestStatus.DRAFT),
            _routing("routing_deprecated", ManifestStatus.DEPRECATED),
        ]
    )

    result = registry.by_status(ManifestStatus.ACTIVE)

    assert [manifest.id for manifest in result] == ["routing_active"]


# 2. Consultar por status: deprecated -> devuelve los deprecados sin marcarlos invocables.


def test_by_status_deprecated_does_not_make_them_invocable() -> None:
    registry = ManifestRegistry(
        [
            _routing("routing_active", ManifestStatus.ACTIVE),
            _routing("routing_deprecated", ManifestStatus.DEPRECATED),
        ]
    )

    result = registry.by_status(ManifestStatus.DEPRECATED)

    assert [manifest.id for manifest in result] == ["routing_deprecated"]
    # Consultar por deprecated no lo reactiva: sigue sin ser invocable.
    assert registry.is_invocable("routing_deprecated") is False
    assert registry.get_invocable("routing_deprecated") is None
    assert [manifest.id for manifest in registry.invocable()] == ["routing_active"]


# 3. La consulta no muta el catalogo (operacion pura de lectura).


def test_by_status_query_does_not_mutate_the_catalog() -> None:
    registry = ManifestRegistry(
        [
            _routing("routing_active", ManifestStatus.ACTIVE),
            _routing("routing_draft", ManifestStatus.DRAFT),
            _routing("routing_deprecated", ManifestStatus.DEPRECATED),
        ]
    )

    before_len = len(registry)
    before_ids = {manifest.id for manifest in registry}
    before_statuses = {manifest.id: manifest.status for manifest in registry}

    # Varias consultas por distintos status, incluyendo repetidas.
    registry.by_status(ManifestStatus.ACTIVE)
    registry.by_status(ManifestStatus.DEPRECATED)
    registry.by_status(ManifestStatus.DRAFT)
    registry.by_status(ManifestStatus.VALIDATED)
    registry.by_status(ManifestStatus.ACTIVE)

    assert len(registry) == before_len
    assert {manifest.id for manifest in registry} == before_ids
    assert {manifest.id: manifest.status for manifest in registry} == before_statuses
    # El estado invocable tampoco cambio por haber consultado.
    assert [manifest.id for manifest in registry.invocable()] == ["routing_active"]


# 4. Consulta por un status sin manifests -> coleccion vacia sin error.


def test_by_status_with_no_matching_manifests_returns_empty_collection() -> None:
    registry = ManifestRegistry(
        [
            _routing("routing_active", ManifestStatus.ACTIVE),
        ]
    )

    result = registry.by_status(ManifestStatus.VALIDATED)

    assert result == ()

    empty_registry: ManifestRegistry[RoutingManifest] = ManifestRegistry([])
    assert empty_registry.by_status(ManifestStatus.ACTIVE) == ()
