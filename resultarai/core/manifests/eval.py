"""Eval Template Manifest: Eval Placeholder obligatorio (docs/04-manifiestos.md).

Reserva el espacio de evaluacion desde el dia uno (blueprint, principio 16) sin exigir
datasets reales todavia: admite `status: placeholder` y `dataset: null`.

Conflicto de `status` resuelto: `BaseManifest.status` modela el ciclo de vida
draft/validated/active/deprecated, pero el Eval Template de docs/04 usa
`status: placeholder`, que NO pertenece a ese ciclo. Por eso este Manifest hereda de
`BaseManifest` (para conservar `id`, `version` semver y el modo estricto) pero
**sobrescribe** el campo `status` con su propio enum `EvalStatus`, que incluye
`placeholder`. Asi se es fiel a docs/04 y al requirement (que exige admitir
`status: placeholder`) sin contaminar el ciclo de vida de los otros 5 Manifests.
"""

from __future__ import annotations

import enum
from typing import Annotated

from pydantic import Field

from resultarai.core.manifests.base import BaseManifest, EvalStatus

__all__ = ["EvalStatus", "EvalTargetKind", "EvalTemplateManifest"]


class EvalTargetKind(enum.StrEnum):
    """Que clase de Manifest evalua esta plantilla (docs/04-manifiestos.md)."""

    AGENT = "agent"
    SKILL = "skill"
    TOOL = "tool"


# Ambos enums aceptan strings del YAML (strict=False local) manteniendo el resto
# estricto; un valor fuera del conjunto produce un ValidationError que nombra el campo.
_EvalStatusField = Annotated[EvalStatus, Field(strict=False)]
_EvalTargetKindField = Annotated[EvalTargetKind, Field(strict=False)]


class EvalTemplateManifest(BaseManifest):
    """Eval Placeholder: reserva la evaluacion sin dataset real.

    Hereda `id` y `version` semver (y el modo estricto) de `BaseManifest`, pero
    sobrescribe `status` con `EvalStatus` para admitir `placeholder`.
    """

    # Override intencional: el Eval Template usa `placeholder`, ajeno al ciclo de vida
    # ManifestStatus de la base. mypy avisa del cambio de tipo del campo heredado; es
    # deliberado y Pydantic lo soporta (redeclaracion de campo con enum propio).
    status: _EvalStatusField  # type: ignore[assignment]
    target_kind: _EvalTargetKindField
    metrics_planned: list[str]
    dataset: str | None = None
