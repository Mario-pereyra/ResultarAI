"""Ejecucion gobernada de Tools MCP: Policy Gate antes de `tools/call` + `AuditEvent` por decision.

`GovernedToolExecutor` integra el binding (`binding.py`), el Policy Gate (`a03`), el
cliente MCP (`client.py`) y el audit log (`a03`) en un unico flujo por invocacion,
conforme a la Requirement "Ejecucion gobernada por la clasificacion con emision de
AuditEvent" y a las Decisions 4 y 5 de `openspec/changes/c09-mcp-tools/design.md`:

1. `resolve_tool_binding`: sin `ToolManifest` activo -> la Tool NO existe. Resultado
   "tool inexistente": NO se consulta el Policy Gate, NO hay `tools/call`, y se emite un
   `AuditEvent` con `effect="deny"`, `applied_policy="tool_not_in_registry"` y `reason`
   nombrando la Tool.
2. Con binding: se construye el `ActionRequest` con la clasificacion DEL MANIFIESTO
   (`operation_type`, `risk_level`), nunca la del server.
3. Escritura (`operation_type: write`) -> `escalate_hitl` INCONDICIONAL (aunque una Policy
   dijera `allow`): NO se emite `tools/call`; el evento queda en espera de aprobacion
   humana (la Tarjeta HITL es `d17`).
4. Lectura -> `policy_gate` (deny-by-default). `allow` ejecuta via el cliente MCP y mide
   `duration_ms`; `deny`/`escalate_hitl` NO emiten `tools/call`.
5. TODA decision emite exactamente un `AuditEvent` (via `create_audit_event`, salvo el
   caso "tool inexistente" que se construye directo por no haber `ActionRequest`).

El `AuditEvent` (append-only, `a03`) es la unica fuente de verdad; el
`GovernedInvocationResult` lleva la decision, el evento, el `outcome` tipado y
`duration_ms`, lo necesario para que `project_visible_tool_call`
(`core/audit/visibility.py`) lo proyecte para la UI.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from resultarai.adapters.tools_mcp.binding import ResolvedToolBinding, resolve_tool_binding
from resultarai.adapters.tools_mcp.client import McpToolClient, ToolExecutionResult
from resultarai.adapters.tools_mcp.errors import McpToolClientError
from resultarai.adapters.tools_mcp.session import (
    ToolCallOutcome,
    ToolExecutionFailure,
    ToolProtocolFailure,
)
from resultarai.adapters.tools_mcp.transports import TransportConfig
from resultarai.core.audit import AuditEvent, create_audit_event
from resultarai.core.manifests import PolicyManifest
from resultarai.core.manifests.tool import OperationType
from resultarai.core.policy import ActionRequest, PolicyDecision, policy_gate
from resultarai.core.registries import ToolRegistry

__all__ = [
    "AuditSink",
    "EndpointResolutionError",
    "GovernedInvocationResult",
    "GovernedToolExecutor",
]

# Marcadores de `applied_policy` para las decisiones que no salen de una PolicyManifest.
_TOOL_NOT_IN_REGISTRY = "tool_not_in_registry"
_WRITE_REQUIRES_HITL = "write_requires_hitl"

# Un audit sink es un callable que recibe cada `AuditEvent` emitido; una `list` tambien
# sirve directamente (se usa su `.append`).
type AuditSink = Callable[[AuditEvent], None]


class EndpointResolutionError(Exception):
    """El `endpoint_ref` de un `ToolManifest` no resuelve a ningun `TransportConfig`.

    Error de configuracion: el `endpoint_resolver` no mapea el `endpoint_ref` del binding a
    un transport. Solo puede ocurrir en el camino de lectura `allow` (el unico que abre
    sesion MCP).
    """

    def __init__(self, endpoint_ref: str, manifest_id: str) -> None:
        self.endpoint_ref = endpoint_ref
        self.manifest_id = manifest_id
        super().__init__(
            f"no se pudo resolver el endpoint_ref {endpoint_ref!r} del ToolManifest "
            f"{manifest_id!r} a un TransportConfig: falta en el endpoint_resolver."
        )


@dataclass(frozen=True, slots=True)
class GovernedInvocationResult:
    """Resultado inmutable de una invocacion gobernada.

    - `decision`: la `PolicyDecision` que goberno la invocacion (allow/deny/escalate_hitl).
    - `audit_event`: el unico `AuditEvent` emitido para esta invocacion (fuente de verdad).
    - `outcome`: el resultado tipado del cliente MCP si hubo `tools/call` (`allow`), o `None`
      cuando no se ejecuto (`deny`, `escalate_hitl`, tool inexistente, o fallo local previo
      a `tools/call`).
    - `duration_ms`: milisegundos medidos alrededor del `tools/call`, o `None` si no se
      ejecuto.
    """

    decision: PolicyDecision
    audit_event: AuditEvent
    outcome: ToolExecutionResult | None
    duration_ms: int | None


def _operation_literal(operation_type: OperationType) -> Literal["read", "write"]:
    """Convierte el `OperationType` del manifiesto al `Literal` que exige `ActionRequest`."""
    return "write" if operation_type is OperationType.WRITE else "read"


def _elapsed_ms(start: float) -> int:
    """Milisegundos transcurridos desde `start` (`time.perf_counter`)."""
    return int((time.perf_counter() - start) * 1000)


def _summarize_outcome(outcome: ToolExecutionResult) -> str:
    """Resumen textual del `outcome` para el `result_summary` del `AuditEvent`.

    Un `ToolExecutionFailure`/`ToolProtocolFailure` en el camino `allow` conserva su
    decision `allow` (la Policy autorizo la lectura) pero registra el error observado, tal
    como pide la spec `tool-registry-binding`.
    """
    if isinstance(outcome, ToolCallOutcome):
        return outcome.content
    if isinstance(outcome, ToolExecutionFailure):
        return f"la Tool devolvio un error de ejecucion (isError): {outcome.message}"
    if isinstance(outcome, ToolProtocolFailure):
        return f"error de protocolo JSON-RPC {outcome.code}: {outcome.message}"
    # `ToolExecutionRejected` no ocurre en el camino `allow` (el cliente solo lo devuelve
    # cuando la decision no es `allow`, y aqui la decision es `allow`).
    return outcome.reason


class GovernedToolExecutor:
    """Ejecuta Tools MCP pasando SIEMPRE por el Policy Gate y auditando cada decision.

    Constructor:
    - `tool_registry`: el `ToolRegistry` (`a02`) del que se resuelve el binding.
    - `active_policies`: las `PolicyManifest` activas que evalua el Policy Gate.
    - `endpoint_resolver`: mapa `endpoint_ref -> TransportConfig` para abrir la sesion MCP
      del server que corresponda a cada Tool (solo se consulta en el camino `allow`).
    - `audit_sink`: callable `(AuditEvent) -> None` (o una `list[AuditEvent]`, se usa su
      `.append`) al que se emite exactamente un `AuditEvent` por invocacion.
    """

    def __init__(
        self,
        tool_registry: ToolRegistry,
        active_policies: list[PolicyManifest],
        endpoint_resolver: Mapping[str, TransportConfig],
        audit_sink: AuditSink | list[AuditEvent],
    ) -> None:
        self._tool_registry = tool_registry
        self._active_policies = list(active_policies)
        self._endpoint_resolver = endpoint_resolver
        self._emit: AuditSink = audit_sink.append if isinstance(audit_sink, list) else audit_sink

    def invoke(
        self,
        tool_id: str,
        arguments: dict[str, Any],
        *,
        user: str,
        agent: str,
        skill: str,
        environment: str,
        tenant: str | None = None,
    ) -> GovernedInvocationResult:
        """Ejecuta `tool_id` gobernada por su clasificacion; emite un `AuditEvent` por decision.

        `arguments` son los argumentos de la Tool. El resto (user/agent/skill/environment/
        tenant) es el contexto de gobernanza que va al `ActionRequest` y al `AuditEvent`.
        """
        binding = resolve_tool_binding(tool_id, self._tool_registry)
        if binding is None:
            return self._registry_miss(
                tool_id,
                arguments,
                user=user,
                agent=agent,
                skill=skill,
                environment=environment,
                tenant=tenant,
            )

        request = ActionRequest(
            user=user,
            tenant=tenant,
            agent=agent,
            skill=skill,
            tool=tool_id,
            operation_type=_operation_literal(binding.operation_type),
            risk_level=binding.risk_level,
            environment=environment,
            parameters=dict(arguments),
        )

        if binding.operation_type is OperationType.WRITE:
            return self._write_escalates_to_hitl(request)

        decision = policy_gate(request, self._active_policies)
        if decision.effect != "allow":
            # `deny` (deny-by-default) o `escalate_hitl` desde el gate: no hay `tools/call`.
            return self._audit_without_execution(request, decision)

        return self._execute_allowed_read(binding, request, decision, arguments)

    def _registry_miss(
        self,
        tool_id: str,
        arguments: dict[str, Any],
        *,
        user: str,
        agent: str,
        skill: str,
        environment: str,
        tenant: str | None,
    ) -> GovernedInvocationResult:
        """Camino "tool inexistente": deny sin Policy Gate ni `tools/call`, con `AuditEvent`.

        Sin `ToolManifest` activo no hay `ActionRequest` (no hay clasificacion que gobernar),
        asi que el `AuditEvent` se construye directo. `operation_type="read"` es el valor
        conservador (nada se ejecuto ni se escribio); `parameters` registra el intento tal
        cual para trazabilidad forense del rechazo.
        """
        reason = (
            f"La Tool {tool_id!r} no esta declarada en ningun ToolManifest activo del "
            "ToolRegistry: no existe para el runtime (deny-by-default a nivel de registro, "
            "regla dura 6)."
        )
        decision = PolicyDecision(
            effect="deny",
            reason=reason,
            applied_policy=_TOOL_NOT_IN_REGISTRY,
        )
        event = AuditEvent(
            user=user,
            tenant=tenant,
            agent=agent,
            skill=skill,
            tool=tool_id,
            operation_type="read",
            timestamp=datetime.now(UTC),
            environment=environment,
            effect="deny",
            applied_policy=_TOOL_NOT_IN_REGISTRY,
            reason=reason,
            parameters=dict(arguments),
        )
        self._emit(event)
        return GovernedInvocationResult(
            decision=decision, audit_event=event, outcome=None, duration_ms=None
        )

    def _write_escalates_to_hitl(self, request: ActionRequest) -> GovernedInvocationResult:
        """Escritura -> `escalate_hitl` incondicional (regla dura 4): sin `tools/call`."""
        decision = PolicyDecision(
            effect="escalate_hitl",
            reason=(
                "Operacion de escritura: escala a HITL de forma incondicional (regla dura 4, "
                "design Decision 4); no se emite tools/call y el evento queda en espera de "
                "aprobacion humana."
            ),
            applied_policy=_WRITE_REQUIRES_HITL,
        )
        event = create_audit_event(request, decision)
        self._emit(event)
        return GovernedInvocationResult(
            decision=decision, audit_event=event, outcome=None, duration_ms=None
        )

    def _audit_without_execution(
        self, request: ActionRequest, decision: PolicyDecision
    ) -> GovernedInvocationResult:
        """Emite el `AuditEvent` de una decision que no ejecuta (`deny`/`escalate_hitl`)."""
        event = create_audit_event(request, decision)
        self._emit(event)
        return GovernedInvocationResult(
            decision=decision, audit_event=event, outcome=None, duration_ms=None
        )

    def _execute_allowed_read(
        self,
        binding: ResolvedToolBinding,
        request: ActionRequest,
        decision: PolicyDecision,
        arguments: dict[str, Any],
    ) -> GovernedInvocationResult:
        """Ejecuta una lectura `allow` via el cliente MCP y audita con `result_summary`.

        Usa `binding.tool_name` (el nombre que el server conoce), no el `tool_id` del
        registro. Un fallo LOCAL del cliente (`ToolArgumentValidationError`,
        `UnknownToolError`) ocurre ANTES de `tools/call`: no hubo invocacion, pero el intento
        queda auditado (spec 1.4). Un `ToolExecutionFailure`/`ToolProtocolFailure` conserva la
        decision `allow` y registra el error en `result_summary`.
        """
        transport = self._endpoint_resolver.get(binding.endpoint_ref)
        if transport is None:
            raise EndpointResolutionError(binding.endpoint_ref, binding.manifest_id)

        client = McpToolClient(transport)
        start = time.perf_counter()
        outcome: ToolExecutionResult | None
        try:
            outcome = client.execute(binding.tool_name, dict(arguments), decision)
        except McpToolClientError as exc:
            duration_ms = _elapsed_ms(start)
            summary = f"error del cliente MCP antes de tools/call: {exc}"
            outcome = None
        else:
            duration_ms = _elapsed_ms(start)
            summary = _summarize_outcome(outcome)

        event = create_audit_event(request, decision, result_summary=summary)
        self._emit(event)
        return GovernedInvocationResult(
            decision=decision, audit_event=event, outcome=outcome, duration_ms=duration_ms
        )
