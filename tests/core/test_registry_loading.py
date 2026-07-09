"""Tests del cargador YAML->schema y los Registries en memoria (a02-core-manifiestos, 2.1).

Escribe manifiestos de fixture con `yaml.safe_dump` sobre `tmp_path` (no depende de los
manifiestos de fabrica de la tarea 3.x, que aun no existen) y ejercita `load_registries`
contra ese directorio `manifests/` temporal. Los payloads reproducen los ejemplos
normativos ya cubiertos por `test_agent_manifest.py`, `test_skill_manifest.py`,
`test_tool_manifest.py` y `test_policy_routing_eval.py`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from resultarai.core.manifests import (
    AgentManifest,
    EvalTemplateManifest,
    PolicyManifest,
    RoutingManifest,
    SkillManifest,
    ToolManifest,
)
from resultarai.core.registries import (
    DuplicateManifestIdError,
    ManifestLoadError,
    load_registries,
)


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
        "description": "Skill de ejemplo para el test del loader de Registries.",
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


def _policy_payload(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": "example_read_only_policy",
        "status": "active",
        "version": "1.0.0",
        "applies_to": {"skills": ["example_skill"]},
        "rules": [{"effect": "allow", "when": {"operation_type": "read"}}],
    }
    data.update(overrides)
    return data


def _routing_payload(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": "default_chat_routing",
        "status": "active",
        "version": "1.0.0",
        "rules": [{"intent": "general_question", "action": "answer_directly"}],
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


# 1. Carga de manifiestos validos: cada Manifest queda catalogado y consultable por id.


def test_loads_valid_manifests_and_queries_by_id(tmp_path: Path) -> None:
    _write_manifest(tmp_path / "agents", "default_chat.yaml", _agent_payload())
    _write_manifest(tmp_path / "skills", "example_skill.yaml", _skill_payload())
    _write_manifest(tmp_path / "tools", "example_echo.yaml", _tool_payload())
    _write_manifest(tmp_path / "policies", "example_read_only_policy.yaml", _policy_payload())
    _write_manifest(tmp_path / "routing", "default_chat_routing.yaml", _routing_payload())
    _write_manifest(tmp_path / "evals", "skill_eval_template.yaml", _eval_payload())

    registries = load_registries(tmp_path)

    agent = registries.agents.get("default_chat")
    assert isinstance(agent, AgentManifest)
    assert agent.name == "Chat por Defecto"

    skill = registries.skills.get("example_skill")
    assert isinstance(skill, SkillManifest)

    tool = registries.tools.get("example_echo")
    assert isinstance(tool, ToolManifest)

    policy = registries.policies.get("example_read_only_policy")
    assert isinstance(policy, PolicyManifest)

    routing = registries.routing.get("default_chat_routing")
    assert isinstance(routing, RoutingManifest)

    evaluation = registries.evals.get("skill_eval_template")
    assert isinstance(evaluation, EvalTemplateManifest)

    assert len(registries.agents) == 1
    assert registries.agents.get("nonexistent") is None
    assert "default_chat" in registries.agents


def test_missing_subdirectory_yields_empty_registry(tmp_path: Path) -> None:
    # Un `manifests/` parcial (sin `evals/`, p. ej.) es valido: registry vacio, no error.
    _write_manifest(tmp_path / "agents", "default_chat.yaml", _agent_payload())

    registries = load_registries(tmp_path)

    assert len(registries.evals) == 0
    assert list(registries.evals) == []


# 2. Dos manifiestos del mismo tipo con el mismo id -> falla senalando el duplicado.


def test_duplicate_id_within_same_type_is_rejected(tmp_path: Path) -> None:
    _write_manifest(tmp_path / "skills", "example_skill.yaml", _skill_payload())
    _write_manifest(
        tmp_path / "skills",
        "example_skill_copy.yaml",
        _skill_payload(description="Copia con el mismo id, para forzar el duplicado."),
    )

    with pytest.raises(DuplicateManifestIdError) as exc_info:
        load_registries(tmp_path)

    assert "example_skill" in str(exc_info.value)
    assert exc_info.value.manifest_id == "example_skill"


# 3. YAML invalido detiene la carga del Registry nombrando el archivo y la causa.


def test_broken_yaml_syntax_fails_naming_the_file(tmp_path: Path) -> None:
    broken_path = tmp_path / "tools" / "broken.yaml"
    broken_path.parent.mkdir(parents=True)
    broken_path.write_text("id: [unclosed\n", encoding="utf-8")

    with pytest.raises(ManifestLoadError) as exc_info:
        load_registries(tmp_path)

    assert str(broken_path) in str(exc_info.value)


def test_schema_violation_fails_naming_the_file_and_the_cause(tmp_path: Path) -> None:
    invalid_payload = _tool_payload()
    del invalid_payload["security"]  # campo obligatorio del Tool Manifest
    path = _write_manifest(tmp_path / "tools", "invalid_tool.yaml", invalid_payload)

    with pytest.raises(ManifestLoadError) as exc_info:
        load_registries(tmp_path)

    message = str(exc_info.value)
    assert str(path) in message
    assert "security" in message
