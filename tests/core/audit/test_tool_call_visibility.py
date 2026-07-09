"""Tests del contrato de datos y del estado de gobernanza de la Tool call visible.

Cubre los scenarios de `openspec/changes/c09-mcp-tools/specs/tool-call-visibility/spec.md`:
1. Cada invocacion produce un registro visible colapsable.
2. Truncado del resultado en el registro visible.
5. Escritura escalada se muestra en espera de aprobacion.
6. Lectura permitida se muestra como ejecutada.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from resultarai.core.audit import AuditEvent, ToolCallStatus, project_visible_tool_call


def _build_audit_event(
    *,
    effect: str = "allow",
    operation_type: str = "read",
    tool: str = "erp_read_invoices",
) -> AuditEvent:
    """Construye un AuditEvent (frozen) minimo para los tests de este archivo."""
    return AuditEvent(
        user="Alice",
        tenant="totalpec",
        agent="agent_1",
        skill="erp_skill",
        tool=tool,
        operation_type=operation_type,  # type: ignore[arg-type]
        timestamp=datetime.now(UTC),
        environment="production",
        effect=effect,  # type: ignore[arg-type]
        applied_policy="erp_read_only_policy",
        reason=f"Effect is {effect}",
        parameters={"invoice_id": "123"},
    )


def test_scenario_1_lectura_allow_produce_registro_visible_colapsable() -> None:
    """Scenario 1: una lectura con Policy Gate allow produce un registro visible.

    Debe incluir tool, argumentos, resultado truncado y duracion, colapsado por
    defecto, y ser coherente con el AuditEvent de esa invocacion.
    """
    event = _build_audit_event(effect="allow", operation_type="read")

    visible_call = project_visible_tool_call(
        event=event,
        result_text="factura #123: total 450.00 BOB",
        duration_ms=120,
    )

    # Coherente con el AuditEvent de origen (mismo id, mismo tool, mismo effect).
    assert visible_call.audit_event_id == event.id
    assert visible_call.tool_name == event.tool
    assert visible_call.status is ToolCallStatus.EXECUTED

    # Contrato minimo: nombre de tool, argumentos, resultado truncado y duracion.
    assert visible_call.arguments == event.parameters
    assert visible_call.result_preview == "factura #123: total 450.00 BOB"
    assert visible_call.result_truncated is False
    assert visible_call.duration_ms == 120

    # Colapsada por defecto y expandible (contrato de UI).
    assert visible_call.collapsed_by_default is True


def test_scenario_2_resultado_largo_se_trunca_con_marca_explicita() -> None:
    """Scenario 2: un resultado que excede el largo mostrable se trunca con marca.

    El AuditEvent de origen no se altera (verificamos ademas que sigue siendo
    frozen, o sea que ninguna mutacion pudo haber ocurrido).
    """
    event = _build_audit_event(effect="allow", operation_type="read")
    long_result = "x" * 1000

    visible_call = project_visible_tool_call(
        event=event,
        result_text=long_result,
        duration_ms=50,
        max_preview_chars=100,
    )

    assert visible_call.result_truncated is True
    assert len(visible_call.result_preview or "") <= 100
    assert (visible_call.result_preview or "").endswith("[truncado]")
    assert visible_call.result_preview != long_result

    # El AuditEvent origen sigue intacto: mismos parametros, sigue frozen.
    assert event.parameters == {"invoice_id": "123"}
    with pytest.raises((ValidationError, TypeError)):
        event.parameters = {"invoice_id": "999"}  # type: ignore[misc]


def test_scenario_2_resultado_corto_no_se_trunca() -> None:
    """Complemento del scenario 2: un resultado corto no dispara truncado."""
    event = _build_audit_event(effect="allow", operation_type="read")

    visible_call = project_visible_tool_call(
        event=event,
        result_text="ok",
        duration_ms=10,
        max_preview_chars=100,
    )

    assert visible_call.result_truncated is False
    assert visible_call.result_preview == "ok"


def test_scenario_5_escritura_escalada_se_muestra_en_espera_de_aprobacion() -> None:
    """Scenario 5: una escritura con escalate_hitl se muestra en espera de aprobacion.

    Nunca como ejecutada; no hubo ejecucion real, por lo que duration_ms es None.
    """
    event = _build_audit_event(effect="escalate_hitl", operation_type="write")

    visible_call = project_visible_tool_call(
        event=event,
        result_text=None,
        duration_ms=None,
    )

    # Nunca ejecutada: `is PENDING_APPROVAL` ya excluye `EXECUTED` (enum de un solo valor).
    assert visible_call.status is ToolCallStatus.PENDING_APPROVAL
    assert visible_call.duration_ms is None
    assert visible_call.audit_event_id == event.id


def test_scenario_6_lectura_permitida_se_muestra_como_ejecutada() -> None:
    """Scenario 6: una lectura con Policy Gate allow se muestra como ejecutada."""
    event = _build_audit_event(effect="allow", operation_type="read")

    visible_call = project_visible_tool_call(
        event=event,
        result_text="3 facturas encontradas",
        duration_ms=80,
    )

    assert visible_call.status is ToolCallStatus.EXECUTED
    assert visible_call.result_preview == "3 facturas encontradas"
    assert visible_call.duration_ms == 80


def test_deny_se_mapea_a_denied() -> None:
    """Complemento: un deny del Policy Gate se proyecta como denied (no ejecutada)."""
    event = _build_audit_event(effect="deny", operation_type="write")

    visible_call = project_visible_tool_call(
        event=event,
        result_text=None,
        duration_ms=None,
    )

    assert visible_call.status is ToolCallStatus.DENIED
    assert visible_call.duration_ms is None


def test_visible_tool_call_es_inmutable() -> None:
    """La proyeccion de lectura tambien es frozen: no se reescribe tras crearse."""
    event = _build_audit_event(effect="allow", operation_type="read")
    visible_call = project_visible_tool_call(event=event, result_text="ok", duration_ms=5)

    with pytest.raises((ValidationError, TypeError)):
        visible_call.status = ToolCallStatus.DENIED  # type: ignore[misc]
