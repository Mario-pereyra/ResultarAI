"""Tests de Policy, Routing y Eval Template Manifests (a02-core-manifiestos, tarea 1.5).

Se importa directo de cada modulo (no via `__init__`) y se valida con `model_validate`
sobre dicts equivalentes a los ejemplos YAML normativos de docs/04-manifiestos.md.
"""

from typing import Any

import pytest
from pydantic import ValidationError

from resultarai.core.manifests.eval import EvalStatus, EvalTemplateManifest
from resultarai.core.manifests.policy import PolicyEffect, PolicyManifest
from resultarai.core.manifests.routing import RoutingAction, RoutingManifest


def _policy_payload() -> dict[str, Any]:
    """Ejemplo `example_read_only_policy` de docs/04, seccion Policy Manifest."""
    return {
        "id": "example_read_only_policy",
        "status": "active",
        "version": "1.0.0",
        "applies_to": {"skills": ["example_skill"]},
        "rules": [
            {"effect": "allow", "when": {"operation_type": "read"}},
            {"effect": "escalate_hitl", "when": {"risk_level": "high"}},
        ],
    }


def _routing_payload() -> dict[str, Any]:
    """Ejemplo `default_chat_routing` de docs/04, seccion Routing Manifest."""
    return {
        "id": "default_chat_routing",
        "status": "active",
        "version": "1.0.0",
        "rules": [
            {"intent": "example_task", "action": "activate_skill", "target": "example_skill"},
            {"intent": "general_question", "action": "answer_directly"},
            {
                "intent": "unknown",
                "action": "answer_directly",
                "note": "nunca inventar acceso a datos; declarar que no se tiene la capacidad",
            },
        ],
    }


def _eval_payload() -> dict[str, Any]:
    """Ejemplo `skill_eval_template` de docs/04, seccion Eval Template Manifest."""
    return {
        "id": "skill_eval_template",
        "status": "placeholder",
        "version": "1.0.0",
        "target_kind": "skill",
        "metrics_planned": ["task_completion_rate", "tool_call_accuracy", "groundedness_score"],
        "dataset": None,
    }


# 1. Los 3 ejemplos validos de docs/04 se aceptan tal cual.


def test_policy_example_from_docs_is_accepted() -> None:
    policy = PolicyManifest.model_validate(_policy_payload())

    assert policy.id == "example_read_only_policy"
    assert policy.applies_to.skills == ["example_skill"]
    assert [rule.effect for rule in policy.rules] == [
        PolicyEffect.ALLOW,
        PolicyEffect.ESCALATE_HITL,
    ]
    assert policy.rules[0].when == {"operation_type": "read"}


def test_routing_example_from_docs_is_accepted() -> None:
    routing = RoutingManifest.model_validate(_routing_payload())

    assert routing.id == "default_chat_routing"
    assert routing.rules[0].action is RoutingAction.ACTIVATE_SKILL
    assert routing.rules[0].target == "example_skill"
    assert routing.rules[1].action is RoutingAction.ANSWER_DIRECTLY
    assert routing.rules[1].target is None


def test_eval_example_from_docs_is_accepted() -> None:
    template = EvalTemplateManifest.model_validate(_eval_payload())

    assert template.id == "skill_eval_template"
    assert template.status is EvalStatus.PLACEHOLDER
    assert template.dataset is None
    assert "groundedness_score" in template.metrics_planned


# 2. effect fuera de {allow, deny, escalate_hitl} se rechaza.


def test_policy_rejects_unknown_effect() -> None:
    payload = _policy_payload()
    payload["rules"][0]["effect"] = "permit"

    with pytest.raises(ValidationError) as exc_info:
        PolicyManifest.model_validate(payload)

    assert "effect" in str(exc_info.value)


def test_policy_accepts_deny_effect() -> None:
    payload = _policy_payload()
    payload["rules"].append({"effect": "deny", "when": {"operation_type": "write"}})

    policy = PolicyManifest.model_validate(payload)

    assert policy.rules[-1].effect is PolicyEffect.DENY


# 3. action fuera de {answer_directly, activate_skill, delegate} se rechaza.


def test_routing_rejects_unknown_action() -> None:
    payload = _routing_payload()
    payload["rules"][1]["action"] = "ignore"

    with pytest.raises(ValidationError) as exc_info:
        RoutingManifest.model_validate(payload)

    assert "action" in str(exc_info.value)


def test_routing_activate_skill_requires_target() -> None:
    payload = _routing_payload()
    del payload["rules"][0]["target"]

    with pytest.raises(ValidationError) as exc_info:
        RoutingManifest.model_validate(payload)

    assert "target" in str(exc_info.value)


# 4. Eval Template con status: placeholder y dataset: null se acepta.


def test_eval_placeholder_with_null_dataset_is_accepted() -> None:
    template = EvalTemplateManifest.model_validate(
        {
            "id": "tool_eval_template",
            "status": "placeholder",
            "version": "1.0.0",
            "target_kind": "tool",
            "metrics_planned": ["latency_ms"],
            "dataset": None,
        }
    )

    assert template.status is EvalStatus.PLACEHOLDER
    assert template.dataset is None


def test_eval_rejects_lifecycle_status_from_base() -> None:
    # El status del ciclo de vida (draft/validated/deprecated) NO aplica al Eval Template.
    payload = _eval_payload()
    payload["status"] = "draft"

    with pytest.raises(ValidationError) as exc_info:
        EvalTemplateManifest.model_validate(payload)

    assert "status" in str(exc_info.value)


def test_strict_mode_rejects_unknown_key_in_policy_rule() -> None:
    payload = _policy_payload()
    payload["rules"][0]["unexpected"] = "boom"

    with pytest.raises(ValidationError) as exc_info:
        PolicyManifest.model_validate(payload)

    assert "unexpected" in str(exc_info.value)
