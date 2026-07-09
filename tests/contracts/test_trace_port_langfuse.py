"""Contract tests for Langfuse tracing adapter."""

import hashlib

import pytest
from pydantic import ValidationError

from resultarai.adapters.tracing_langfuse.client import MockLangfuse
from resultarai.adapters.tracing_langfuse.models import TurnTrace
from resultarai.adapters.tracing_langfuse.trace import LangfuseTraceAdapter
from resultarai.core.policy.models import PolicyDecision
from resultarai.core.ports.llm import LLMResponse
from resultarai.core.routing.skill_router import RoutingDecision


def test_turn_trace_validation() -> None:
    """Verify that TurnTrace enforces fields and validates properly."""
    # TurnTrace with all fields
    trace = TurnTrace(
        turn_id="turn-123",
        session_id="session-456",
        user_id="user-789",
        prompt="hello world",
        response=LLMResponse(
            text="hello",
            model_profile_id="gpt-4o",
            is_alternate_model=False,
            cache_hit_tokens=10,
            cache_miss_tokens=20,
            cost_usd=0.0005,
        ),
        routing_decision=RoutingDecision(
            action="answer_directly",
            reason="just chat",
        ),
        policy_decisions=[
            PolicyDecision(
                effect="allow",
                reason="pass",
                applied_policy="default_policy",
            )
        ],
        scan_result={"n2_flag": False, "injection_alert": False},
        prompt_version="v1.2",
    )
    assert trace.turn_id == "turn-123"
    assert trace.session_id == "session-456"

    # Missing mandatory field should raise ValidationError
    with pytest.raises(ValidationError):
        # Missing user_id
        TurnTrace(
            turn_id="turn-123",
            session_id="session-456",
            prompt="hello",
        )  # type: ignore


def test_user_id_masking() -> None:
    """Verify that the user_id is masked (SHA-256) and never sent in clear text."""
    client = MockLangfuse()
    adapter = LangfuseTraceAdapter(client=client)

    raw_user_id = "sensitive-user-username"
    expected_hash = hashlib.sha256(raw_user_id.encode("utf-8")).hexdigest()

    # Test via trace_turn
    turn_trace = TurnTrace(
        turn_id="turn-1",
        session_id="session-1",
        user_id=raw_user_id,
        prompt="hello",
    )
    adapter.trace_turn(turn_trace)

    trace_data = client.traces["turn-1"]
    assert trace_data["user_id"] == expected_hash
    assert raw_user_id not in str(trace_data)

    # Test via trace_step
    adapter.trace_step(
        step_name="receive",
        inputs={
            "turn_id": "turn-2",
            "user_id": raw_user_id,
            "session_id": "session-1",
            "prompt": "hello",
        },
        outputs={},
    )

    trace_data2 = client.traces["turn-2"]
    assert trace_data2["user_id"] == expected_hash
    assert raw_user_id not in str(trace_data2)


def test_prompt_version_binding() -> None:
    """Verify that prompt_version is bound and accessible in the trace metadata."""
    client = MockLangfuse()
    adapter = LangfuseTraceAdapter(client=client)

    # Via trace_turn
    turn_trace = TurnTrace(
        turn_id="turn-1",
        session_id="session-1",
        user_id="user-1",
        prompt="hello",
        prompt_version="prompt-v3.0.1",
    )
    adapter.trace_turn(turn_trace)

    metadata = client.traces["turn-1"]["metadata"]
    assert metadata["prompt_version"] == "prompt-v3.0.1"

    # Via trace_step
    adapter.trace_step(
        step_name="receive",
        inputs={
            "turn_id": "turn-2",
            "user_id": "user-1",
            "session_id": "session-1",
            "prompt": "hello",
            "prompt_version": "prompt-v4.0.0",
        },
        outputs={},
    )
    metadata2 = client.traces["turn-2"]["metadata"]
    assert metadata2["prompt_version"] == "prompt-v4.0.0"


def test_cache_hit_and_miss_usage_and_cost() -> None:
    """Verify that cache hit and cache miss usages/costs are mapped to distinct buckets."""
    client = MockLangfuse()
    adapter = LangfuseTraceAdapter(client=client)

    # 1. Turn with cache hit
    response_hit = LLMResponse(
        text="cached response",
        model_profile_id="gpt-4o",
        is_alternate_model=False,
        cache_hit_tokens=150,
        cache_miss_tokens=0,
        cost_usd=0.001,
    )
    turn_hit = TurnTrace(
        turn_id="turn-hit",
        session_id="session-1",
        user_id="user-1",
        prompt="hello cached",
        response=response_hit,
    )
    adapter.trace_turn(turn_hit)

    trace_hit_data = client.traces["turn-hit"]
    gen_hit = trace_hit_data["spans"][0]
    assert gen_hit["usage"]["input"] == 150
    assert gen_hit["usage"]["input_details"]["cache_read"] == 150
    assert gen_hit["metadata"]["usage_details"]["prompt_cache_hit_tokens"] == 150
    assert gen_hit["metadata"]["usage_details"]["prompt_cache_miss_tokens"] == 0
    assert gen_hit["metadata"]["cost_details"]["cost_usd"] == 0.001

    # 2. Turn with cache miss
    response_miss = LLMResponse(
        text="fresh response",
        model_profile_id="gpt-4o",
        is_alternate_model=False,
        cache_hit_tokens=0,
        cache_miss_tokens=200,
        cost_usd=0.003,
    )
    turn_miss = TurnTrace(
        turn_id="turn-miss",
        session_id="session-1",
        user_id="user-1",
        prompt="hello fresh",
        response=response_miss,
    )
    adapter.trace_turn(turn_miss)

    trace_miss_data = client.traces["turn-miss"]
    gen_miss = trace_miss_data["spans"][0]
    assert gen_miss["usage"]["input"] == 200
    assert "input_details" not in gen_miss["usage"]
    assert gen_miss["metadata"]["usage_details"]["prompt_cache_hit_tokens"] == 0
    assert gen_miss["metadata"]["usage_details"]["prompt_cache_miss_tokens"] == 200
    assert gen_miss["metadata"]["cost_details"]["cost_usd"] == 0.003


def test_routing_and_policy_decisions_nesting() -> None:
    """Verify that routing and policy decisions are nested as child events/observations."""
    client = MockLangfuse()
    adapter = LangfuseTraceAdapter(client=client)

    # Setup TurnTrace with routing decision (activate skill) and policy decision (escalate_hitl)
    routing_dec = RoutingDecision(
        action="activate_skill",
        target="erp_safe_query",
        reason="user wants to query invoices",
    )
    policy_dec = PolicyDecision(
        effect="escalate_hitl",
        reason="high risk financial write operation",
        applied_policy="financial_limit_policy",
        limits={"max_amount": 5000},
    )

    turn_trace = TurnTrace(
        turn_id="turn-nest",
        session_id="session-1",
        user_id="user-1",
        prompt="query invoice",
        routing_decision=routing_dec,
        policy_decisions=[policy_dec],
    )
    adapter.trace_turn(turn_trace)

    trace_data = client.traces["turn-nest"]
    events = trace_data["events"]

    # Verify routing decision event
    routing_event = next(e for e in events if e["name"] == "routing_decision")
    assert routing_event["input"]["reason"] == "user wants to query invoices"
    assert routing_event["output"]["action"] == "activate_skill"
    assert routing_event["output"]["target"] == "erp_safe_query"

    # Verify policy decision event
    policy_event = next(e for e in events if e["name"] == "policy_decision")
    assert policy_event["input"]["applied_policy"] == "financial_limit_policy"
    assert policy_event["input"]["limits"] == {"max_amount": 5000}
    assert policy_event["output"]["effect"] == "escalate_hitl"
    assert policy_event["output"]["reason"] == "high risk financial write operation"


def test_flagged_attachments() -> None:
    """Verify that attachment scan results and injection alert flags are in metadata."""
    client = MockLangfuse()
    adapter = LangfuseTraceAdapter(client=client)

    # 1. Flagged attachment
    turn_flagged = TurnTrace(
        turn_id="turn-flagged",
        session_id="session-1",
        user_id="user-1",
        prompt="here is my file",
        scan_result={
            "n2_flag": True,
            "n3_flag": False,
            "injection_alert": True,
            "scan_id": "scan-xyz",
        },
    )
    adapter.trace_turn(turn_flagged)
    metadata_flagged = client.traces["turn-flagged"]["metadata"]
    assert metadata_flagged["n2_flag"] is True
    assert metadata_flagged["injection_alert"] is True
    assert metadata_flagged["scan_id"] == "scan-xyz"

    # 2. Clean attachment
    turn_clean = TurnTrace(
        turn_id="turn-clean",
        session_id="session-1",
        user_id="user-1",
        prompt="here is my clean file",
        scan_result={
            "n2_flag": False,
            "n3_flag": False,
            "injection_alert": False,
            "scan_id": "scan-abc",
        },
    )
    adapter.trace_turn(turn_clean)
    metadata_clean = client.traces["turn-clean"]["metadata"]
    assert metadata_clean["n2_flag"] is False
    assert metadata_clean["injection_alert"] is False


def test_fallback_escalation_tag() -> None:
    """Verify that the 'alternate-model' tag is present when fallback is active."""
    client = MockLangfuse()
    adapter = LangfuseTraceAdapter(client=client)

    # Fallback Active -> is_alternate_model is True
    resp_fallback = LLMResponse(
        text="response",
        model_profile_id="gpt-4-alternate",
        is_alternate_model=True,
        primary_model_profile_id="gpt-4-primary",
        fallback_reason="Primary model rate limited",
    )
    turn_fallback = TurnTrace(
        turn_id="turn-fallback",
        session_id="session-1",
        user_id="user-1",
        prompt="run fallback",
        response=resp_fallback,
    )
    adapter.trace_turn(turn_fallback)
    assert "alternate-model" in client.traces["turn-fallback"]["tags"]

    # Fallback Inactive -> is_alternate_model is False
    resp_no_fallback = LLMResponse(
        text="response",
        model_profile_id="gpt-4-primary",
        is_alternate_model=False,
    )
    turn_no_fallback = TurnTrace(
        turn_id="turn-no-fallback",
        session_id="session-1",
        user_id="user-1",
        prompt="run primary",
        response=resp_no_fallback,
    )
    adapter.trace_turn(turn_no_fallback)
    assert "alternate-model" not in client.traces["turn-no-fallback"]["tags"]


def test_url_pattern_formatting() -> None:
    """Verify URL naming conventions for traces and sessions as defined in README."""
    host = "https://cloud.langfuse.com"
    project_id = "proj_123"
    trace_id = "trace_abc"
    session_id = "session_xyz"

    trace_url = f"{host}/project/{project_id}/traces/{trace_id}"
    session_url = f"{host}/project/{project_id}/sessions/{session_id}"

    assert trace_url == "https://cloud.langfuse.com/project/proj_123/traces/trace_abc"
    assert session_url == "https://cloud.langfuse.com/project/proj_123/sessions/session_xyz"
