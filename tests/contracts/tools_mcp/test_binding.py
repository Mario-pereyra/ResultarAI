"""Tests de contrato: binding ToolManifest -> (MCP Server + tool_name) (c09, tareas 2.1-2.3).

Cubre los scenarios de las Requirements de
`openspec/changes/c09-mcp-tools/specs/tool-registry-binding/spec.md`:

- "Solo las Tools declaradas en un ToolManifest activo existen para el runtime":
  parte de binding de "Tool del server sin ToolManifest activo no existe" y "Tool con
  ToolManifest activo si es invocable".
- "El ToolManifest fija MCP Server, tool_name y clasificacion inmutable en runtime":
  "El binding resuelve server y tool_name desde el manifiesto", "La clasificacion no se
  puede cambiar en runtime" y "Las annotations del server no alteran la clasificacion".
- "Validacion cruzada del binding contra el MCP Server": "tool_name inexistente en el
  server invalida el binding" (check puro y contra el example_server real por stdio).

Sin `pytest-asyncio`: los tests async ejecutan su cuerpo con `anyio.run(...)`.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import anyio
import pytest
from pydantic import ValidationError

from resultarai.adapters.tools_mcp.binding import (
    BindingValidationError,
    ResolvedToolBinding,
    resolve_tool_binding,
    validate_binding_against_live_server,
    validate_binding_against_server,
)
from resultarai.adapters.tools_mcp.descriptors import ToolDescriptor
from resultarai.adapters.tools_mcp.transports import StdioTransportConfig
from resultarai.core.manifests import ToolManifest
from resultarai.core.manifests.base import RiskLevel
from resultarai.core.manifests.tool import OperationType
from resultarai.core.registries import (
    ManifestRegistry,
    Registries,
    ToolRegistry,
    load_registries,
)

_SERVER_MODULE = "resultarai.adapters.tools_mcp.example_server"


def _find_manifests_dir() -> Path:
    """Resuelve `manifests/` subiendo desde este archivo (no relativo al cwd de pytest)."""
    start = Path(__file__).resolve()
    for candidate in (start, *start.parents):
        if (candidate / "pyproject.toml").is_file() and (candidate / "manifests").is_dir():
            return candidate / "manifests"
    raise RuntimeError("no se encontro manifests/ subiendo desde el archivo de test")


_MANIFESTS_DIR = _find_manifests_dir()


@pytest.fixture(scope="module")
def registries() -> Registries:
    """Los Registries de fabrica REALES (incluye example_echo y example_record_note)."""
    return load_registries(_MANIFESTS_DIR)


def _tool_manifest(
    tool_id: str,
    *,
    status: str = "active",
    operation_type: str = "read",
    level: str = "low",
    tool_name: str = "echo",
) -> ToolManifest:
    """Construye un ToolManifest desde un dict equivalente al YAML normativo."""
    payload: dict[str, Any] = {
        "id": tool_id,
        "name": "Tool de prueba",
        "status": status,
        "version": "1.0.0",
        "type": "mcp_tool",
        "adapter": "mcp",
        "mcp": {
            "server": "example_utilities_server",
            "tool_name": tool_name,
            "spec_revision": "2025-11-25",
            "endpoint_ref": "example_mcp_endpoint",
        },
        "risk": {"level": level, "operation_type": operation_type},
        "permissions": {"mode": "read_only", "requires_human_approval": False},
        "security": {
            "allow_sql_freeform": False,
            "allow_dynamic_table_access": False,
            "mask_sensitive_fields": True,
        },
        "audit": {
            "log_request": True,
            "log_response_summary": True,
            "log_user": True,
            "log_tenant": True,
        },
        "evals": {"status": "placeholder", "template": "t"},
    }
    return ToolManifest.model_validate(payload)


def _example_server_transport(cwd: Path) -> StdioTransportConfig:
    return StdioTransportConfig(command=sys.executable, args=("-m", _SERVER_MODULE), cwd=str(cwd))


class TestOnlyActiveManifestsExist:
    """Requirement: solo las Tools de un ToolManifest activo existen para el runtime."""

    def test_tool_without_active_manifest_does_not_resolve(self) -> None:
        # Un manifiesto `draft` esta catalogado pero NO es invocable: no existe para el
        # runtime. Un tool_id no catalogado tampoco. Ambos devuelven None (sin binding, sin
        # Policy Gate, sin tools/call).
        registry: ToolRegistry = ManifestRegistry([_tool_manifest("draft_tool", status="draft")])

        assert resolve_tool_binding("draft_tool", registry) is None
        assert resolve_tool_binding("tool_no_catalogada", registry) is None

    def test_tool_with_active_manifest_resolves_to_a_binding(self, registries: Registries) -> None:
        binding = resolve_tool_binding("example_echo", registries.tools)

        assert isinstance(binding, ResolvedToolBinding)
        assert binding.manifest_id == "example_echo"


class TestBindingResolvesServerAndClassificationFromManifest:
    """Requirement: el ToolManifest fija server, tool_name y clasificacion."""

    def test_binding_reads_server_tool_name_and_classification_from_manifest(
        self, registries: Registries
    ) -> None:
        binding = resolve_tool_binding("example_echo", registries.tools)
        assert binding is not None

        assert binding.server == "example_utilities_server"
        assert binding.tool_name == "echo"
        assert binding.endpoint_ref == "example_mcp_endpoint"
        assert binding.operation_type is OperationType.READ
        assert binding.risk_level is RiskLevel.LOW
        assert binding.manifest_version == "1.0.0"


class TestClassificationIsImmutableAtRuntime:
    """Requirement: la clasificacion no se puede cambiar en runtime (frozen)."""

    def test_manifest_risk_classification_cannot_be_reassigned(
        self, registries: Registries
    ) -> None:
        manifest = registries.tools.get("example_echo")
        assert manifest is not None

        with pytest.raises(ValidationError):
            manifest.risk.operation_type = OperationType.WRITE  # type: ignore[misc]

        with pytest.raises(ValidationError):
            manifest.risk.level = RiskLevel.CRITICAL  # type: ignore[misc]

    def test_resolved_binding_classification_cannot_be_reassigned(
        self, registries: Registries
    ) -> None:
        binding = resolve_tool_binding("example_echo", registries.tools)
        assert binding is not None

        with pytest.raises(ValidationError):
            binding.operation_type = OperationType.WRITE  # type: ignore[misc]

        with pytest.raises(ValidationError):
            binding.risk_level = RiskLevel.CRITICAL  # type: ignore[misc]


class TestServerAnnotationsDoNotAlterClassification:
    """Requirement: las annotations del server (no confiables) no alteran la clasificacion."""

    def test_read_only_hint_annotation_does_not_downgrade_a_write_tool(
        self, registries: Registries
    ) -> None:
        # El descriptor del server anuncia la escritura como readOnlyHint (spec MCP:
        # annotations no confiables). La gobernanza usa la clasificacion del manifiesto.
        deceptive_descriptor = ToolDescriptor(
            name="record_note",
            description="simula registrar una nota",
            input_schema={"type": "object", "properties": {"note": {"type": "string"}}},
            annotations={"readOnlyHint": True},
        )
        assert deceptive_descriptor.annotations == {"readOnlyHint": True}

        binding = resolve_tool_binding("example_record_note", registries.tools)
        assert binding is not None

        # El binding no consulta las annotations: write se mantiene write, critical critical.
        assert binding.operation_type is OperationType.WRITE
        assert binding.risk_level is RiskLevel.CRITICAL


class TestCrossValidationAgainstServer:
    """Requirement: validacion cruzada del binding contra el MCP Server."""

    def test_pure_check_passes_when_tool_name_is_present(self) -> None:
        manifest = _tool_manifest("t_echo", tool_name="echo")
        # No lanza: "echo" esta en el conjunto de tools del server.
        validate_binding_against_server(manifest, {"echo", "calculate", "record_note"})

    def test_pure_check_fails_naming_the_absent_tool_name(self) -> None:
        manifest = _tool_manifest("t_missing", tool_name="tool_inexistente")

        with pytest.raises(BindingValidationError) as exc_info:
            validate_binding_against_server(manifest, {"echo", "calculate"})

        assert "tool_inexistente" in str(exc_info.value)
        assert exc_info.value.tool_name == "tool_inexistente"

    def test_factory_manifests_validate_against_real_example_server(
        self, tmp_path: Path, registries: Registries
    ) -> None:
        transport = _example_server_transport(tmp_path)
        for tool_id in ("example_echo", "example_record_note"):
            manifest = registries.tools.get(tool_id)
            assert manifest is not None
            # No lanza: el tool_name del manifiesto existe en el tools/list real del server.
            anyio.run(validate_binding_against_live_server, manifest, transport)

    def test_nonexistent_tool_name_invalidates_binding_against_real_server(
        self, tmp_path: Path
    ) -> None:
        manifest = _tool_manifest("t_bad", tool_name="tool_que_el_server_no_expone")
        transport = _example_server_transport(tmp_path)

        with pytest.raises(BindingValidationError) as exc_info:
            anyio.run(validate_binding_against_live_server, manifest, transport)

        assert "tool_que_el_server_no_expone" in str(exc_info.value)
