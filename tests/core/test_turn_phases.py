"""Tests for TurnPhase enum and steps requiring gate checks."""

from resultarai.core.routing import TurnPhase, steps_requiring_gate


def test_turn_phase_values() -> None:
    """Verify TurnPhase members and their string values."""
    assert TurnPhase.RECEIVE.value == "receive"
    assert TurnPhase.ROUTE.value == "route"
    assert TurnPhase.EXECUTE_GRAPH.value == "execute_graph"
    assert TurnPhase.RESPOND.value == "respond"

    # Verify we can list all phases
    expected_phases = ["receive", "route", "execute_graph", "respond"]
    assert [phase.value for phase in TurnPhase] == expected_phases


def test_steps_requiring_gate() -> None:
    """Verify that steps_requiring_gate returns the exact required list of phases."""
    steps = steps_requiring_gate(None)
    assert steps == ["respond", "activate_skill", "compaction"]
