"""Paquete de skill: modelo SkillPackage, validación y resolución de toolset.

Contiene el modelo Pydantic `SkillPackage` (frontmatter + body + resources de un
paquete Agent Skill conforme a la spec agentskills.io), las reglas de validación
(nombre, consistencia, presupuesto de metadata) y la función pura de intersección
de toolset (`resolve_executable_toolset`).

Todo este paquete es dominio puro (`core/`): sin I/O, sin frameworks, sin adapters.
"""

from resultarai.core.skills.package import SkillPackage
from resultarai.core.skills.toolset import resolve_executable_toolset
from resultarai.core.skills.validation import (
    SkillPackageValidationError,
    validate_metadata_budget,
    validate_name_consistency,
    validate_skill_name,
)

__all__ = [
    "SkillPackage",
    "SkillPackageValidationError",
    "resolve_executable_toolset",
    "validate_metadata_budget",
    "validate_name_consistency",
    "validate_skill_name",
]
