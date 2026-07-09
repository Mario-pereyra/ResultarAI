"""Routing Manifest: reglas del Skill Router (docs/04-manifiestos.md).

Declara, por intent, si el Default Chat responde directo (`answer_directly`), activa una
Skill (`activate_skill`) o delega en otro agente (`delegate`). Es solo el contrato
declarativo; la decision real de enrutado es del Skill Router en runtime. Una `action`
fuera del conjunto permitido produce un error que la nombra.
"""

from __future__ import annotations

import enum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from resultarai.core.manifests.base import BaseManifest, ManifestId

__all__ = ["RoutingAction", "RoutingManifest", "RoutingRule"]


class RoutingAction(enum.StrEnum):
    """Acciones que una regla de Routing puede ordenar (docs/04-manifiestos.md)."""

    ANSWER_DIRECTLY = "answer_directly"
    ACTIVATE_SKILL = "activate_skill"
    DELEGATE = "delegate"


# La action acepta strings del YAML (strict=False local); un valor fuera de
# {answer_directly, activate_skill, delegate} produce un ValidationError que nombra la
# accion invalida y el conjunto admitido.
_ActionField = Annotated[RoutingAction, Field(strict=False)]

# Acciones que exigen un `target` (a que Skill o agente dirigirse).
_ACTIONS_REQUIRING_TARGET = frozenset({RoutingAction.ACTIVATE_SKILL, RoutingAction.DELEGATE})


class RoutingRule(BaseModel):
    """Una regla del Skill Router: para un `intent`, que `action` tomar.

    `target` (id de la Skill o agente) es obligatorio para `activate_skill` y
    `delegate`, y debe ausentarse en `answer_directly`; el schema lo valida por
    invariante. `note` es una anotacion declarativa opcional.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    intent: str
    action: _ActionField
    target: ManifestId | None = None
    note: str | None = None

    @model_validator(mode="after")
    def _enforce_target_consistency(self) -> Self:
        """Coherencia target/action: solo activate_skill y delegate llevan target."""
        needs_target = self.action in _ACTIONS_REQUIRING_TARGET
        if needs_target and self.target is None:
            raise ValueError(
                f"action {self.action.value!r} requires a 'target' (id de la Skill o agente)"
            )
        if not needs_target and self.target is not None:
            raise ValueError(f"action {self.action.value!r} must not declare a 'target'")
        return self


class RoutingManifest(BaseManifest):
    """Reglas del Skill Router: cuando responder directo, activar Skill o delegar.

    Hereda `id`, `status`, `version` (y el modo estricto) de `BaseManifest`.
    """

    rules: list[RoutingRule]
