"""Tests de la capa por rol de la Tool call visible.

Cubre los scenarios de `openspec/changes/c09-mcp-tools/specs/tool-call-visibility/spec.md`:
3. Funcional ve lenguaje simple.
4. Tecnico y Admin ven parametros completos.
"""

from __future__ import annotations

from datetime import UTC, datetime

from resultarai.core.audit import (
    AuditEvent,
    ToolCallStatus,
    ViewerRole,
    project_visible_tool_call,
    render_for_role,
)


def _build_audit_event(*, effect: str = "allow", operation_type: str = "read") -> AuditEvent:
    """Construye un AuditEvent (frozen) minimo, con un parametro tecnico distintivo."""
    return AuditEvent(
        user="Alice",
        tenant="totalpec",
        agent="agent_1",
        skill="erp_skill",
        tool="erp_read_invoices",
        operation_type=operation_type,  # type: ignore[arg-type]
        timestamp=datetime.now(UTC),
        environment="production",
        effect=effect,  # type: ignore[arg-type]
        applied_policy="erp_read_only_policy",
        reason=f"Effect is {effect}",
        parameters={"invoice_id": "SC5-000123", "branch_code": "D MG 01"},
    )


def test_scenario_3_funcional_ve_lenguaje_simple_sin_parametros_tecnicos() -> None:
    """Scenario 3: el rol Funcional expande una lectura ejecutada (allow).

    Debe ver una descripcion en lenguaje simple y NO los parametros tecnicos
    completos (parameters is None), sin volcar los argumentos crudos en el texto.
    """
    event = _build_audit_event(effect="allow", operation_type="read")
    visible_call = project_visible_tool_call(
        event=event,
        result_text="3 facturas encontradas para la sucursal",
        duration_ms=90,
    )

    view = render_for_role(visible_call, ViewerRole.FUNCIONAL)

    assert view.parameters is None
    assert view.simple_description != ""
    # No debe filtrar los valores tecnicos crudos en la descripcion simple.
    assert "SC5-000123" not in view.simple_description
    assert "branch_code" not in view.simple_description
    assert view.status is ToolCallStatus.EXECUTED
    assert view.status_label == "ejecutada"


def test_scenario_4_tecnico_y_admin_ven_parametros_completos() -> None:
    """Scenario 4: Tecnico y Admin expanden la misma Tool call (allow).

    Ambos deben ver los parametros completos de la invocacion, derivados del
    mismo AuditEvent (misma VisibleToolCall para los dos roles).
    """
    event = _build_audit_event(effect="allow", operation_type="read")
    visible_call = project_visible_tool_call(
        event=event,
        result_text="3 facturas encontradas",
        duration_ms=90,
    )

    tecnico_view = render_for_role(visible_call, ViewerRole.TECNICO)
    admin_view = render_for_role(visible_call, ViewerRole.ADMIN)

    assert tecnico_view.parameters == visible_call.arguments
    assert admin_view.parameters == visible_call.arguments
    assert tecnico_view.parameters == admin_view.parameters


def test_escritura_escalada_nunca_se_muestra_como_ejecutada_en_ningun_rol() -> None:
    """Complemento: una escritura escalate_hitl no se muestra como ejecutada.

    Ni para Funcional ni para Tecnico/Admin: el estado de gobernanza es el mismo
    para todos los roles, solo cambia la presentacion.
    """
    event = _build_audit_event(effect="escalate_hitl", operation_type="write")
    visible_call = project_visible_tool_call(event=event, result_text=None, duration_ms=None)

    for role in ViewerRole:
        view = render_for_role(visible_call, role)
        # Nunca ejecutada: `is PENDING_APPROVAL` ya excluye `EXECUTED` (enum de un solo valor).
        assert view.status is ToolCallStatus.PENDING_APPROVAL
        assert view.status_label == "en espera de aprobación"
        assert view.duration_ms is None

    funcional_view = render_for_role(visible_call, ViewerRole.FUNCIONAL)
    assert funcional_view.parameters is None

    tecnico_view = render_for_role(visible_call, ViewerRole.TECNICO)
    assert tecnico_view.parameters == visible_call.arguments
