"""Audit models for the core framework."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class AuditEvent(BaseModel):
    """Represents an immutable, append-only audit log entry."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    user: str
    tenant: str | None
    agent: str
    skill: str
    tool: str
    operation_type: Literal["read", "write"]
    timestamp: datetime
    environment: str
    effect: Literal["allow", "deny", "escalate_hitl"]
    applied_policy: str
    reason: str
    parameters: dict[str, Any]
    corrects: str | None = None
    result_summary: str | None = None
    cost: float | None = None
    trace_id: str | None = None
