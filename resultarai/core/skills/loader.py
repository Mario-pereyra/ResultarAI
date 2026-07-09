"""Carga y validación fail-fast de paquetes Agent Skill + divulgación progresiva.

Funciones puras de orquestación que conectan el `SkillPackagePort` (adapter) con el
modelo `SkillPackage` (core) y las reglas de validación: cargan, validan y resuelven
el toolset de cada skill activa, y construyen el contexto progresivo de skills para
el agente.

Todas son funciones puras sobre datos ya cargados (el I/O lo hace el adapter que se
pasa por inyección). No importan adapters ni frameworks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from resultarai.core.manifests.base import ManifestStatus
from resultarai.core.skills.package import SkillPackage
from resultarai.core.skills.toolset import resolve_executable_toolset
from resultarai.core.skills.validation import (
    SkillPackageValidationError,
    validate_metadata_budget,
    validate_name_consistency,
    validate_skill_name,
)

if TYPE_CHECKING:
    from resultarai.core.manifests.agent import AgentManifest
    from resultarai.core.ports.skill_package import SkillPackagePort
    from resultarai.core.registries.loader import SkillRegistry

__all__ = [
    "SkillPackageLoadError",
    "build_skills_context",
    "load_level2_body",
    "load_level3_resource",
    "load_skill_packages",
    "resolve_agent_skillset",
]


class SkillPackageLoadError(Exception):
    """Un paquete Agent Skill referenciado por un Skill Manifest activo no es válido."""


def _build_package_from_metadata(
    metadata: dict[str, Any],
    body: str,
    resources: list[str],
) -> SkillPackage:
    """Construye un SkillPackage a partir de metadata del frontmatter.

    Mapea `allowed-tools` (con guión, formato YAML) a `allowed_tools` (underscore, Python).
    """
    # Normalize key: YAML uses `allowed-tools`, Python model uses `allowed_tools`
    normalized = dict(metadata)
    if "allowed-tools" in normalized:
        normalized["allowed_tools"] = normalized.pop("allowed-tools")

    return SkillPackage(
        name=normalized.get("name", ""),
        description=normalized.get("description", ""),
        license=normalized.get("license"),
        compatibility=normalized.get("compatibility"),
        metadata=normalized.get("metadata"),
        allowed_tools=normalized.get("allowed_tools", []),
        body=body,
        resources=resources,
    )


def load_skill_packages(
    skill_registry: SkillRegistry,
    package_port: SkillPackagePort,
    packages_dir: str,
) -> dict[str, SkillPackage]:
    """Carga y valida los paquetes de todas las skills activas.

    Para cada Skill Manifest con `status: active`, carga su paquete via el
    `SkillPackagePort` y ejecuta las validaciones de la spec. Si un paquete
    falta o es inválido, lanza `SkillPackageLoadError` (fail-fast).

    Retorna un dict `{skill_manifest_id: SkillPackage}`.
    """
    packages: dict[str, SkillPackage] = {}

    for skill_manifest in skill_registry:
        if skill_manifest.status != ManifestStatus.ACTIVE:
            continue

        ref = skill_manifest.skill_package.ref

        try:
            metadata = package_port.read_metadata(ref)
        except Exception as exc:
            raise SkillPackageLoadError(
                f"failed to read metadata for skill package {ref!r} "
                f"(referenced by Skill Manifest {skill_manifest.id!r}): {exc}"
            ) from exc

        try:
            body = package_port.read_body(ref)
        except Exception as exc:
            raise SkillPackageLoadError(
                f"failed to read body for skill package {ref!r} "
                f"(referenced by Skill Manifest {skill_manifest.id!r}): {exc}"
            ) from exc

        try:
            package = _build_package_from_metadata(metadata, body, resources=[])
        except Exception as exc:
            raise SkillPackageLoadError(
                f"invalid skill package {ref!r} "
                f"(referenced by Skill Manifest {skill_manifest.id!r}): {exc}"
            ) from exc

        # Run spec validations
        try:
            validate_skill_name(package.name)
            validate_name_consistency(
                package.name,
                directory_name=ref,
                manifest_ref=ref,
            )
            validate_metadata_budget(package.name, package.description)
        except SkillPackageValidationError as exc:
            raise SkillPackageLoadError(
                f"validation failed for skill package {ref!r} "
                f"(referenced by Skill Manifest {skill_manifest.id!r}): {exc}"
            ) from exc

        packages[skill_manifest.id] = package

    return packages


def resolve_agent_skillset(
    agent_manifest: AgentManifest,
    skill_registry: SkillRegistry,
    packages: dict[str, SkillPackage],
) -> dict[str, frozenset[str]]:
    """Resuelve el skillset/toolset fijo de un agente desde sus `enabled_skills`.

    Solo incluye skills que están en `enabled_skills`, tienen un Skill Manifest
    `active` en el registry, y tienen un paquete cargado. El resultado es inmutable
    por sesión (skillset fijo por versión de agente).

    Retorna `{skill_manifest_id: frozenset[tool_ids]}`.
    """
    skillset: dict[str, frozenset[str]] = {}

    for skill_id in agent_manifest.enabled_skills:
        skill_manifest = skill_registry.get_invocable(skill_id)
        if skill_manifest is None:
            continue

        package = packages.get(skill_id)
        if package is None:
            continue

        toolset = resolve_executable_toolset(
            package.allowed_tools,
            skill_manifest.tools,
        )
        skillset[skill_id] = toolset

    return skillset


def build_skills_context(
    agent_manifest: AgentManifest,
    skill_registry: SkillRegistry,
    packages: dict[str, SkillPackage],
) -> str:
    """Construye el contexto Nivel 1 para el system prompt del agente.

    Inyecta solo `name` + `description` de las skills activas habilitadas.
    NO incluye el cuerpo (body) de ningún SKILL.md — eso es Nivel 2.
    """
    lines: list[str] = []
    lines.append("Available skills:")

    for skill_id in agent_manifest.enabled_skills:
        package = packages.get(skill_id)
        if package is None:
            continue
        lines.append(f"- {package.name}: {package.description}")

    return "\n".join(lines)


def load_level2_body(
    package_port: SkillPackagePort,
    package_name: str,
) -> str:
    """Carga el cuerpo Markdown de un skill al activarla (Nivel 2).

    Invocado por el Skill Router al activar la skill, no precargado.
    """
    return package_port.read_body(package_name)


def load_level3_resource(
    package_port: SkillPackagePort,
    package_name: str,
    resource_path: str,
) -> str:
    """Carga un archivo de apoyo bajo demanda (Nivel 3).

    Invocado solo cuando el cuerpo referencia un recurso, no precargado.
    """
    return package_port.read_resource(package_name, resource_path)
