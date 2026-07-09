"""Tests de validacion de referencias cruzadas entre Manifests (a02-core-manifiestos, 2.2).

Ejercita el camino real: `load_registries` (no una funcion de validacion aislada), porque
la tarea 2.2 integra la validacion de referencias cruzadas ahi mismo (ver la decision
documentada en `resultarai/core/registries/cross_references.py` y en el docstring de
`load_registries`). Los payloads siguen el mismo estilo que `test_registry_loading.py`
(`yaml.safe_dump` sobre `tmp_path`), reproduciendo los ejemplos normativos de docs/04.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from resultarai.core.registries import DanglingReferenceError, load_registries


def _agent_payload(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": "default_chat",
        "name": "Chat por Defecto",
        "type": "default_orchestrator",
        "status": "active",
        "version": "1.0.0",
        "runtime": {"framework": "langgraph", "graph": "default_chat_graph"},
        "capabilities": {
            "can_answer_general_questions": True,
            "can_use_skills": True,
            "can_delegate_to_agents": False,
            "can_execute_tools_directly": False,
        },
        "enabled_skills": ["example_skill"],
        "tool_access_policy": {"mode": "deny_by_default", "allow_only_via_skills": True},
        "observability": {
            "provider": "langfuse",
            "trace_all_interactions": True,
            "log_skill_selection": True,
            "log_tool_calls": True,
            "log_model_calls": True,
            "log_costs": True,
        },
        "evals": {"status": "placeholder", "template": "agent_eval_template"},
    }
    data.update(overrides)
    return data


def _skill_payload(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": "example_skill",
        "name": "Utilidades de Ejemplo",
        "status": "active",
        "version": "1.0.0",
        "description": "Skill de ejemplo para los tests de referencias cruzadas.",
        "skill_package": {
            "spec": "agent_skills",
            "ref": "example_utils",
            "path": "skills/example_utils/SKILL.md",
            "version": "1.0.0",
        },
        "execution": {"mode": "read_only", "graph": "default_skill_graph"},
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


def _tool_payload(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": "example_echo",
        "name": "Echo de Ejemplo",
        "status": "active",
        "version": "1.0.0",
        "type": "mcp_tool",
        "adapter": "mcp",
        "mcp": {
            "server": "example_utils_server",
            "tool_name": "echo",
            "spec_revision": "2025-11-25",
            "endpoint_ref": "example_mcp_endpoint",
        },
        "risk": {"level": "low", "operation_type": "read"},
        "permissions": {"mode": "read_only", "requires_human_approval": False},
        "security": {
            "allow_sql_freeform": False,
            "allow_dynamic_table_access": False,
            "mask_sensitive_fields": True,
        },
        "audit": {
            "log_request": True,
            "log_response_summary": True,
            "log_user": True,
            "log_tenant": True,
        },
        "evals": {"status": "placeholder", "template": "tool_eval_template"},
    }
    data.update(overrides)
    return data


def _eval_payload(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": "skill_eval_template",
        "status": "placeholder",
        "version": "1.0.0",
        "target_kind": "skill",
        "metrics_planned": ["task_completion_rate"],
        "dataset": None,
    }
    data.update(overrides)
    return data


def _write_manifest(directory: Path, filename: str, payload: dict[str, Any]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


def _write_full_valid_set(tmp_path: Path) -> None:
    """Agent -> Skill active -> Tool active + los 3 Eval Templates que referencian."""
    _write_manifest(tmp_path / "agents", "default_chat.yaml", _agent_payload())
    _write_manifest(tmp_path / "skills", "example_skill.yaml", _skill_payload())
    _write_manifest(tmp_path / "tools", "example_echo.yaml", _tool_payload())
    _write_manifest(
        tmp_path / "evals",
        "agent_eval_template.yaml",
        _eval_payload(id="agent_eval_template", target_kind="agent"),
    )
    _write_manifest(tmp_path / "evals", "skill_eval_template.yaml", _eval_payload())
    _write_manifest(
        tmp_path / "evals",
        "tool_eval_template.yaml",
        _eval_payload(id="tool_eval_template", target_kind="tool"),
    )


# 1. Conjunto completo valido: Agent habilita una Skill active que declara Tools active y
#    una Eval Template existente -> los Registries se construyen y todo resuelve.


def test_full_valid_set_resolves_without_errors(tmp_path: Path) -> None:
    _write_full_valid_set(tmp_path)

    registries = load_registries(tmp_path)

    assert registries.agents.get("default_chat") is not None
    assert registries.skills.get("example_skill") is not None
    assert registries.tools.get("example_echo") is not None
    assert registries.evals.get("agent_eval_template") is not None
    assert registries.evals.get("skill_eval_template") is not None
    assert registries.evals.get("tool_eval_template") is not None


# 2. Skill -> Tool inexistente: falla citando la referencia colgante Skill->Tool.


def test_skill_referencing_nonexistent_tool_fails_citing_skill_to_tool(tmp_path: Path) -> None:
    _write_full_valid_set(tmp_path)
    # Sobrescribe la Skill para que declare una Tool que ningun Tool Manifest define.
    _write_manifest(
        tmp_path / "skills",
        "example_skill.yaml",
        _skill_payload(tools=["nonexistent_tool"]),
    )

    with pytest.raises(DanglingReferenceError) as exc_info:
        load_registries(tmp_path)

    message = str(exc_info.value)
    assert "Skill:example_skill" in message
    assert "Tool:nonexistent_tool" in message
    assert exc_info.value.field == "tools"


# 3. Agent habilita una Skill deprecated: solo Skills active son referenciables.


def test_agent_enabling_deprecated_skill_fails(tmp_path: Path) -> None:
    _write_full_valid_set(tmp_path)
    # La Skill pasa a `deprecated`; el Agent sigue habilitandola en `enabled_skills`.
    _write_manifest(tmp_path / "skills", "example_skill.yaml", _skill_payload(status="deprecated"))

    with pytest.raises(DanglingReferenceError) as exc_info:
        load_registries(tmp_path)

    message = str(exc_info.value)
    assert "Agent:default_chat" in message
    assert "Skill:example_skill" in message
    assert "deprecated" in message
    assert exc_info.value.field == "enabled_skills"


# 4. Skill -> Eval Template inexistente: falla nombrando la referencia colgante.


def test_skill_referencing_nonexistent_eval_template_fails(tmp_path: Path) -> None:
    _write_full_valid_set(tmp_path)
    # Sobrescribe la Skill para referenciar un Eval Template que no existe en `evals/`.
    _write_manifest(
        tmp_path / "skills",
        "example_skill.yaml",
        _skill_payload(evals={"status": "placeholder", "template": "nonexistent_eval_template"}),
    )

    with pytest.raises(DanglingReferenceError) as exc_info:
        load_registries(tmp_path)

    message = str(exc_info.value)
    assert "Skill:example_skill" in message
    assert "EvalTemplate:nonexistent_eval_template" in message
    assert exc_info.value.field == "evals.template"
