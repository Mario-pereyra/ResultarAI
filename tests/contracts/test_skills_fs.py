"""Test de contrato: adapter de filesystem para paquetes Agent Skill.

Usa `tmp_path` para crear un paquete fixture y verifica que el adapter
devuelve metadata, cuerpo y recursos por separado.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from resultarai.adapters.skills_fs.loader import FilesystemSkillPackageAdapter

_SKILL_MD_CONTENT = """\
---
name: test-skill
description: A test skill for contract testing.
license: MIT
metadata:
  category: testing
allowed-tools:
  - example_echo
  - another_tool
---

# Test Skill

This is the body of the test skill.

## Usage

Use this for testing.
"""

_RESOURCE_CONTENT = """\
# Template

A reference template for testing.
"""


@pytest.fixture
def packages_dir(tmp_path: Path) -> Path:
    """Crea un paquete fixture en un directorio temporal."""
    pkg_dir = tmp_path / "test-skill"
    pkg_dir.mkdir()

    # SKILL.md
    (pkg_dir / "SKILL.md").write_text(_SKILL_MD_CONTENT, encoding="utf-8")

    # references/
    refs_dir = pkg_dir / "references"
    refs_dir.mkdir()
    (refs_dir / "template.md").write_text(_RESOURCE_CONTENT, encoding="utf-8")

    return tmp_path


@pytest.fixture
def adapter(packages_dir: Path) -> FilesystemSkillPackageAdapter:
    """Adapter configurado para el directorio de paquetes temporal."""
    return FilesystemSkillPackageAdapter(packages_dir=packages_dir)


class TestDiscover:
    """Descubrimiento de paquetes."""

    def test_discovers_package_with_skill_md(
        self, adapter: FilesystemSkillPackageAdapter, packages_dir: Path
    ) -> None:
        """Descubre subdirectorios que contienen SKILL.md."""
        result = adapter.discover(str(packages_dir))
        assert result == ["test-skill"]

    def test_ignores_directory_without_skill_md(
        self, adapter: FilesystemSkillPackageAdapter, packages_dir: Path
    ) -> None:
        """Ignora subdirectorios sin SKILL.md."""
        (packages_dir / "no-skill").mkdir()
        result = adapter.discover(str(packages_dir))
        assert result == ["test-skill"]

    def test_empty_directory(self, adapter: FilesystemSkillPackageAdapter, tmp_path: Path) -> None:
        """Directorio vacío retorna lista vacía."""
        empty = tmp_path / "empty"
        empty.mkdir()
        result = adapter.discover(str(empty))
        assert result == []

    def test_nonexistent_directory(
        self, adapter: FilesystemSkillPackageAdapter, tmp_path: Path
    ) -> None:
        """Directorio inexistente retorna lista vacía."""
        result = adapter.discover(str(tmp_path / "nonexistent"))
        assert result == []


class TestReadMetadata:
    """Lectura de metadata (frontmatter)."""

    def test_returns_frontmatter_dict(self, adapter: FilesystemSkillPackageAdapter) -> None:
        """Retorna los campos del frontmatter como diccionario."""
        metadata = adapter.read_metadata("test-skill")
        assert metadata["name"] == "test-skill"
        assert metadata["description"] == "A test skill for contract testing."
        assert metadata["license"] == "MIT"
        assert metadata["metadata"] == {"category": "testing"}
        assert metadata["allowed-tools"] == ["example_echo", "another_tool"]

    def test_metadata_does_not_contain_body(self, adapter: FilesystemSkillPackageAdapter) -> None:
        """La metadata no incluye el cuerpo Markdown."""
        metadata = adapter.read_metadata("test-skill")
        assert "# Test Skill" not in str(metadata.values())


class TestReadBody:
    """Lectura del cuerpo Markdown."""

    def test_returns_body_without_frontmatter(self, adapter: FilesystemSkillPackageAdapter) -> None:
        """Retorna el cuerpo sin el frontmatter YAML."""
        body = adapter.read_body("test-skill")
        assert "# Test Skill" in body
        assert "This is the body of the test skill." in body
        assert "---" not in body
        assert "name:" not in body


class TestReadResource:
    """Lectura de archivos de apoyo."""

    def test_reads_reference_file(self, adapter: FilesystemSkillPackageAdapter) -> None:
        """Lee un archivo desde `references/`."""
        content = adapter.read_resource("test-skill", "references/template.md")
        assert "# Template" in content
        assert "A reference template for testing." in content

    def test_rejects_invalid_resource_dir(self, adapter: FilesystemSkillPackageAdapter) -> None:
        """Rechaza rutas que no empiezan con references/, scripts/ o assets/."""
        with pytest.raises(ValueError, match="must start with one of"):
            adapter.read_resource("test-skill", "other/file.md")

    def test_rejects_path_traversal(
        self, adapter: FilesystemSkillPackageAdapter, packages_dir: Path
    ) -> None:
        """Rechaza intentos de path traversal."""
        # Create a file outside the package
        (packages_dir / "secret.txt").write_text("secret", encoding="utf-8")
        with pytest.raises((ValueError, FileNotFoundError)):
            adapter.read_resource("test-skill", "references/../../secret.txt")
