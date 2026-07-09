"""Agent Manifest: contrato declarativo de un agente (ver docs/04-manifiestos.md).

Garantiza por invariante la REGLA DE ORO (regla dura 3): el Default Chat nunca
ejecuta Tools directamente. Un agente solo alcanza Tools via Skills aprobadas y
con `tool_access_policy.mode: deny_by_default`; el schema rechaza cualquier otra
configuracion antes de que el Manifest pueda cargarse.
"""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from resultarai.core.manifests.base import BaseManifest, ManifestId

__all__ = ["AgentManifest"]

# Valor unico admitido por la regla de oro; se valida por invariante (no como Literal)
# para poder emitir un mensaje que cite la regla, no un error de tipo generico.
_DENY_BY_DEFAULT = "deny_by_default"


class _StrictModel(BaseModel):
    """Sub-modelo estricto: rechaza claves desconocidas y coerciones implicitas."""

    model_config = ConfigDict(strict=True, extra="forbid")


class AgentRuntime(_StrictModel):
    framework: str
    graph: str


class AgentCapabilities(_StrictModel):
    can_answer_general_questions: bool
    can_use_skills: bool
    can_delegate_to_agents: bool
    can_execute_tools_directly: bool


class ToolAccessPolicy(_StrictModel):
    mode: str
    allow_only_via_skills: bool


class AgentLimits(_StrictModel):
    max_steps_per_task: int
    max_cost_usd_per_task: float


class AgentObservability(_StrictModel):
    provider: str
    trace_all_interactions: bool
    log_skill_selection: bool
    log_tool_calls: bool
    log_model_calls: bool
    log_costs: bool


class AgentEvals(_StrictModel):
    status: str
    template: ManifestId


class AgentManifest(BaseManifest):
    """Define un agente: proposito, runtime, skills habilitadas, limites y evals.

    Hereda `id`, `status`, `version` (y el modo estricto) de `BaseManifest`.
    """

    name: str
    type: str
    runtime: AgentRuntime
    capabilities: AgentCapabilities
    enabled_skills: list[ManifestId]
    tool_access_policy: ToolAccessPolicy
    observability: AgentObservability
    evals: AgentEvals
    limits: AgentLimits | None = None

    @model_validator(mode="after")
    def _enforce_golden_rule(self) -> Self:
        """Regla de oro (regla dura 3): Tools solo via Skills, deny-by-default."""
        if self.capabilities.can_execute_tools_directly:
            raise ValueError(
                "capabilities.can_execute_tools_directly must be false: viola la regla de oro "
                "(Tools solo via Skills; el Default Chat nunca ejecuta Tools directamente)"
            )
        if self.tool_access_policy.mode != _DENY_BY_DEFAULT:
            raise ValueError(
                f"tool_access_policy.mode must be {_DENY_BY_DEFAULT!r}: la regla de oro exige "
                f"deny-by-default (lo no permitido explicitamente esta bloqueado)"
            )
        return self
