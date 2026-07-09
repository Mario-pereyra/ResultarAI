"""Tests de contrato: ejecucion gobernada de Tools MCP (c09, tarea 2.4).

Cubre los scenarios de la Requirement "Ejecucion gobernada por la clasificacion con
emision de AuditEvent" y la parte de flujo de "Tool del server sin ToolManifest activo no
existe" de `openspec/changes/c09-mcp-tools/specs/tool-registry-binding/spec.md`:

- "Tool del server sin ToolManifest activo no existe": deny sin Policy Gate ni tools/call,
  con AuditEvent.
- "Lectura permitida se ejecuta y se audita": allow + tools/call real por stdio +
  AuditEvent allow con result_summary.
- "Lectura sin Policy que la permita se bloquea": deny-by-default, sin tools/call.
- "Escritura escala a HITL siempre y no se ejecuta": escalate_hitl incondicional aunque
  una Policy autorice writes; sin tools/call; evento en espera.
- "La tool de lectura del server de ejemplo corre end-to-end": criterio de salida del
  roadmap, resolviendo el toolset de la Skill (regla dura 3) y ejecutando contra el
  example_server real por stdio.

Para verificar "NO se emite tools/call" se usa un transport spy que apunta a un comando
inexistente: si el executor intentara ejecutar, fallaria al lanzar el subproceso en vez de
devolver la decision esperada (patron de `test_client.py`).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

from resultarai.adapters.skills_fs.loader import FilesystemSkillPackageAdapter
from resultarai.adapters.tools_mcp.governed import EndpointResolutionError, GovernedToolExecutor
from resultarai.adapters.tools_mcp.session import ToolCallOutcome
from resultarai.adapters.tools_mcp.transports import StdioTransportConfig, TransportConfig
from resultarai.core.audit import AuditEvent, ToolCallStatus, project_visible_tool_call
from resultarai.core.manifests import PolicyManifest
from resultarai.core.registries import Registries, load_registries
from resultarai.core.skills.toolset import resolve_executable_toolset

_SERVER_MODULE = "resultarai.adapters.tools_mcp.example_server"
_NONEXISTENT_COMMAND = "comando-mcp-que-no-existe-resultarai-c09-governed"
_ENDPOINT_REF = "example_mcp_endpoint"


def _find_manifests_dir() -> Path:
    start = Path(__file__).resolve()
    for candidate in (start, *start.parents):
        if (candidate / "pyproject.toml").is_file() and (candidate / "manifests").is_dir():
            return candidate / "manifests"
    raise RuntimeError("no se encontro manifests/ subiendo desde el archivo de test")


_MANIFESTS_DIR = _find_manifests_dir()


@pytest.fixture(scope="module")
def registries() -> Registries:
    return load_registries(_MANIFESTS_DIR)


def _real_resolver(cwd: Path) -> dict[str, TransportConfig]:
    """Resolver endpoint_ref -> transport que lanza el example_server real por stdio."""
    transport = StdioTransportConfig(
        command=sys.executable, args=("-m", _SERVER_MODULE), cwd=str(cwd)
    )
    return {_ENDPOINT_REF: transport}


def _spy_resolver() -> dict[str, TransportConfig]:
    """Resolver cuyo transport falla si se abre: prueba que NO se emitio tools/call."""
    return {_ENDPOINT_REF: StdioTransportConfig(command=_NONEXISTENT_COMMAND)}


def _invoke(
    executor: GovernedToolExecutor,
    tool_id: str,
    arguments: dict[str, Any],
    *,
    skill: str = "example_skill",
) -> Any:
    return executor.invoke(
        tool_id,
        arguments,
        user="ana",
        agent="default_chat",
        skill=skill,
        environment="test",
    )


class TestToolWithoutActiveManifestDoesNotExist:
    """Scenario: Tool del server sin ToolManifest activo no existe."""

    def test_registry_miss_denies_without_gate_or_tools_call_and_audits(
        self, registries: Registries
    ) -> None:
        events: list[AuditEvent] = []
        executor = GovernedToolExecutor(
            tool_registry=registries.tools,
            active_policies=list(registries.policies.invocable()),
            endpoint_resolver=_spy_resolver(),  # nunca se abre: no hay tools/call
            audit_sink=events,
        )

        result = _invoke(executor, "tool_que_no_existe_en_el_registry", {"text": "x"})

        assert result.decision.effect == "deny"
        assert result.decision.applied_policy == "tool_not_in_registry"
        assert "tool_que_no_existe_en_el_registry" in result.decision.reason
        assert result.outcome is None
        assert result.duration_ms is None
        # El intento queda registrado en exactamente un AuditEvent deny.
        assert len(events) == 1
        assert events[0].effect == "deny"
        assert events[0].applied_policy == "tool_not_in_registry"
        assert events[0].tool == "tool_que_no_existe_en_el_registry"


class TestAllowedReadRunsAndIsAudited:
    """Scenario: Lectura permitida se ejecuta y se audita."""

    def test_read_with_allowing_policy_executes_and_emits_allow_audit_event(
        self, tmp_path: Path, registries: Registries
    ) -> None:
        events: list[AuditEvent] = []
        executor = GovernedToolExecutor(
            tool_registry=registries.tools,
            active_policies=list(registries.policies.invocable()),
            endpoint_resolver=_real_resolver(tmp_path),
            audit_sink=events,
        )

        result = _invoke(executor, "example_echo", {"text": "hola gobernada"})

        assert result.decision.effect == "allow"
        assert isinstance(result.outcome, ToolCallOutcome)
        assert result.outcome.content == "hola gobernada"
        assert result.duration_ms is not None
        assert result.duration_ms >= 0

        assert len(events) == 1
        event = events[0]
        assert event.effect == "allow"
        assert event.tool == "example_echo"
        assert event.operation_type == "read"
        assert event.result_summary == "hola gobernada"


class TestReadWithoutAllowingPolicyIsBlocked:
    """Scenario: Lectura sin Policy que la permita se bloquea."""

    def test_read_without_any_policy_is_denied_by_default_without_tools_call(
        self, registries: Registries
    ) -> None:
        events: list[AuditEvent] = []
        executor = GovernedToolExecutor(
            tool_registry=registries.tools,
            active_policies=[],  # ninguna Policy concede allow
            endpoint_resolver=_spy_resolver(),  # nunca se abre: no hay tools/call
            audit_sink=events,
        )

        result = _invoke(executor, "example_echo", {"text": "hola"})

        assert result.decision.effect == "deny"
        assert result.decision.applied_policy == "deny_by_default"
        assert result.outcome is None
        assert result.duration_ms is None
        assert len(events) == 1
        assert events[0].effect == "deny"


class TestEndpointResolutionFailureIsAudited:
    """Un `allow` cuyo `endpoint_ref` no resuelve audita la decision antes de propagar.

    Cubre el hallazgo LOW del review final de c09: toda decision del Policy Gate emite su
    `AuditEvent`, incluso cuando un error de configuracion interno (endpoint_resolver sin
    el `endpoint_ref` del binding) impide abrir el transport. No hay `tools/call`.
    """

    def test_allow_with_unresolvable_endpoint_audits_before_raising(
        self, registries: Registries
    ) -> None:
        events: list[AuditEvent] = []
        executor = GovernedToolExecutor(
            tool_registry=registries.tools,
            active_policies=list(registries.policies.invocable()),
            endpoint_resolver={},  # sin mapeo: error de configuracion interno
            audit_sink=events,
        )

        with pytest.raises(EndpointResolutionError) as excinfo:
            _invoke(executor, "example_echo", {"text": "hola"})

        assert _ENDPOINT_REF in str(excinfo.value)
        # La decision allow quedo auditada aunque no hubo tools/call.
        assert len(events) == 1
        event = events[0]
        assert event.effect == "allow"
        assert event.tool == "example_echo"
        assert event.result_summary is not None
        assert "error de configuracion antes de tools/call" in event.result_summary


class TestWriteAlwaysEscalatesToHitl:
    """Scenario: Escritura escala a HITL siempre y no se ejecuta."""

    def test_write_escalates_to_hitl_even_with_a_policy_allowing_writes(
        self, registries: Registries
    ) -> None:
        # Policy que EXPLICITAMENTE autoriza writes: aun asi la escritura escala a HITL
        # de forma incondicional (regla dura 4 / design Decision 4).
        write_allow_policy = PolicyManifest.model_validate(
            {
                "id": "allow_writes_policy",
                "status": "active",
                "version": "1.0.0",
                "applies_to": {"skills": ["example_skill"]},
                "rules": [{"effect": "allow", "when": {"operation_type": "write"}}],
            }
        )
        events: list[AuditEvent] = []
        executor = GovernedToolExecutor(
            tool_registry=registries.tools,
            active_policies=[write_allow_policy],
            endpoint_resolver=_spy_resolver(),  # nunca se abre: no hay tools/call
            audit_sink=events,
        )

        result = _invoke(executor, "example_record_note", {"note": "nota pendiente"})

        assert result.decision.effect == "escalate_hitl"
        assert result.decision.applied_policy == "write_requires_hitl"
        assert result.outcome is None
        assert result.duration_ms is None
        assert len(events) == 1
        assert events[0].effect == "escalate_hitl"

        # El evento queda "en espera de aprobacion" en la proyeccion visible.
        visible = project_visible_tool_call(events[0], result_text=None, duration_ms=None)
        assert visible.status is ToolCallStatus.PENDING_APPROVAL


class TestReadToolRunsEndToEnd:
    """Scenario: La tool de lectura del server de ejemplo corre end-to-end."""

    def test_example_echo_runs_via_the_skill_toolset_against_the_real_server(
        self, tmp_path: Path, registries: Registries
    ) -> None:
        # Regla dura 3: la Tool va via la Skill. Se resuelve el toolset ejecutable como
        # interseccion de los allowed-tools del paquete (SKILL.md) y los tools del Manifest.
        packages_dir = _MANIFESTS_DIR / "skills" / "packages"
        package_port = FilesystemSkillPackageAdapter(packages_dir)
        allowed_tools = package_port.read_metadata("example-utils").get("allowed-tools", [])

        skill = registries.skills.get("example_skill")
        assert skill is not None
        toolset = resolve_executable_toolset(allowed_tools, skill.tools)
        assert "example_echo" in toolset  # la Tool esta permitida via la Skill

        events: list[AuditEvent] = []
        executor = GovernedToolExecutor(
            tool_registry=registries.tools,
            active_policies=list(registries.policies.invocable()),
            endpoint_resolver=_real_resolver(tmp_path),
            audit_sink=events,
        )

        result = _invoke(executor, "example_echo", {"text": "eco de fabrica"})

        assert result.decision.effect == "allow"
        assert isinstance(result.outcome, ToolCallOutcome)
        assert result.outcome.content == "eco de fabrica"

        assert len(events) == 1
        event = events[0]
        assert event.user == "ana"
        assert event.skill == "example_skill"
        assert event.tool == "example_echo"
        assert event.effect == "allow"
        assert event.result_summary == "eco de fabrica"
