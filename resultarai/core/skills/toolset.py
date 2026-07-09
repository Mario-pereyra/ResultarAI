"""Resolución del toolset ejecutable de una skill.

Función pura que calcula la intersección entre los `allowed_tools` del paquete
(SKILL.md frontmatter) y los `tools` del Skill Manifest (envoltorio de gobernanza).
El resultado es el ÚNICO conjunto de tools que el runtime puede intentar ejecutar
para esa skill; cada intento pasa igualmente por el Policy Gate.
"""

from __future__ import annotations

from collections.abc import Sequence

__all__ = ["resolve_executable_toolset"]


def resolve_executable_toolset(
    package_allowed_tools: Sequence[str],
    manifest_tools: Sequence[str],
) -> frozenset[str]:
    """Calcula el toolset ejecutable como intersección de ambas listas.

    - `package_allowed_tools`: campo `allowed-tools` del frontmatter de SKILL.md.
    - `manifest_tools`: campo `tools` del Skill Manifest (allowlist de gobernanza).

    Retorna `frozenset` (inmutable, orden no garantizado) con los tool ids presentes
    en ambas listas. Si la intersección es vacía, retorna un frozenset vacío.
    """
    return frozenset(package_allowed_tools) & frozenset(manifest_tools)
