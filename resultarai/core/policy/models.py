"""Policy and risk models for the core framework."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, model_validator

from resultarai.core.manifests.base import RiskLevel


class ActionRequest(BaseModel):
    """Represents a request to execute an action in the system.

    Validates that any ERP tool execution contains a valid tenant.
    """

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    user: str
    tenant: str | None = None
    agent: str
    skill: str
    tool: str
    operation_type: Literal["read", "write"]
    risk_level: RiskLevel
    environment: str
    irreversible: bool = False
    parameters: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_erp_tool_tenant(self) -> ActionRequest:
        """Validate that tenant is provided and not empty if tool is an ERP tool."""
        # ERP tools are identified if they start with "erp_" or contain "erp".
        if (self.tool.startswith("erp_") or "erp" in self.tool) and (
            not self.tenant or not self.tenant.strip()
        ):
            raise ValueError("tenant is required for ERP tools")
        return self


class PolicyDecision(BaseModel):
    """Represents the decision made by the Policy Gate for an ActionRequest."""

    model_config = ConfigDict(strict=True, extra="forbid")

    effect: Literal["allow", "deny", "escalate_hitl"]
    reason: str
    applied_policy: str  # id de PolicyManifest o marcador "deny_by_default"
    limits: dict[str, Any] | None = None
    requires_approver_comment: bool = False
    requires_second_approval: bool = False
