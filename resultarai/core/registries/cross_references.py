"""Validacion de referencias cruzadas entre Manifests (a02-core-manifiestos, tarea 2.2).

Cada uno de los 6 Registries carga y cataloga su propio tipo de Manifest de forma aislada
(tarea 2.1, `loader.py`): nada impide, a ese nivel, que un Agent habilite una Skill que no
existe o que una Skill declare una Tool nunca definida. Este modulo cierra esa brecha:
recorre los Registries ya construidos y valida que cada campo que un Manifest usa para
referenciar a otro ("enabled_skills" de un Agent, "tools" de una Skill, "evals.template" de
Agent/Skill/Tool, "applies_to.skills" de una Policy y el "target" de una regla de Routing)
resuelva a un Manifest que exista (requirement "Validacion de referencias cruzadas entre
Manifests", `openspec/changes/a02-core-manifiestos/specs/manifest-registries/spec.md`).

Es una pasada de solo lectura: no muta `registries`, no importa adapters, no ejecuta
ninguna Tool ni llama a ningun modelo (mismas restricciones que `loader.py`).

**Decision -- destino del `target` de Routing.** `RoutingRule` (ver `manifests/routing.py`)
tiene una unica accion que activa una Skill (`activate_skill`) y otra que delega en un
agente distinto (`delegate`); el propio docstring de ese modulo lo dice: "activa una Skill
(`activate_skill`) o delega en otro agente (`delegate`)". Por eso el mismo campo `target`
se valida contra Registries distintos segun la `action` de la regla: `activate_skill.target`
contra el `SkillRegistry`, `delegate.target` contra el `AgentRegistry`. `answer_directly` no
lleva `target` (ya lo garantiza el `model_validator` de `RoutingRule`) y no se valida aqui.

**Decision -- el Eval Template no exige `status: active`.** El requirement solo exige que el
`template` referenciado "exista como Eval Template"; no repite la exigencia general de
`active` para este caso. Ademas `EvalTemplateManifest` sobrescribe `status` con su propio
`EvalStatus` (`placeholder`/`active`, ver `manifests/eval.py`), un ciclo de vida distinto al
`ManifestStatus` (`draft/validated/active/deprecated`) del resto de Manifests: exigirle
`active` habria bloqueado el conjunto de fabrica, que referencia sus Eval Templates en
`status: placeholder` a proposito (principio 16: eval placeholder desde el dia uno, sin
dataset real). Las referencias a Agent/Skill/Tool si exigen `status: active`, siguiendo la
regla general del requirement ("referencia a un Manifest inexistente o no `active` ...
referencias colgantes prohibidas").

**Decision -- integracion en `load_registries`.** La spec dice que "la construccion del
Registry falla" ante una referencia colgante: no hay un estado intermedio valido en el que
existan Registries con referencias sin resolver. Por eso `load_registries` (`loader.py`)
llama a `validate_cross_references` antes de devolver `Registries`, en vez de exponer un
`load_and_validate_registries` separado que alguien pudiera omitir por error.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from resultarai.core.manifests.base import BaseManifest, ManifestStatus
from resultarai.core.manifests.routing import RoutingAction
from resultarai.core.registries.registry import ManifestRegistry

if TYPE_CHECKING:
    # Solo para anotaciones de tipo: `Registries` vive en `loader.py`, que importa este
    # modulo para llamar a `validate_cross_references`. Bajo `TYPE_CHECKING` no hay import
    # en tiempo de ejecucion, asi que no se forma un ciclo real entre los dos modulos.
    from resultarai.core.registries.loader import Registries

__all__ = ["DanglingReferenceError", "validate_cross_references"]


class DanglingReferenceError(ValueError):
    """Un Manifest referencia a otro que no existe o que existe pero no esta `active`.

    Nombra el origen y el destino de la referencia (p. ej. ``Skill:example_skill ->
    Tool:nonexistent_tool``), el campo que la declara y la razon puntual (destino
    inexistente, o existente con un `status` que no es `active`).
    """

    def __init__(self, *, origin: str, field: str, target: str, reason: str) -> None:
        message = f"{origin} -> {target} referencia colgante en {field!r}: {reason}"
        super().__init__(message)
        self.origin = origin
        self.field = field
        self.target = target
        self.reason = reason


def _resolve_active[M: BaseManifest](
    registry: ManifestRegistry[M],
    target_id: str,
    *,
    origin: str,
    field: str,
    target_kind: str,
) -> None:
    """El destino debe existir en `registry` y estar `active`; si no, dispara el error."""
    target = f"{target_kind}:{target_id}"
    manifest = registry.get(target_id)
    if manifest is None:
        raise DanglingReferenceError(
            origin=origin,
            field=field,
            target=target,
            reason=f"no existe ningun {target_kind} con id {target_id!r}",
        )
    if manifest.status != ManifestStatus.ACTIVE:
        raise DanglingReferenceError(
            origin=origin,
            field=field,
            target=target,
            reason=(
                f"{target_kind} {target_id!r} existe pero su status es "
                f"{manifest.status.value!r} (se requiere 'active')"
            ),
        )


def _resolve_exists[M: BaseManifest](
    registry: ManifestRegistry[M],
    target_id: str,
    *,
    origin: str,
    field: str,
    target_kind: str,
) -> None:
    """El destino debe existir en `registry`; a diferencia de `_resolve_active`, no exige
    ningun `status` puntual (usado solo para Eval Templates, ver decision en el modulo)."""
    if registry.get(target_id) is None:
        raise DanglingReferenceError(
            origin=origin,
            field=field,
            target=f"{target_kind}:{target_id}",
            reason=f"no existe ningun {target_kind} con id {target_id!r}",
        )


def validate_cross_references(registries: Registries) -> None:
    """Valida todas las referencias cruzadas de `registries`; lanza en la primera colgante.

    Operacion pura de lectura: no modifica ningun Registry. El orden de recorrido (Agent,
    Skill, Tool, Policy, Routing) es deterministico dentro de cada Registry (mismo orden de
    iteracion que `ManifestRegistry.__iter__`, que preserva el orden de insercion del dict
    interno) pero no esta pensado como contrato: el objetivo es fallar rapido citando origen,
    campo y destino, no acumular todos los errores del conjunto.
    """
    for agent in registries.agents:
        origin = f"Agent:{agent.id}"
        for skill_id in agent.enabled_skills:
            _resolve_active(
                registries.skills,
                skill_id,
                origin=origin,
                field="enabled_skills",
                target_kind="Skill",
            )
        _resolve_exists(
            registries.evals,
            agent.evals.template,
            origin=origin,
            field="evals.template",
            target_kind="EvalTemplate",
        )

    for skill in registries.skills:
        origin = f"Skill:{skill.id}"
        for tool_id in skill.tools:
            _resolve_active(
                registries.tools,
                tool_id,
                origin=origin,
                field="tools",
                target_kind="Tool",
            )
        _resolve_exists(
            registries.evals,
            skill.evals.template,
            origin=origin,
            field="evals.template",
            target_kind="EvalTemplate",
        )

    for tool in registries.tools:
        _resolve_exists(
            registries.evals,
            tool.evals.template,
            origin=f"Tool:{tool.id}",
            field="evals.template",
            target_kind="EvalTemplate",
        )

    for policy in registries.policies:
        origin = f"Policy:{policy.id}"
        for skill_id in policy.applies_to.skills:
            _resolve_active(
                registries.skills,
                skill_id,
                origin=origin,
                field="applies_to.skills",
                target_kind="Skill",
            )

    for routing in registries.routing:
        origin = f"Routing:{routing.id}"
        for rule in routing.rules:
            if rule.action == RoutingAction.ACTIVATE_SKILL and rule.target is not None:
                _resolve_active(
                    registries.skills,
                    rule.target,
                    origin=origin,
                    field="rules[].target (activate_skill)",
                    target_kind="Skill",
                )
            elif rule.action == RoutingAction.DELEGATE and rule.target is not None:
                _resolve_active(
                    registries.agents,
                    rule.target,
                    origin=origin,
                    field="rules[].target (delegate)",
                    target_kind="Agent",
                )
