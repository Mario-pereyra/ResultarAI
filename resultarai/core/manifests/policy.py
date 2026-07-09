"""Policy Manifest: reglas declarativas que el Policy Gate evalua (docs/04-manifiestos.md).

Este Manifest es SOLO el contrato declarativo. La semantica deny-by-default (regla dura
4) la aplica el Policy Gate en runtime (change a03): toda operacion no cubierta por una
regla `allow`/`escalate_hitl` explicita queda implicitamente en `deny`. Aqui solo se
declara el conjunto de reglas y sus efectos permitidos; el schema no decide nada por si
mismo mas alla de validar la estructura y rechazar efectos fuera del conjunto.
"""

from __future__ import annotations

import enum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

from resultarai.core.manifests.base import BaseManifest, ManifestId

__all__ = ["PolicyEffect", "PolicyManifest", "PolicyRule"]


class PolicyEffect(enum.StrEnum):
    """Efectos declarables por una regla de Policy (docs/04-manifiestos.md).

    `allow` y `escalate_hitl` habilitan explicitamente; `deny` bloquea explicitamente.
    Todo lo no cubierto por una regla es `deny` implicito (deny-by-default, regla dura 4),
    resuelto por el Policy Gate en a03, no por este schema.
    """

    ALLOW = "allow"
    DENY = "deny"
    ESCALATE_HITL = "escalate_hitl"


# El effect acepta strings del YAML (strict=False local) manteniendo el resto estricto:
# un valor fuera de {allow, deny, escalate_hitl} produce un ValidationError que nombra
# el campo `effect` y los valores admitidos.
_EffectField = Annotated[PolicyEffect, Field(strict=False)]


class _StrictModel(BaseModel):
    """Sub-modelo estricto: rechaza claves desconocidas y coerciones implicitas."""

    model_config = ConfigDict(strict=True, extra="forbid")


class PolicyAppliesTo(_StrictModel):
    """Alcance de la Policy: a que Skills aplica (docs/04-manifiestos.md).

    En la Etapa P las condiciones multi-tenant del ERP viven en `PolicyRule.when`
    (p. ej. `tenant_in`), no aqui; la semantica deny-by-default no cambia.
    """

    skills: list[ManifestId] = Field(default_factory=list)


class PolicyRule(_StrictModel):
    """Una regla: un `effect` explicito bajo una condicion `when` declarativa.

    `when` es un mapa declarativo abierto (p. ej. `operation_type: read`,
    `risk_level: high`); el Policy Gate (a03) lo interpreta. Una regla sin `when`
    es un catch-all para ese efecto.
    """

    effect: _EffectField
    when: dict[str, Any] = Field(default_factory=dict)


class PolicyManifest(BaseManifest):
    """Reglas de ejecucion que evalua el Policy Gate; deny-by-default implicito.

    Hereda `id`, `status`, `version` (y el modo estricto) de `BaseManifest`.
    """

    applies_to: PolicyAppliesTo
    rules: list[PolicyRule]
