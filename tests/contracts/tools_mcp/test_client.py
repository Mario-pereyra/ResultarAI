"""Tests de contrato: `McpToolClient` (adapter `ToolPort` completo).

Cubre, de punta a punta, el contrato descrito en `design.md` (Decision 4) y
en la Requirement "Cliente MCP conforme a la spec MCP revisión 2025-11-25
detrás del ToolPort":

- `McpToolClient` conforma estructuralmente `ToolPort` (chequeo de tipos,
  mismo patrón que `tests/core/ports/test_protocols.py`).
- `PolicyDecision.effect == "allow"` ejecuta la Tool end-to-end (stdio, server
  de ejemplo) y devuelve un `ToolCallOutcome`.
- `PolicyDecision.effect in {"deny", "escalate_hitl"}` NUNCA abre una sesión
  MCP ni contacta al server: se prueba apuntando a un comando de subproceso
  inexistente, de forma que si el cliente intentara conectar igual, el test
  fallaría con un error de proceso en vez de con el rechazo tipado esperado.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from resultarai.adapters.tools_mcp.client import McpToolClient, ToolExecutionRejected
from resultarai.adapters.tools_mcp.errors import UnknownToolError
from resultarai.adapters.tools_mcp.session import ToolCallOutcome
from resultarai.adapters.tools_mcp.transports import StdioTransportConfig
from resultarai.core.policy import PolicyDecision
from resultarai.core.ports import ToolPort

_SERVER_MODULE = "resultarai.adapters.tools_mcp.example_server"
_NONEXISTENT_COMMAND = "comando-mcp-que-no-existe-resultarai-c09"


def _example_server_transport(cwd: Path) -> StdioTransportConfig:
    return StdioTransportConfig(command=sys.executable, args=("-m", _SERVER_MODULE), cwd=str(cwd))


def test_mcp_tool_client_conforms_to_tool_port(tmp_path: Path) -> None:
    # Asignación tipada: si McpToolClient no satisface ToolPort
    # estructuralmente, esto falla en `uv run mypy`, no en tiempo de
    # ejecución (mismo patrón que tests/core/ports/test_protocols.py).
    port: ToolPort = McpToolClient(_example_server_transport(tmp_path))
    assert isinstance(port, McpToolClient)


class TestExecuteWithAllowRunsEndToEnd:
    """`decision.effect == "allow"` ejecuta la Tool contra el server de ejemplo."""

    def test_allow_decision_executes_echo_and_returns_a_typed_outcome(self, tmp_path: Path) -> None:
        client = McpToolClient(_example_server_transport(tmp_path))
        decision = PolicyDecision(
            effect="allow",
            reason="lectura autorizada por policy de prueba",
            applied_policy="policy_test",
        )

        outcome = client.execute("echo", {"text": "hola execute"}, decision)

        assert isinstance(outcome, ToolCallOutcome)
        assert outcome.is_error is False
        assert outcome.content == "hola execute"

    def test_allow_decision_with_unknown_tool_name_raises(self, tmp_path: Path) -> None:
        client = McpToolClient(_example_server_transport(tmp_path))
        decision = PolicyDecision(
            effect="allow",
            reason="lectura autorizada por policy de prueba",
            applied_policy="policy_test",
        )

        with pytest.raises(UnknownToolError):
            client.execute("tool_que_no_existe_en_el_server", {}, decision)


class TestExecuteWithoutAllowNeverContactsTheServer:
    """`decision.effect` distinto de `allow` nunca abre sesión MCP ni llama al server."""

    def test_deny_decision_returns_typed_rejection(self) -> None:
        client = McpToolClient(StdioTransportConfig(command=_NONEXISTENT_COMMAND))
        decision = PolicyDecision(
            effect="deny", reason="no autorizado por policy de prueba", applied_policy="policy_test"
        )

        result = client.execute("record_note", {"note": "no debería ejecutarse"}, decision)

        assert isinstance(result, ToolExecutionRejected)
        assert result.tool_name == "record_note"
        assert result.effect == "deny"
        assert result.reason == "no autorizado por policy de prueba"

    def test_escalate_hitl_decision_returns_typed_rejection(self) -> None:
        client = McpToolClient(StdioTransportConfig(command=_NONEXISTENT_COMMAND))
        decision = PolicyDecision(
            effect="escalate_hitl",
            reason="escritura: escala a HITL siempre (regla dura 4)",
            applied_policy="policy_test",
        )

        result = client.execute("record_note", {"note": "escritura pendiente"}, decision)

        assert isinstance(result, ToolExecutionRejected)
        assert result.effect == "escalate_hitl"
