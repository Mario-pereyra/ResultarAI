"""LangGraph default chat graph workflow definition for ResultarAI."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from resultarai.core.audit import create_audit_event
from resultarai.core.manifests.base import ManifestStatus, RiskLevel
from resultarai.core.manifests.routing import RoutingAction, RoutingManifest
from resultarai.core.policy import ActionRequest, PolicyDecision
from resultarai.core.ports.llm import LLMResponse
from resultarai.core.routing import RoutingDecision, decide, should_compact, to_action_request


class GraphState(TypedDict, total=False):
    """LangGraph State representation for the default chat workflow."""

    thread_id: str
    user: str
    tenant: str | None
    agent: str
    environment: str
    messages: list[dict[str, Any]]
    already_compacted: bool
    routing_decision: RoutingDecision | None
    policy_decision: PolicyDecision | None
    response: LLMResponse | None
    turn_id: str
    model_profile_id: str
    model_profile_window: int
    prompt: str
    status: str  # "active", "suspended", "denied"
    intent: str
    audit_events: list[Any]


def compaction_check(state: GraphState, config: RunnableConfig) -> dict[str, Any]:
    """Calculates context usage and evaluates should_compact.

    If needed and allowed by policy, triggers compaction of messages.
    """
    configurable = config.get("configurable", {})
    policy_port = configurable.get("policy_port")
    llm_port = configurable.get("llm_port")
    trace_port = configurable.get("trace_port")
    state_port = configurable.get("state_port")
    registries = configurable.get("registries")

    messages = state.get("messages") or []
    usage = sum(len(msg.get("content") or "") for msg in messages if msg.get("content") is not None)
    window = state.get("model_profile_window") or 0
    already_compacted = state.get("already_compacted") or False

    if should_compact(usage, window, already_compacted):
        if not policy_port:
            raise ValueError("policy_port is required for compaction check")

        request = ActionRequest(
            user=state.get("user") or "",
            tenant=state.get("tenant"),
            agent=state.get("agent") or "",
            skill="default_chat",
            tool="compaction",
            operation_type="read",
            risk_level=RiskLevel.LOW,
            environment=state.get("environment") or "",
        )
        active_policies = (
            list(registries.policies.invocable())
            if (registries and hasattr(registries, "policies") and registries.policies)
            else []
        )
        decision = policy_port.evaluate(request, active_policies)

        if decision.effect == "allow":
            summary_text = "Mock summary of the conversation."
            if llm_port:
                prompt = f"Summarize the following conversation: {messages}"
                try:
                    response = llm_port.generate(prompt=prompt)
                    summary_text = response.text
                except Exception:
                    pass

            range_compacted = list(messages)

            summary_msg = {
                "id": uuid.uuid4().hex,
                "role": "system",
                "content": f"Summary of previous messages: {summary_text}",
                "parent_id": messages[-1]["id"] if messages else None,
                "created_at": datetime.now(UTC).replace(tzinfo=None),
            }
            new_messages = [*messages, summary_msg]
            updated_state = {
                "messages": new_messages,
                "already_compacted": True,
            }

            if state_port:
                state_port.save_state(state.get("thread_id") or "", {**state, **updated_state})

            if trace_port:
                trace_port.trace_step(
                    step_name="compaction",
                    inputs={"messages": messages, "usage": usage, "turn_id": state.get("turn_id")},
                    outputs={
                        "compacted": True,
                        "range": range_compacted,
                        "turn_id": state.get("turn_id"),
                    },
                )

            return updated_state

    return {}


def receive(state: GraphState, config: RunnableConfig) -> dict[str, Any]:
    """Generates a new turn_id and appends the user's prompt as a new user message."""
    configurable = config.get("configurable", {})
    trace_port = configurable.get("trace_port")

    turn_id = uuid.uuid4().hex
    prompt = state.get("prompt") or ""
    messages = state.get("messages") or []

    user_msg = {
        "id": uuid.uuid4().hex,
        "role": "user",
        "content": prompt,
        "parent_id": messages[-1]["id"] if messages else None,
        "created_at": datetime.now(UTC).replace(tzinfo=None),
    }
    new_messages = [*messages, user_msg]

    if trace_port:
        trace_port.trace_step(
            step_name="receive",
            inputs={
                "prompt": prompt,
                "turn_id": turn_id,
                "user_id": state.get("user") or "",
                "session_id": state.get("thread_id") or "",
            },
            outputs={"messages": new_messages, "turn_id": turn_id},
        )

    return {
        "turn_id": turn_id,
        "messages": new_messages,
    }


def route_node(state: GraphState, config: RunnableConfig) -> dict[str, Any]:
    """Calls decide(state, routing_manifest) using default_routing manifest."""
    configurable = config.get("configurable", {})
    trace_port = configurable.get("trace_port")
    registries = configurable.get("registries")

    routing_manifest = None
    if registries and hasattr(registries, "routing") and registries.routing is not None:
        routing_manifest = registries.routing.get_invocable("default_routing")

    if routing_manifest is None:
        routing_manifest = RoutingManifest(
            id="default_routing",
            status=ManifestStatus.ACTIVE,
            version="1.0.0",
            rules=[],
        )

    decision = decide(state, routing_manifest)

    if trace_port:
        trace_port.trace_step(
            step_name="route",
            inputs={"state": state, "turn_id": state.get("turn_id")},
            outputs={"routing_decision": decision, "turn_id": state.get("turn_id")},
        )

    return {
        "routing_decision": decision,
    }


def policy_gate_respond(state: GraphState, config: RunnableConfig) -> dict[str, Any]:
    """Evaluates ActionRequest against policies for answering directly."""
    configurable = config.get("configurable", {})
    policy_port = configurable.get("policy_port")
    registries = configurable.get("registries")
    state_port = configurable.get("state_port")
    trace_port = configurable.get("trace_port")

    if not policy_port:
        raise ValueError("policy_port is required for policy gate respond")

    routing_decision = state.get("routing_decision")
    if not routing_decision:
        routing_decision = RoutingDecision(
            action=RoutingAction.ANSWER_DIRECTLY,
            reason="Fallback to respond",
        )

    action_request = to_action_request(routing_decision, state)
    active_policies = (
        list(registries.policies.invocable())
        if (registries and hasattr(registries, "policies") and registries.policies)
        else []
    )

    decision = policy_port.evaluate(action_request, active_policies)

    audit_event = create_audit_event(action_request, decision)
    audit_events = [*state.get("audit_events", []), audit_event]

    status = "active"
    if decision.effect == "deny":
        status = "denied"
    elif decision.effect == "escalate_hitl":
        status = "suspended"

    updated_state = {
        "policy_decision": decision,
        "status": status,
        "audit_events": audit_events,
    }

    if state_port:
        state_port.save_state(state.get("thread_id") or "", {**state, **updated_state})

    if trace_port:
        trace_port.trace_step(
            step_name="policy_gate",
            inputs={"action_request": action_request, "turn_id": state.get("turn_id")},
            outputs={
                "policy_decision": decision,
                "status": status,
                "turn_id": state.get("turn_id"),
            },
        )

    return updated_state


def policy_gate_activate_skill(state: GraphState, config: RunnableConfig) -> dict[str, Any]:
    """Evaluates ActionRequest against policies for activating a skill."""
    configurable = config.get("configurable", {})
    policy_port = configurable.get("policy_port")
    registries = configurable.get("registries")
    state_port = configurable.get("state_port")
    trace_port = configurable.get("trace_port")

    if not policy_port:
        raise ValueError("policy_port is required for policy gate activate skill")

    routing_decision = state.get("routing_decision")
    if not routing_decision:
        raise ValueError("routing_decision is required for policy gate activate skill")

    action_request = to_action_request(routing_decision, state)
    active_policies = (
        list(registries.policies.invocable())
        if (registries and hasattr(registries, "policies") and registries.policies)
        else []
    )

    decision = policy_port.evaluate(action_request, active_policies)

    audit_event = create_audit_event(action_request, decision)
    audit_events = [*state.get("audit_events", []), audit_event]

    status = "active"
    if decision.effect == "deny":
        status = "denied"
    elif decision.effect == "escalate_hitl":
        status = "suspended"

    updated_state = {
        "policy_decision": decision,
        "status": status,
        "audit_events": audit_events,
    }

    if state_port:
        state_port.save_state(state.get("thread_id") or "", {**state, **updated_state})

    if trace_port:
        trace_port.trace_step(
            step_name="policy_gate",
            inputs={"action_request": action_request, "turn_id": state.get("turn_id")},
            outputs={
                "policy_decision": decision,
                "status": status,
                "turn_id": state.get("turn_id"),
            },
        )

    return updated_state


def respond(state: GraphState, config: RunnableConfig) -> dict[str, Any]:
    """Generates LLM response and appends it to conversation history."""
    configurable = config.get("configurable", {})
    llm_port = configurable.get("llm_port")
    trace_port = configurable.get("trace_port")

    if not llm_port:
        raise ValueError("llm_port is required for respond")

    prompt = state.get("prompt") or ""
    kwargs = {}
    if state.get("model_profile_id"):
        kwargs["fallback_cascade"] = [state.get("model_profile_id")]

    response = llm_port.generate(prompt=prompt, **kwargs)

    messages = state.get("messages") or []
    reply_msg = {
        "id": uuid.uuid4().hex,
        "role": "assistant",
        "content": response.text,
        "parent_id": messages[-1]["id"] if messages else None,
        "created_at": datetime.now(UTC).replace(tzinfo=None),
    }
    new_messages = [*messages, reply_msg]

    if trace_port:
        trace_port.trace_step(
            step_name="respond",
            inputs={"messages": messages, "prompt": prompt, "turn_id": state.get("turn_id")},
            outputs={
                "response": response,
                "reply_message": reply_msg,
                "turn_id": state.get("turn_id"),
            },
        )

    return {
        "response": response,
        "messages": new_messages,
    }


def execute_graph(state: GraphState, config: RunnableConfig) -> dict[str, Any]:
    """Placeholder node for skill/sub-graph execution."""
    configurable = config.get("configurable", {})
    trace_port = configurable.get("trace_port")

    if trace_port:
        trace_port.trace_step(
            step_name="execute_graph",
            inputs={"state": state, "turn_id": state.get("turn_id")},
            outputs={"status": "completed", "turn_id": state.get("turn_id")},
        )

    return {}


def deny_node(state: GraphState, config: RunnableConfig) -> dict[str, Any]:
    """Ends execution with status denied."""
    return {"status": "denied"}


def suspend_node(state: GraphState, config: RunnableConfig) -> dict[str, Any]:
    """Ends execution with status suspended."""
    return {"status": "suspended"}


def after_route_routing(state: GraphState) -> str:
    """Routes based on the RoutingDecision action."""
    decision = state.get("routing_decision")
    if decision and decision.action == RoutingAction.ACTIVATE_SKILL:
        return "policy_gate_activate_skill"
    return "policy_gate_respond"


def after_policy_gate_respond(state: GraphState) -> str:
    """Routes based on PolicyGate decision after respond gate."""
    decision = state.get("policy_decision")
    if not decision:
        return "deny_node"
    if decision.effect == "allow":
        return "respond"
    if decision.effect == "escalate_hitl":
        return "suspend_node"
    return "deny_node"


def after_policy_gate_activate_skill(state: GraphState) -> str:
    """Routes based on PolicyGate decision after skill gate."""
    decision = state.get("policy_decision")
    if not decision:
        return "deny_node"
    if decision.effect == "allow":
        return "execute_graph"
    if decision.effect == "escalate_hitl":
        return "suspend_node"
    return "deny_node"


workflow = StateGraph(GraphState)

workflow.add_node("compaction_check", compaction_check)
workflow.add_node("receive", receive)
workflow.add_node("route", route_node)
workflow.add_node("policy_gate_respond", policy_gate_respond)
workflow.add_node("policy_gate_activate_skill", policy_gate_activate_skill)
workflow.add_node("respond", respond)
workflow.add_node("execute_graph", execute_graph)
workflow.add_node("deny_node", deny_node)
workflow.add_node("suspend_node", suspend_node)

workflow.add_edge(START, "compaction_check")
workflow.add_edge("compaction_check", "receive")
workflow.add_edge("receive", "route")

workflow.add_conditional_edges(
    "route",
    after_route_routing,
    {
        "policy_gate_respond": "policy_gate_respond",
        "policy_gate_activate_skill": "policy_gate_activate_skill",
    },
)

workflow.add_conditional_edges(
    "policy_gate_respond",
    after_policy_gate_respond,
    {
        "respond": "respond",
        "deny_node": "deny_node",
        "suspend_node": "suspend_node",
    },
)

workflow.add_conditional_edges(
    "policy_gate_activate_skill",
    after_policy_gate_activate_skill,
    {
        "execute_graph": "execute_graph",
        "deny_node": "deny_node",
        "suspend_node": "suspend_node",
    },
)

workflow.add_edge("respond", END)
workflow.add_edge("execute_graph", END)
workflow.add_edge("deny_node", END)
workflow.add_edge("suspend_node", END)

default_chat_graph = workflow.compile()
