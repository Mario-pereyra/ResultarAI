"""Tests del Tool Manifest: referencia MCP obligatoria, clasificacion fija y regla dura 5.

Se importa directo del modulo (`resultarai.core.manifests.tool`), no del paquete, porque
`__init__.py` lo pueblan otros changes en paralelo. Se valida con `model_validate` sobre
dicts equivalentes al YAML normativo de docs/04-manifiestos.md (asi llega en produccion:
YAML -> dict -> validacion).
"""

from typing import Any

import pytest
from pydantic import ValidationError

from resultarai.core.manifests.tool import (
    OperationType,
    RiskLevel,
    ToolManifest,
    ToolType,
)


def _payload(**overrides: Any) -> dict[str, Any]:
    """Dict equivalente al Tool Manifest de lectura de ejemplo (docs/04-manifiestos.md)."""
    data: dict[str, Any] = {
        "id": "example_echo",
        "name": "Echo de Ejemplo",
        "status": "active",
        "version": "1.0.0",
        "type": "mcp_tool",
        "adapter": "mcp",
        "mcp": {
            "server": "example_utils_server",
            "tool_name": "echo",
            "spec_revision": "2025-11-25",
            "endpoint_ref": "example_mcp_endpoint",
        },
        "risk": {
            "level": "low",
            "operation_type": "read",
        },
        "permissions": {
            "mode": "read_only",
            "requires_human_approval": False,
        },
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
        "evals": {
            "status": "placeholder",
            "template": "tool_eval_template",
        },
    }
    data.update(overrides)
    return data


def test_reading_tool_example_is_accepted() -> None:
    manifest = ToolManifest.model_validate(_payload())

    assert manifest.id == "example_echo"
    assert manifest.type is ToolType.MCP_TOOL
    assert manifest.mcp.server == "example_utils_server"
    assert manifest.mcp.tool_name == "echo"
    assert manifest.risk.level is RiskLevel.LOW
    assert manifest.risk.operation_type is OperationType.READ
    assert manifest.security.allow_sql_freeform is False


def test_sql_freeform_true_rejected_citing_hard_rule_5() -> None:
    security = _payload()["security"]
    security["allow_sql_freeform"] = True

    with pytest.raises(ValidationError) as exc_info:
        ToolManifest.model_validate(_payload(security=security))

    message = str(exc_info.value)
    assert "regla dura 5" in message
    assert "allow_sql_freeform" in message


@pytest.mark.parametrize("missing", ["server", "tool_name"])
def test_missing_mcp_binding_rejected(missing: str) -> None:
    mcp = _payload()["mcp"]
    del mcp[missing]

    with pytest.raises(ValidationError) as exc_info:
        ToolManifest.model_validate(_payload(mcp=mcp))

    assert missing in str(exc_info.value)


@pytest.mark.parametrize("missing", ["level", "operation_type"])
def test_missing_risk_classification_rejected(missing: str) -> None:
    risk = _payload()["risk"]
    del risk[missing]

    with pytest.raises(ValidationError) as exc_info:
        ToolManifest.model_validate(_payload(risk=risk))

    assert missing in str(exc_info.value)
