"""Smoke tests to confirm that dummy doubles satisfy their corresponding ports protocols."""

from resultarai.core.ports.llm import LLMPort
from resultarai.core.ports.policy import PolicyPort
from resultarai.core.ports.state import StatePort
from resultarai.core.ports.tool import ToolPort
from resultarai.core.ports.trace import TracePort
from tests.contracts.fixtures.doubles import (
    DummyLLMPort,
    DummyPolicyPort,
    DummyStatePort,
    DummyToolPort,
    DummyTracePort,
)


def test_doubles_satisfy_protocols() -> None:
    """Instantiate and verify that doubles can be assigned to protocol types."""
    policy_port: PolicyPort = DummyPolicyPort()
    llm_port: LLMPort = DummyLLMPort()
    trace_port: TracePort = DummyTracePort()
    state_port: StatePort = DummyStatePort()
    tool_port: ToolPort = DummyToolPort()

    assert policy_port is not None
    assert llm_port is not None
    assert trace_port is not None
    assert state_port is not None
    assert tool_port is not None
