"""Tests del Skill Manifest: envoltorio de gobernanza de un paquete Agent Skill.

Se importa `SkillManifest` directamente del modulo (no del paquete `__init__`, que aun no lo
reexporta). Se valida con dicts porque asi llega un Manifest en produccion: YAML -> dict ->
validacion (los valores son strings, no miembros de enum).
"""

from typing import Any

import pytest
from pydantic import ValidationError

from resultarai.core.manifests.skill import ERP_SAFE_QUERY_API, SkillManifest


def _example_skill(**overrides: Any) -> dict[str, Any]:
    """Dict equivalente al YAML de ejemplo de docs/04-manifiestos.md (Skill Manifest)."""
    data: dict[str, Any] = {
        "id": "example_skill",
        "name": "Utilidades de Ejemplo",
        "status": "active",
        "version": "1.0.0",
        "description": (
            "Skill de ejemplo de fabrica: envuelve un paquete Agent Skill (SKILL.md) con "
            "utilidades genericas y expone, con gobernanza, sus tools permitidas."
        ),
        "skill_package": {
            "spec": "agent_skills",
            "ref": "example_utils",
            "path": "skills/example_utils/SKILL.md",
            "version": "1.0.0",
        },
        "execution": {
            "mode": "read_only",
            "graph": "default_skill_graph",
            "requires_human_approval": False,
        },
        "visibility": {"roles": ["admin", "tecnico", "funcional"]},
        "risk": {"level": "low"},
        "tools": ["example_echo"],
        "output_policy": {
            "summarize_results": True,
            "mask_sensitive_fields": True,
            "max_rows": 20,
        },
        "evals": {"status": "placeholder", "template": "skill_eval_template"},
    }
    data.update(overrides)
    return data


def test_accepts_example_skill_from_docs() -> None:
    manifest = SkillManifest.model_validate(_example_skill())

    assert manifest.id == "example_skill"
    assert manifest.skill_package.ref == "example_utils"
    assert manifest.execution.graph == "default_skill_graph"
    assert manifest.tools == ["example_echo"]
    assert manifest.visibility is not None
    assert manifest.visibility.roles == ["admin", "tecnico", "funcional"]
    assert manifest.retrieval is None  # ausente -> ningun comportamiento de recuperacion


def test_accepts_skill_without_optional_governance_blocks() -> None:
    payload = _example_skill()
    del payload["visibility"]
    del payload["risk"]

    manifest = SkillManifest.model_validate(payload)

    assert manifest.visibility is None
    assert manifest.risk is None


def test_rejects_empty_tools_list() -> None:
    with pytest.raises(ValidationError) as exc_info:
        SkillManifest.model_validate(_example_skill(tools=[]))

    assert "tools" in str(exc_info.value)


def test_rejects_missing_tools_field() -> None:
    payload = _example_skill()
    del payload["tools"]

    with pytest.raises(ValidationError) as exc_info:
        SkillManifest.model_validate(payload)

    assert "tools" in str(exc_info.value)


def test_rejects_field_that_duplicates_skill_md_content() -> None:
    # `instructions` es contenido del SKILL.md: el envoltorio no lo declara -> strict lo rechaza.
    with pytest.raises(ValidationError) as exc_info:
        SkillManifest.model_validate(_example_skill(instructions="Paso 1: hacer X"))

    assert "instructions" in str(exc_info.value)


def test_rejects_examples_field_that_duplicates_skill_md_content() -> None:
    with pytest.raises(ValidationError) as exc_info:
        SkillManifest.model_validate(_example_skill(examples=["ejemplo embebido"]))

    assert "examples" in str(exc_info.value)


def test_rejects_erp_skill_without_plan_then_execute_graph() -> None:
    # Skill que toca el ERP (target ERP Safe Query API) pero con graph NO plan-then-execute.
    erp_execution = {
        "mode": "read_only",
        "graph": "default_skill_graph",
        "requires_human_approval": False,
        "target": ERP_SAFE_QUERY_API,
    }

    with pytest.raises(ValidationError) as exc_info:
        SkillManifest.model_validate(_example_skill(execution=erp_execution))

    message = str(exc_info.value)
    assert "regla dura 7" in message


def test_accepts_erp_skill_with_plan_then_execute_graph() -> None:
    erp_execution = {
        "mode": "read_only",
        "graph": "plan_then_execute_graph",
        "requires_human_approval": True,
        "target": ERP_SAFE_QUERY_API,
    }

    manifest = SkillManifest.model_validate(_example_skill(execution=erp_execution))

    assert manifest.execution.target == ERP_SAFE_QUERY_API
    assert manifest.execution.graph == "plan_then_execute_graph"


def test_rejects_unknown_execution_key_by_strict_mode() -> None:
    bad_execution = {"mode": "read_only", "graph": "default_skill_graph", "surprise": True}

    with pytest.raises(ValidationError) as exc_info:
        SkillManifest.model_validate(_example_skill(execution=bad_execution))

    assert "surprise" in str(exc_info.value)
