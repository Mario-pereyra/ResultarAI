"""Grafo de transiciones del ciclo de vida de `status` (a02-core-manifiestos, tarea 2.3).

El ciclo de vida de un Manifest es `draft -> validated -> active -> deprecated`
(`docs/04-manifiestos.md`, "Ciclo de vida de un manifiesto"; `ManifestStatus` en
`manifests/base.py`). Este modulo codifica ese grafo como una funcion pura,
independiente de cualquier mecanismo de persistencia: dado un `status` de partida y uno
de llegada, dice si la transicion esta permitida.

**Por que una funcion pura y no historial persistido.** La tarea 2.3 solo pide que "la
operacion" de marcar `active` sin pasar por `validated` falle. Los Manifests de este
change viven en YAML y se cargan en memoria de forma inmutable (`ManifestRegistry` no
muta manifiestos, ver `registries/registry.py`): no existe todavia un mecanismo que
recuerde el `status` anterior de un Manifest entre una carga y la siguiente (eso exigiria
persistencia de historial, diferida a `b04`, "Git + Postgres"). Inventar esa persistencia
aqui se saldria del alcance de 2.3 y anticiparia una decision de `b04` sin evidencia.

En su lugar, `validate_status_transition` expone el grafo permitido como una funcion pura
que cualquier futuro punto de escritura de `status` puede llamar con el `status` que tenia
un Manifest y el que se le quiere asignar:

- Los builders que editaran manifiestos con conocimiento del `status` previo (`d21`,
  herramienta de autoria/edicion de manifiestos, fuera del alcance de a02) la usaran para
  rechazar una transicion invalida antes de escribir el YAML.
- El propio `ManifestRegistry` (`registries/registry.py`) no la necesita para el camino de
  solo-lectura de este change (carga YAML -> catalogo -> invocabilidad por `status`
  actual), porque no conoce el `status` anterior de un Manifest; queda documentada aqui
  como el punto de extension cuando el registro empiece a versionar o mutar manifiestos.

Esta funcion sola ya cubre el escenario 4 del requirement de ciclo de vida ("marcar como
`active` un Manifest que no ha pasado por `validated`"): se invoca con el `status` de
origen real (`draft`) y el de destino (`active`) y falla, sin necesitar que el propio
Manifest recuerde su historial.
"""

from __future__ import annotations

from resultarai.core.manifests.base import ManifestStatus

__all__ = [
    "ALLOWED_STATUS_TRANSITIONS",
    "InvalidStatusTransitionError",
    "validate_status_transition",
]

# Grafo del ciclo de vida: draft -> validated -> active -> deprecated, sin saltos hacia
# adelante (p. ej. draft -> active) ni hacia atras (p. ej. active -> validated). Un status
# sin salidas en el mapeo (deprecated) es terminal: el kill switch es la unica escritura que
# lo alcanza y no se revierte dentro de este grafo.
ALLOWED_STATUS_TRANSITIONS: dict[ManifestStatus, frozenset[ManifestStatus]] = {
    ManifestStatus.DRAFT: frozenset({ManifestStatus.VALIDATED}),
    ManifestStatus.VALIDATED: frozenset({ManifestStatus.ACTIVE}),
    ManifestStatus.ACTIVE: frozenset({ManifestStatus.DEPRECATED}),
    ManifestStatus.DEPRECATED: frozenset(),
}


class InvalidStatusTransitionError(ValueError):
    """`current -> new` no es una transicion permitida del ciclo de vida del Manifest.

    Cubre tanto saltos hacia adelante (`draft -> active` sin pasar por `validated`) como
    cualquier otro movimiento fuera del grafo (`ALLOWED_STATUS_TRANSITIONS`), incluyendo
    intentar salir de `deprecated` (estado terminal en este grafo).
    """

    def __init__(self, current: ManifestStatus, new: ManifestStatus) -> None:
        allowed_from_current = ALLOWED_STATUS_TRANSITIONS.get(current, frozenset())
        allowed = sorted(status.value for status in allowed_from_current)
        allowed_desc = ", ".join(allowed) if allowed else "ninguna (estado terminal)"
        message = (
            f"transicion de status no permitida: {current.value!r} -> {new.value!r} "
            f"(desde {current.value!r} solo se permite: {allowed_desc})"
        )
        super().__init__(message)
        self.current = current
        self.new = new


def validate_status_transition(current: ManifestStatus, new: ManifestStatus) -> None:
    """Valida que `current -> new` sea una transicion permitida del ciclo de vida.

    Operacion pura: no lee ni escribe ningun Manifest, solo consulta el grafo de
    `ALLOWED_STATUS_TRANSITIONS`. Lanza `InvalidStatusTransitionError` si la transicion no
    esta permitida (p. ej. `draft -> active` sin pasar por `validated`, o cualquier salida
    de `deprecated`).
    """
    if new not in ALLOWED_STATUS_TRANSITIONS.get(current, frozenset()):
        raise InvalidStatusTransitionError(current, new)
