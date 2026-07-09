"""Schema base compartido por los 6 Manifests declarativos.

Define los campos comunes (`id`, `status`, `version`) y las reglas de validacion
transversales. Todos los Manifests concretos (Agent, Skill, Tool, Policy, Routing,
Eval) heredan de `BaseManifest`, por lo que el modo estricto y el rechazo de campos
desconocidos aplican por igual a todos.
"""

from __future__ import annotations

import enum
import re
from typing import Annotated, Final

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

__all__ = [
    "BaseManifest",
    "EvalStatus",
    "ManifestStatus",
    "RiskLevel",
    "SemVer",
]


class RiskLevel(enum.StrEnum):
    """Nivel de riesgo declarado (glosario: Niveles de riesgo). Compartido por Skills y Tools."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EvalStatus(enum.StrEnum):
    """Estado del bloque de evals (principio 16: evals preparadas, no definidas).

    `placeholder`: espacio reservado, sin dataset real. `active`: dataset real y
    eval ejecutable (Etapa P / e25).
    """

    PLACEHOLDER = "placeholder"
    ACTIVE = "active"


class ManifestStatus(enum.StrEnum):
    """Ciclo de vida de un Manifest (ver docs/04-manifiestos.md).

    Orden del ciclo: draft -> validated -> active -> deprecated. El kill switch es
    cambiar el `status` (nunca borrar el Manifest), por trazabilidad.
    """

    DRAFT = "draft"
    VALIDATED = "validated"
    ACTIVE = "active"
    DEPRECATED = "deprecated"


# Semver estricto MAJOR.MINOR.PATCH sin ceros a la izquierda (p. ej. 1.0.0).
# No admite prefijos ("v1"), versiones parciales ("1.2") ni prerelease/build todavia.
_SEMVER_PATTERN: Final = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def _ensure_semver(value: str) -> str:
    """Valida el formato semver MAJOR.MINOR.PATCH con stdlib (sin dependencias)."""
    if not _SEMVER_PATTERN.match(value):
        raise ValueError(f"version must be semver MAJOR.MINOR.PATCH (e.g. '1.0.0'), got {value!r}")
    return value


# Tipo reutilizable: string validado como semver. Los 6 Manifests lo comparten.
SemVer = Annotated[str, AfterValidator(_ensure_semver)]

# Identificador en ingles, snake_case, no vacio (p. ej. `default_chat`, `example_echo`).
ManifestId = Annotated[str, Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")]

# El status acepta strings del YAML (strict=False solo aqui): un StrEnum en modo
# estricto global rechazaria "active"; con strict=False sigue admitiendo unicamente
# valores del enum, sin coercion insegura. El resto del modelo permanece estricto.
StatusField = Annotated[ManifestStatus, Field(strict=False)]


class BaseManifest(BaseModel):
    """Base comun de los 6 Manifests: campos compartidos + modo estricto.

    `strict=True` rechaza coerciones implicitas de tipo; `extra="forbid"` rechaza
    claves no declaradas (regla dura 6: sin manifiesto valido no existe).
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    id: ManifestId
    status: StatusField
    version: SemVer
