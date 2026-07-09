"""Routing models and components for the core framework."""

from resultarai.core.routing.compaction import should_compact
from resultarai.core.routing.skill_router import (
    RoutingDecision,
    TurnPhase,
    decide,
    steps_requiring_gate,
    to_action_request,
)

__all__ = [
    "RoutingDecision",
    "TurnPhase",
    "decide",
    "should_compact",
    "steps_requiring_gate",
    "to_action_request",
]
