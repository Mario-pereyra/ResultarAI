"""Policy Gate implementation for evaluating ActionRequests against active policies."""

from __future__ import annotations

from typing import Any, Literal

from resultarai.core.manifests.policy import PolicyManifest, PolicyRule
from resultarai.core.policy.models import ActionRequest, PolicyDecision


def _rule_matches(rule: PolicyRule, request: ActionRequest) -> bool:
    """Helper to check if all conditions in rule.when match the request."""
    for key, val in rule.when.items():
        if not hasattr(request, key):
            return False
        req_val = getattr(request, key)
        # Normalize enums to their values for comparison
        if hasattr(req_val, "value"):
            req_val = req_val.value
        if hasattr(val, "value"):
            val = val.value
        if req_val != val:
            return False
    return True


def policy_gate(request: ActionRequest, active_policies: list[PolicyManifest]) -> PolicyDecision:
    """Evaluates an ActionRequest against a list of active PolicyManifests.

    Ensures user-tenant isolation, applies deny-by-default, and maps risk level
    to HITL constraints.
    """
    # 1. User-tenant isolation check
    user_associated_tenants = set()
    for policy in active_policies:
        for rule in policy.rules:
            if rule.when.get("user") == request.user and "tenant" in rule.when:
                val = rule.when["tenant"]
                if isinstance(val, list):
                    for t in val:
                        user_associated_tenants.add(t)
                else:
                    user_associated_tenants.add(val)

    if user_associated_tenants and request.tenant not in user_associated_tenants:
        return PolicyDecision(
            effect="deny",
            reason="Falta de autorización usuario↔tenant: cruce entre tenants bloqueado",
            applied_policy="deny_by_default",
        )

    # 2. Filter policies that apply to the requested skill
    applicable_policies = [
        policy for policy in active_policies if request.skill in policy.applies_to.skills
    ]

    # 3. Find the first matching rule in order
    matched_rule = None
    applied_policy_id = None
    for policy in applicable_policies:
        for rule in policy.rules:
            if _rule_matches(rule, request):
                matched_rule = rule
                applied_policy_id = policy.id
                break
        if matched_rule:
            break

    # 4. Deny by default if no rule matches
    if not matched_rule or applied_policy_id is None:
        return PolicyDecision(
            effect="deny",
            reason="Acción bloqueada por defecto: ninguna política aplicable autoriza la acción",
            applied_policy="deny_by_default",
        )

    # 5. Rule effect is deny
    rule_effect = (
        matched_rule.effect.value if hasattr(matched_rule.effect, "value") else matched_rule.effect
    )
    if rule_effect == "deny":
        return PolicyDecision(
            effect="deny",
            reason=f"Acción denegada explícitamente por política '{applied_policy_id}'",
            applied_policy=applied_policy_id,
        )

    # 6. Risk and HITL mapping
    effect: Literal["allow", "deny", "escalate_hitl"] = "allow"
    reason = ""
    limits: dict[str, Any] | None = None
    requires_approver_comment = False
    requires_second_approval = False

    risk_level = (
        request.risk_level.value if hasattr(request.risk_level, "value") else request.risk_level
    )

    if risk_level == "critical":
        effect = "escalate_hitl"
        reason = (
            f"Acción requiere aprobación humana (HITL) por "
            f"riesgo crítico en política '{applied_policy_id}'"
        )
        requires_approver_comment = True
        if request.irreversible or matched_rule.when.get("irreversible") is True:
            requires_second_approval = True
    elif risk_level == "high":
        effect = "escalate_hitl"
        reason = (
            f"Acción requiere aprobación humana (HITL) por "
            f"riesgo alto en política '{applied_policy_id}'"
        )
    elif risk_level == "medium":
        if rule_effect == "escalate_hitl":
            effect = "escalate_hitl"
            reason = (
                f"Acción requiere aprobación humana (HITL) "
                f"escalada por regla de política '{applied_policy_id}'"
            )
        else:
            effect = "allow"
            reason = (
                f"Acción permitida con límites por riesgo medio bajo política '{applied_policy_id}'"
            )
            limits = {"max_rows": 20, "pagination": True, "summarize": True}
    else:  # low
        if rule_effect == "escalate_hitl":
            effect = "escalate_hitl"
            reason = (
                f"Acción requiere aprobación humana (HITL) "
                f"escalada por regla de política '{applied_policy_id}'"
            )
        else:
            effect = "allow"
            reason = f"Acción permitida por política '{applied_policy_id}'"

    return PolicyDecision(
        effect=effect,
        reason=reason,
        applied_policy=applied_policy_id,
        limits=limits,
        requires_approver_comment=requires_approver_comment,
        requires_second_approval=requires_second_approval,
    )
