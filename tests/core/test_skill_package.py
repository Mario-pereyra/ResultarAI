"""Tests del modelo SkillPackage: construcción válida y fallos ante frontmatter incompleto."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from resultarai.core.skills.package import SkillPackage


class TestSkillPackageConstruction:
    """Construcción de un SkillPackage válido."""

    def test_valid_minimal_package(self) -> None:
        """Un paquete con solo los campos obligatorios se construye correctamente."""
        pkg = SkillPackage(name="my-skill", description="A test skill")
        assert pkg.name == "my-skill"
        assert pkg.description == "A test skill"
        assert pkg.license is None
        assert pkg.compatibility is None
        assert pkg.metadata is None
        assert pkg.allowed_tools == []
        assert pkg.body == ""
        assert pkg.resources == []

    def test_valid_full_package(self) -> None:
        """Un paquete con todos los campos se construye correctamente."""
        pkg = SkillPackage(
            name="report-formatting",
            description="Formats reports",
            license="MIT",
            compatibility="Generic, no ERP dependency",
            metadata={"category": "productivity"},
            allowed_tools=["example_echo", "another_tool"],
            body="# Report Formatting\n\nBody content here.",
            resources=["references/template.md"],
        )
        assert pkg.name == "report-formatting"
        assert pkg.allowed_tools == ["example_echo", "another_tool"]
        assert pkg.metadata == {"category": "productivity"}
        assert pkg.body.startswith("# Report Formatting")
        assert len(pkg.resources) == 1


class TestSkillPackageValidationFailures:
    """Fallos de validación Pydantic del modelo SkillPackage."""

    def test_missing_name_fails(self) -> None:
        """Frontmatter sin `name` falla."""
        with pytest.raises(ValidationError, match="name"):
            SkillPackage(description="A skill")  # type: ignore[call-arg]

    def test_missing_description_fails(self) -> None:
        """Frontmatter sin `description` falla."""
        with pytest.raises(ValidationError, match="description"):
            SkillPackage(name="my-skill")  # type: ignore[call-arg]

    def test_empty_name_fails(self) -> None:
        """`name` vacío falla por min_length."""
        with pytest.raises(ValidationError, match="name"):
            SkillPackage(name="", description="A skill")

    def test_name_too_long_fails(self) -> None:
        """`name` mayor a 64 chars falla."""
        with pytest.raises(ValidationError, match="name"):
            SkillPackage(name="a" * 65, description="A skill")

    def test_compatibility_too_long_fails(self) -> None:
        """`compatibility` mayor a 500 chars falla."""
        with pytest.raises(ValidationError, match="compatibility"):
            SkillPackage(
                name="my-skill",
                description="A skill",
                compatibility="x" * 501,
            )

    def test_extra_fields_forbidden(self) -> None:
        """Campos extra son rechazados (extra='forbid')."""
        with pytest.raises(ValidationError, match="extra"):
            SkillPackage(
                name="my-skill",
                description="A skill",
                unknown_field="value",  # type: ignore[call-arg]
            )

    def test_strict_mode_rejects_int_name(self) -> None:
        """strict=True rechaza tipos incorrectos (int en lugar de str)."""
        with pytest.raises(ValidationError):
            SkillPackage(name=123, description="A skill")  # type: ignore[arg-type]
