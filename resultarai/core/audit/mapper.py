"""Mapper for creating AuditEvents from ActionRequests and PolicyDecisions."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from resultarai.core.audit.models import AuditEvent
from resultarai.core.policy.models import ActionRequest, PolicyDecision


def _enmask_parameters(params: dict[str, Any] | None) -> dict[str, Any]:
    """Recursively masks sensitive parameters in the dictionary."""
    if params is None:
        return {}

    sensitive_substrings = {
        "password",
        "secret",
        "token",
        "key",
        "credential",
        "auth",
        "private",
    }

    def mask_value(val: Any) -> Any:
        if isinstance(val, dict):
            return {
                k: (
                    "[ENMASKED]"
                    if any(sub in k.lower() for sub in sensitive_substrings)
                    else mask_value(v)
                )
                for k, v in val.items()
            }
        elif isinstance(val, list):
            return [mask_value(item) for item in val]
        return val

    return {
        k: (
            "[ENMASKED]" if any(sub in k.lower() for sub in sensitive_substrings) else mask_value(v)
        )
        for k, v in params.items()
    }


def create_audit_event(
    request: ActionRequest,
    decision: PolicyDecision,
    corrects: str | None = None,
) -> AuditEvent:
    """Creates a new AuditEvent mapping fields from ActionRequest and PolicyDecision."""
    masked_params = _enmask_parameters(request.parameters)

    return AuditEvent(
        user=request.user,
        tenant=request.tenant,
        agent=request.agent,
        skill=request.skill,
        tool=request.tool,
        operation_type=request.operation_type,
        timestamp=datetime.now(UTC),
        environment=request.environment,
        effect=decision.effect,
        applied_policy=decision.applied_policy,
        reason=decision.reason,
        parameters=masked_params,
        corrects=corrects,
    )
