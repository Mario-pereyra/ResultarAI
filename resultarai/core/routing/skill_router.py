"""Skill Router and routing decisions for ResultarAI."""

from __future__ import annotations

import enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from resultarai.core.manifests.base import RiskLevel
from resultarai.core.manifests.routing import RoutingAction, RoutingManifest
from resultarai.core.policy.models import ActionRequest


class RoutingDecision(BaseModel):
    """Routing decision made by the Skill Router."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    action: RoutingAction | Literal["answer_directly", "activate_skill", "delegate"]
    target: str | None = None
    reason: str


class TurnPhase(enum.StrEnum):
    """Phases of a single turn execution."""

    RECEIVE = "receive"
    ROUTE = "route"
    EXECUTE_GRAPH = "execute_graph"
    RESPOND = "respond"


def decide(turn: Any, routing_manifest: RoutingManifest) -> RoutingDecision:
    """Decide the routing action based on intent and manifest rules."""
    intent = turn.get("intent") if isinstance(turn, dict) else getattr(turn, "intent", None)

    for rule in routing_manifest.rules:
        if rule.intent == intent:
            reason = (
                f"Matched rule for intent {intent!r} in routing manifest {routing_manifest.id!r}"
            )
            return RoutingDecision(
                action=rule.action,
                target=rule.target,
                reason=reason,
            )

    reason = (
        f"No matching rule found for intent {intent!r} "
        f"in routing manifest {routing_manifest.id!r}. "
        f"Falling back to default chat."
    )
    return RoutingDecision(
        action=RoutingAction.ANSWER_DIRECTLY,
        target=None,
        reason=reason,
    )


def to_action_request(routing_decision: RoutingDecision, turn_context: Any) -> ActionRequest:
    """Translate routing decision into an ActionRequest."""

    def _get_field(ctx: Any, name: str) -> Any:
        if isinstance(ctx, dict):
            return ctx.get(name)
        return getattr(ctx, name, None)

    user = _get_field(turn_context, "user")
    tenant = _get_field(turn_context, "tenant")
    agent = _get_field(turn_context, "agent")
    environment = _get_field(turn_context, "environment")

    if routing_decision.action == RoutingAction.ACTIVATE_SKILL:
        skill = routing_decision.target or ""
    elif routing_decision.action == RoutingAction.ANSWER_DIRECTLY:
        skill = "default_chat"
    else:
        skill = routing_decision.target or "default_chat"

    return ActionRequest(
        user=user,
        tenant=tenant,
        agent=agent,
        skill=skill,
        tool="",
        operation_type="read",
        risk_level=RiskLevel.LOW,
        environment=environment,
    )


def steps_requiring_gate(turn: Any) -> list[str]:
    """Return the steps that require Policy Gate evaluation."""
    return ["respond", "activate_skill", "compaction"]
