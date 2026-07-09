"""Tests del Agent Manifest: campos obligatorios + invariantes de la regla de oro.

Se valida con `model_validate` sobre un dict porque asi llega un Manifest en
produccion: YAML -> dict -> validacion. El fixture reproduce el ejemplo normativo
`default_chat` de docs/04-manifiestos.md.
"""

from typing import Any

import pytest
from pydantic import ValidationError

from resultarai.core.manifests.agent import AgentManifest


def _default_chat_payload(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": "default_chat",
        "name": "Chat por Defecto",
        "type": "default_orchestrator",
        "status": "active",
        "version": "1.0.0",
        "runtime": {
            "framework": "langgraph",
            "graph": "default_chat_graph",
        },
        "capabilities": {
            "can_answer_general_questions": True,
            "can_use_skills": True,
            "can_delegate_to_agents": False,
            "can_execute_tools_directly": False,
        },
        "enabled_skills": ["example_skill"],
        "tool_access_policy": {
            "mode": "deny_by_default",
            "allow_only_via_skills": True,
        },
        "limits": {
            "max_steps_per_task": 10,
            "max_cost_usd_per_task": 0.50,
        },
        "observability": {
            "provider": "langfuse",
            "trace_all_interactions": True,
            "log_skill_selection": True,
            "log_tool_calls": True,
            "log_model_calls": True,
            "log_costs": True,
        },
        "evals": {
            "status": "placeholder",
            "template": "agent_eval_template",
        },
    }
    data.update(overrides)
    return data


def test_conformant_default_chat_is_accepted() -> None:
    manifest = AgentManifest.model_validate(_default_chat_payload())

    assert manifest.id == "default_chat"
    assert manifest.capabilities.can_execute_tools_directly is False
    assert manifest.tool_access_policy.mode == "deny_by_default"
    assert manifest.enabled_skills == ["example_skill"]
    assert manifest.evals.template == "agent_eval_template"


def test_direct_tool_execution_rejected_citing_golden_rule() -> None:
    payload = _default_chat_payload()
    payload["capabilities"]["can_execute_tools_directly"] = True

    with pytest.raises(ValidationError) as exc_info:
        AgentManifest.model_validate(payload)

    message = str(exc_info.value)
    assert "can_execute_tools_directly" in message
    assert "regla de oro" in message
    assert "Tools solo via Skills" in message


def test_tool_access_policy_without_deny_by_default_rejected() -> None:
    payload = _default_chat_payload()
    payload["tool_access_policy"]["mode"] = "allow_all"

    with pytest.raises(ValidationError) as exc_info:
        AgentManifest.model_validate(payload)

    message = str(exc_info.value)
    assert "tool_access_policy.mode" in message
    assert "deny_by_default" in message


@pytest.mark.parametrize("missing_field", ["enabled_skills", "evals"])
def test_missing_required_field_rejected(missing_field: str) -> None:
    payload = _default_chat_payload()
    del payload[missing_field]

    with pytest.raises(ValidationError) as exc_info:
        AgentManifest.model_validate(payload)

    assert missing_field in str(exc_info.value)
