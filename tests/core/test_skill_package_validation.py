"""Tests de validación del paquete Agent Skill: los 4 escenarios de rechazo de la spec."""

from __future__ import annotations

import pytest

from resultarai.core.skills.validation import (
    SkillPackageValidationError,
    validate_metadata_budget,
    validate_name_consistency,
    validate_skill_name,
)


class TestValidateSkillName:
    """Formato de `name`: 1-64, minúsculas/dígitos/guiones, sin guion inicial/final/dobles."""

    def test_valid_names(self) -> None:
        """Nombres válidos no lanzan error."""
        valid_names = [
            "a",
            "my-skill",
            "report-formatting",
            "skill123",
            "a-b-c",
            "x" * 64,
            "abc",
            "a1b2c3",
        ]
        for name in valid_names:
            validate_skill_name(name)  # No exception

    def test_empty_name_rejected(self) -> None:
        """Nombre vacío es rechazado."""
        with pytest.raises(SkillPackageValidationError, match="must not be empty"):
            validate_skill_name("")

    def test_name_too_long_rejected(self) -> None:
        """Nombre mayor a 64 chars es rechazado."""
        with pytest.raises(SkillPackageValidationError, match="exceeds 64 characters"):
            validate_skill_name("a" * 65)

    def test_leading_hyphen_rejected(self) -> None:
        """Guion inicial es rechazado."""
        with pytest.raises(SkillPackageValidationError, match="starts with a hyphen"):
            validate_skill_name("-my-skill")

    def test_trailing_hyphen_rejected(self) -> None:
        """Guion final es rechazado."""
        with pytest.raises(SkillPackageValidationError, match="ends with a hyphen"):
            validate_skill_name("my-skill-")

    def test_consecutive_hyphens_rejected(self) -> None:
        """Guiones consecutivos son rechazados."""
        with pytest.raises(SkillPackageValidationError, match="consecutive hyphens"):
            validate_skill_name("my--skill")

    def test_uppercase_rejected(self) -> None:
        """Mayúsculas son rechazadas."""
        with pytest.raises(SkillPackageValidationError, match="invalid characters"):
            validate_skill_name("My-Skill")

    def test_underscores_rejected(self) -> None:
        """Guiones bajos son rechazados."""
        with pytest.raises(SkillPackageValidationError, match="invalid characters"):
            validate_skill_name("my_skill")

    def test_spaces_rejected(self) -> None:
        """Espacios son rechazados."""
        with pytest.raises(SkillPackageValidationError, match="invalid characters"):
            validate_skill_name("my skill")


class TestValidateNameConsistency:
    """El `name`, directorio y referencia del Skill Manifest deben coincidir."""

    def test_all_match(self) -> None:
        """Cuando los tres coinciden no hay error."""
        validate_name_consistency("my-skill", "my-skill", "my-skill")

    def test_name_differs_from_directory(self) -> None:
        """Nombre difiere del directorio."""
        with pytest.raises(SkillPackageValidationError, match="directory name"):
            validate_name_consistency("my-skill", "other-dir", "my-skill")

    def test_name_differs_from_manifest_ref(self) -> None:
        """Nombre difiere de la referencia del manifiesto."""
        with pytest.raises(SkillPackageValidationError, match="manifest ref"):
            validate_name_consistency("my-skill", "my-skill", "other-ref")

    def test_all_three_differ(self) -> None:
        """Los tres difieren."""
        with pytest.raises(SkillPackageValidationError, match="inconsistency"):
            validate_name_consistency("name-a", "name-b", "name-c")


class TestValidateMetadataBudget:
    """El presupuesto de metadata de descubrimiento (name + description)."""

    def test_within_budget(self) -> None:
        """Dentro del presupuesto no hay error."""
        validate_metadata_budget("my-skill", "A short description")

    def test_exactly_at_budget(self) -> None:
        """Exactamente en el límite no hay error."""
        name = "a" * 10
        desc = "b" * 490
        validate_metadata_budget(name, desc, max_chars=500)

    def test_exceeds_budget(self) -> None:
        """Excede el presupuesto."""
        with pytest.raises(SkillPackageValidationError, match="budget exceeded"):
            validate_metadata_budget("a" * 10, "b" * 491, max_chars=500)

    def test_custom_budget(self) -> None:
        """Presupuesto personalizado."""
        with pytest.raises(SkillPackageValidationError, match="maximum is 100 chars"):
            validate_metadata_budget("skill", "x" * 97, max_chars=100)

    def test_actionable_error_message(self) -> None:
        """El mensaje de error es accionable."""
        with pytest.raises(SkillPackageValidationError, match="Shorten"):
            validate_metadata_budget("a" * 250, "b" * 260, max_chars=500)
