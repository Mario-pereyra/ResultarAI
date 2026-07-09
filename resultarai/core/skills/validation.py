"""Reglas de validación del paquete Agent Skill (spec agentskills.io).

Cada función valida un aspecto del paquete y lanza `SkillPackageValidationError`
con un mensaje accionable si la validación falla. Las reglas cubren:

1. Formato de `name`: 1-64 chars, minúsculas + dígitos + guiones, sin guion
   inicial/final ni guiones consecutivos.
2. Consistencia de nombre: `name` == nombre del directorio == referencia del
   Skill Manifest (`skill_package.ref`).
3. Presupuesto de metadata de descubrimiento: `name` + `description` no deben
   exceder un tope configurable (guía de ~100 tokens → 500 chars por defecto).
"""

from __future__ import annotations

import re

__all__ = [
    "SkillPackageValidationError",
    "validate_metadata_budget",
    "validate_name_consistency",
    "validate_skill_name",
]

# Regex: 1-64 chars, lowercase a-z / digits / hyphens, no leading/trailing/consecutive hyphens.
_NAME_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9]|-(?=[a-z0-9])){0,62}[a-z0-9]?$")


class SkillPackageValidationError(ValueError):
    """El paquete Agent Skill no cumple una regla de validación de la spec."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def validate_skill_name(name: str) -> None:
    """Valida el formato de `name` conforme a la spec.

    Reglas: 1-64 caracteres, solo minúsculas (a-z), dígitos (0-9) y guiones (-);
    sin guion inicial, sin guion final, sin guiones consecutivos.
    """
    if not name:
        raise SkillPackageValidationError(
            "skill package name must not be empty: "
            "provide a name with 1-64 lowercase alphanumeric characters and hyphens"
        )

    if len(name) > 64:
        raise SkillPackageValidationError(
            f"skill package name {name!r} exceeds 64 characters (got {len(name)}): "
            "shorten the name to at most 64 characters"
        )

    if not _NAME_PATTERN.match(name):
        reasons: list[str] = []
        if name.startswith("-"):
            reasons.append("starts with a hyphen")
        if name.endswith("-"):
            reasons.append("ends with a hyphen")
        if "--" in name:
            reasons.append("contains consecutive hyphens")
        if re.search(r"[^a-z0-9-]", name):
            reasons.append("contains invalid characters (only lowercase a-z, 0-9, and hyphens)")

        detail = "; ".join(reasons) if reasons else "invalid format"
        raise SkillPackageValidationError(
            f"skill package name {name!r} is invalid: {detail}. "
            "Use 1-64 lowercase alphanumeric characters and single hyphens (not at start/end)"
        )


def validate_name_consistency(
    name: str,
    directory_name: str,
    manifest_ref: str,
) -> None:
    """Valida que el `name` del frontmatter, el nombre del directorio y la referencia
    del Skill Manifest (`skill_package.ref`) coincidan.
    """
    mismatches: list[str] = []
    if name != directory_name:
        mismatches.append(f"frontmatter name {name!r} != directory name {directory_name!r}")
    if name != manifest_ref:
        mismatches.append(f"frontmatter name {name!r} != manifest ref {manifest_ref!r}")

    if mismatches:
        raise SkillPackageValidationError(
            f"skill package name inconsistency: {'; '.join(mismatches)}. "
            "The frontmatter name, directory name, and manifest skill_package.ref must all match"
        )


def validate_metadata_budget(
    name: str,
    description: str,
    *,
    max_chars: int = 500,
) -> None:
    """Valida que la metadata de descubrimiento (name + description) no exceda el tope.

    El tope por defecto (500 chars) responde a la guía de ~100 tokens de la spec.
    """
    total = len(name) + len(description)
    if total > max_chars:
        raise SkillPackageValidationError(
            f"discovery metadata budget exceeded: name ({len(name)} chars) + "
            f"description ({len(description)} chars) = {total} chars, "
            f"but maximum is {max_chars} chars. "
            "Shorten the name or description to fit within the budget"
        )
