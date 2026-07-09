"""Models for Langfuse tracing adapter."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from resultarai.core.policy.models import PolicyDecision
from resultarai.core.ports.llm import LLMResponse
from resultarai.core.routing.skill_router import RoutingDecision


class TurnTrace(BaseModel):
    """Pydantic model representing the internal trace of a single chat turn."""

    model_config = ConfigDict(strict=True, extra="forbid")

    turn_id: str
    session_id: str
    user_id: str
    prompt: str
    response: LLMResponse | None = None
    routing_decision: RoutingDecision | None = None
    policy_decisions: list[PolicyDecision] = Field(default_factory=list)
    scan_result: dict[str, Any] | None = None
    prompt_version: str | None = None
