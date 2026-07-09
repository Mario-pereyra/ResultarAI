"""Adapter de filesystem que implementa SkillPackagePort.

Recorre `manifests/skills/packages/`, separa frontmatter YAML del cuerpo Markdown
en cada `SKILL.md`, y lee archivos de apoyo bajo `references/`, `scripts/` y
`assets/` bajo demanda.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

__all__ = ["FilesystemSkillPackageAdapter"]

# Subdirectorios permitidos para archivos de apoyo (Nivel 3).
_ALLOWED_RESOURCE_DIRS = frozenset({"references", "scripts", "assets"})


def _split_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Separa el frontmatter YAML (entre `---`) del cuerpo Markdown.

    Retorna (frontmatter_dict, body_string). Si no hay frontmatter válido,
    retorna ({}, content).
    """
    stripped = content.lstrip()
    if not stripped.startswith("---"):
        return {}, content

    # Find the closing ---
    end_idx = stripped.find("---", 3)
    if end_idx == -1:
        return {}, content

    frontmatter_text = stripped[3:end_idx]
    body = stripped[end_idx + 3 :].lstrip("\n")

    parsed = yaml.safe_load(frontmatter_text)
    if not isinstance(parsed, dict):
        return {}, content

    return parsed, body


class FilesystemSkillPackageAdapter:
    """Implementación de SkillPackagePort sobre el filesystem local.

    Satisface el protocolo `SkillPackagePort` de `core/ports/` sin que `core/`
    conozca esta clase ni importe nada de `adapters/`.
    """

    def __init__(self, packages_dir: Path) -> None:
        self._packages_dir = packages_dir

    def discover(self, packages_dir: str) -> list[str]:
        """Lista los paquetes disponibles (subdirectorios que contienen SKILL.md)."""
        base = Path(packages_dir)
        if not base.is_dir():
            return []

        return sorted(
            entry.name
            for entry in base.iterdir()
            if entry.is_dir() and (entry / "SKILL.md").is_file()
        )

    def read_metadata(self, package_name: str) -> dict[str, Any]:
        """Lee solo el frontmatter YAML de SKILL.md."""
        skill_md = self._packages_dir / package_name / "SKILL.md"
        content = skill_md.read_text(encoding="utf-8")
        frontmatter, _ = _split_frontmatter(content)
        return frontmatter

    def read_body(self, package_name: str) -> str:
        """Lee solo el cuerpo Markdown de SKILL.md (después del frontmatter)."""
        skill_md = self._packages_dir / package_name / "SKILL.md"
        content = skill_md.read_text(encoding="utf-8")
        _, body = _split_frontmatter(content)
        return body

    def read_resource(self, package_name: str, resource_path: str) -> str:
        """Lee un archivo de apoyo del paquete.

        Solo permite leer desde subdirectorios `references/`, `scripts/` o `assets/`.
        """
        resource = Path(resource_path)
        parts = resource.parts
        if not parts or parts[0] not in _ALLOWED_RESOURCE_DIRS:
            msg = (
                f"resource path {resource_path!r} must start with one of "
                f"{sorted(_ALLOWED_RESOURCE_DIRS)}"
            )
            raise ValueError(msg)

        full_path = self._packages_dir / package_name / resource_path
        # Prevent path traversal
        resolved = full_path.resolve()
        package_root = (self._packages_dir / package_name).resolve()
        if not str(resolved).startswith(str(package_root)):
            msg = f"resource path {resource_path!r} escapes package directory"
            raise ValueError(msg)

        return full_path.read_text(encoding="utf-8")
