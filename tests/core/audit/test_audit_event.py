"""Tests for AuditEvent validation, immutability, and optional fields."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from resultarai.core.audit import AuditEvent


def test_audit_event_construction_with_only_required_fields() -> None:
    """Verify that AuditEvent constructs successfully with only required fields.

    Omit optionals.
    """
    event = AuditEvent(
        user="Alice",
        tenant="totalpec",
        agent="agent_1",
        skill="erp_skill",
        tool="erp_read_invoices",
        operation_type="read",
        timestamp=datetime.now(UTC),
        environment="production",
        effect="allow",
        applied_policy="erp_read_only_policy",
        reason="Action permitted",
        parameters={"id": "123"},
    )
    # Check required fields
    assert event.user == "Alice"
    assert event.tenant == "totalpec"
    assert event.agent == "agent_1"
    assert event.skill == "erp_skill"
    assert event.tool == "erp_read_invoices"
    assert event.operation_type == "read"
    assert isinstance(event.timestamp, datetime)
    assert event.environment == "production"
    assert event.effect == "allow"
    assert event.applied_policy == "erp_read_only_policy"
    assert event.reason == "Action permitted"
    assert event.parameters == {"id": "123"}

    # Check auto-generated ID
    assert isinstance(event.id, str)
    assert len(event.id) > 0

    # Check that optional fields are None/unset
    assert event.corrects is None
    assert event.result_summary is None
    assert event.cost is None
    assert event.trace_id is None


def test_audit_event_immutability() -> None:
    """Verify that AuditEvent is frozen and its fields cannot be mutated."""
    event = AuditEvent(
        user="Alice",
        tenant="totalpec",
        agent="agent_1",
        skill="erp_skill",
        tool="erp_read_invoices",
        operation_type="read",
        timestamp=datetime.now(UTC),
        environment="production",
        effect="allow",
        applied_policy="erp_read_only_policy",
        reason="Action permitted",
        parameters={"id": "123"},
    )

    with pytest.raises((ValidationError, ValidationError, TypeError)):
        event.user = "Bob"  # type: ignore

    with pytest.raises((ValidationError, ValidationError, TypeError)):
        event.effect = "deny"  # type: ignore
