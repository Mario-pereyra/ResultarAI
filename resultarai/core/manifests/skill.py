"""Schema del Skill Manifest: envoltorio de gobernanza de un paquete Agent Skill.

El paquete real (carpeta con `SKILL.md` + frontmatter, progressive disclosure) NO vive
en el YAML: el manifiesto solo lo referencia por identificador y version (`skill_package`)
y aporta la capa que la spec oficial Agent Skills no cubre (riesgo, visibilidad, tools
permitidas del Tool Registry, plan-then-execute). El modo estricto heredado de
`BaseManifest` rechaza cualquier campo que duplique instrucciones o ejemplos del `SKILL.md`
(regla dura 6 y el MUST NOT de docs/04-manifiestos.md).
"""

from __future__ import annotations

import enum
from typing import Annotated, Final, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from resultarai.core.manifests.base import BaseManifest, EvalStatus, RiskLevel, SemVer

__all__ = [
    "ERP_SAFE_QUERY_API",
    "EvalStatus",
    "EvalsConfig",
    "ExecutionConfig",
    "ExecutionMode",
    "OutputPolicyConfig",
    "RetrievalConfig",
    "RiskConfig",
    "RiskLevel",
    "SkillManifest",
    "SkillPackage",
    "SkillPackageSpec",
    "VisibilityConfig",
]


# Identificador del Tool Registry: snake_case en ingles, no vacio (p. ej. `example_echo`).
_ToolId = Annotated[str, Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")]

# Backend del ERP: unica via permitida hacia el Protheus (regla dura 5, ERP Safe Query API).
# Una skill que declara este target "toca el ERP" y dispara la invariante plan-then-execute.
ERP_SAFE_QUERY_API: Final = "erp_safe_query_api"

# Prefijo del Graph Template que valida el plan antes de ejecutar (regla dura 7).
_PLAN_THEN_EXECUTE_PREFIX: Final = "plan_then_execute"


def _is_plan_then_execute(graph: str) -> bool:
    """True si el graph es un Graph Template plan-then-execute (plan validado antes de ejecutar)."""
    return graph.startswith(_PLAN_THEN_EXECUTE_PREFIX)


class SkillPackageSpec(enum.StrEnum):
    """Spec oficial del paquete referenciado. Solo Agent Skills (agentskills.io)."""

    AGENT_SKILLS = "agent_skills"


class ExecutionMode(enum.StrEnum):
    """Modo de ejecucion declarado de la skill."""

    READ_ONLY = "read_only"
    READ_WRITE = "read_write"


# Los enums llegan como strings desde YAML: strict=False admite solo valores del enum
# (sin coercion insegura), igual que el `status` de BaseManifest. El resto sigue estricto.
_SpecField = Annotated[SkillPackageSpec, Field(strict=False)]
_ModeField = Annotated[ExecutionMode, Field(strict=False)]
_RiskLevelField = Annotated[RiskLevel, Field(strict=False)]
_EvalStatusField = Annotated[EvalStatus, Field(strict=False)]


class _StrictModel(BaseModel):
    """Base estricta para los sub-modelos del Skill Manifest (rechaza claves desconocidas)."""

    model_config = ConfigDict(strict=True, extra="forbid")


class SkillPackage(_StrictModel):
    """Referencia (no copia) al paquete Agent Skill: spec, id del paquete, ruta y version."""

    spec: _SpecField
    ref: Annotated[str, Field(min_length=1)]
    path: Annotated[str, Field(min_length=1)]
    version: SemVer


class ExecutionConfig(_StrictModel):
    """Configuracion de ejecucion + invariante plan-then-execute para skills que tocan el ERP."""

    mode: _ModeField
    graph: Annotated[str, Field(min_length=1)]
    requires_human_approval: bool = False
    # Backend contra el que ejecuta la skill; ausente en las skills de fabrica genericas.
    # Cuando vale `erp_safe_query_api` la skill "toca el ERP" (regla dura 5).
    target: Annotated[str, Field(min_length=1)] | None = None

    @model_validator(mode="after")
    def _enforce_plan_then_execute_for_erp(self) -> Self:
        """Regla dura 7: si la skill toca el ERP, el graph debe ser plan-then-execute."""
        if self.target == ERP_SAFE_QUERY_API and not _is_plan_then_execute(self.graph):
            raise ValueError(
                "regla dura 7: una skill que toca el ERP "
                f"(execution.target: {ERP_SAFE_QUERY_API}) debe usar un graph plan-then-execute "
                "(plan validado antes de ejecutar); "
                f"execution.graph={self.graph!r} no es un graph plan-then-execute"
            )
        return self


class VisibilityConfig(_StrictModel):
    """Visibilidad por rol (capa de gobernanza que la spec Agent Skills no cubre)."""

    roles: Annotated[list[Annotated[str, Field(min_length=1)]], Field(min_length=1)]


class RiskConfig(_StrictModel):
    """Riesgo declarado de la skill."""

    level: _RiskLevelField


class OutputPolicyConfig(_StrictModel):
    """Politica de salida: resumen, enmascarado de campos sensibles y limite de filas."""

    summarize_results: bool
    mask_sensitive_fields: bool
    max_rows: Annotated[int, Field(gt=0)]


class EvalsConfig(_StrictModel):
    """Referencia al Eval Template de la skill (placeholder por diseno)."""

    status: _EvalStatusField
    template: Annotated[str, Field(min_length=1)]


class RetrievalConfig(_StrictModel):
    """Puerta abierta a RAG (docs/04-manifiestos.md, "Puerta abierta: retrieval"): metadato inerte.

    Sub-schema declarativo puro, sin comportamiento ni adapter asociado en este change: reserva
    el contrato para cuando exista `RetrievalPort` (diferido a `a03`; la implementacion real de
    RAG es Etapa P). Como `retrieval` es opcional en el manifiesto, su ausencia (None) no activa
    ningun comportamiento de recuperacion; su presencia tampoco invoca ningun adapter.

    Campos (bloque normativo de docs/04):
    - `enabled`: cuando llegue RAG (Etapa P) sera `true` + fuente indexada; hoy siempre inerte.
    - `source`: id de la coleccion/indice; `null` mientras no exista `RetrievalPort`.

    El modo estricto heredado de `_StrictModel` (`strict=True`, `extra="forbid"`) rechaza toda
    clave desconocida dentro del bloque.
    """

    enabled: bool = False
    source: str | None = None


class SkillManifest(BaseManifest):
    """Envoltorio de gobernanza de un paquete Agent Skill.

    Referencia el paquete por `skill_package` y anade la gobernanza (tools permitidas,
    ejecucion/plan-then-execute, visibilidad, riesgo, output policy, evals). No duplica el
    contenido del `SKILL.md`: el modo estricto heredado rechaza campos no declarados aqui.
    """

    name: Annotated[str, Field(min_length=1)]
    description: Annotated[str, Field(min_length=1)]
    skill_package: SkillPackage
    execution: ExecutionConfig
    # Allowlist explicita del Tool Registry: obligatoria y no vacia (cada skill declara sus tools).
    tools: Annotated[list[_ToolId], Field(min_length=1)]
    output_policy: OutputPolicyConfig
    evals: EvalsConfig
    visibility: VisibilityConfig | None = None
    risk: RiskConfig | None = None
    retrieval: RetrievalConfig | None = None
