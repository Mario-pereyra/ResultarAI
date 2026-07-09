"""Descriptor tipado de una Tool MCP y su parseo desde un payload sin validar.

`parse_tool_descriptor` acepta indistintamente un `Mapping` crudo (el shape
JSON-RPC exacto de `tools/list`, como en
`tests/contracts/tools_mcp/fixtures/canonical_responses.py`) o un objeto
`mcp.types.Tool` ya validado por el SDK — ambos exponen los mismos campos
(`name`, `description`, `inputSchema`, `outputSchema`, `annotations`), solo
que uno vía `__getitem__`/`.get` y el otro vía atributos. Esto permite testear
el descarte de descriptores inválidos (Escenario "Descriptor sin inputSchema
válido rechazado", `openspec/changes/c09-mcp-tools/specs/mcp-tools/spec.md`)
con las respuestas canónicas de los fixtures, sin depender de un MCP Server
real ni de que el SDK acepte construir un `Tool` con `inputSchema: None`
(su propio modelo Pydantic lo tipa como `dict[str, Any]` obligatorio, así que
un payload verdaderamente inválido nunca llegaría a instanciarse como `Tool`).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

__all__ = ["ToolDescriptor", "parse_tool_descriptor"]


@dataclass(frozen=True, slots=True)
class ToolDescriptor:
    """Descriptor tipado de una Tool MCP, ya validado y listo para invocación.

    `annotations` se conserva solo con fines informativos: por la Decision 3
    de `openspec/changes/c09-mcp-tools/design.md`, el cliente MCP NUNCA deriva
    la clasificación lectura/escritura ni el nivel de riesgo de aquí — esa
    clasificación es autoritativa en el `ToolManifest` (sección 2 de este
    change). Las `annotations` del server no son confiables (spec §Tool
    Safety).
    """

    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any] | None = None
    annotations: dict[str, Any] | None = None


def _field(source: Any, key: str) -> Any:
    """Lee `key` de `source`, que puede ser un `Mapping` crudo o un objeto SDK con atributos."""
    if isinstance(source, Mapping):
        return source.get(key)
    return getattr(source, key, None)


def _is_valid_object_json_schema(schema: Any) -> bool:
    """True si `schema` es un dict JSON Schema que describe explícitamente un objeto.

    Rechaza: no-dict, `None`, o un dict cuyo `type` declarado no sea
    `"object"` (p. ej. faltante o distinto). Los `inputSchema`/`outputSchema`
    de Tools MCP siempre describen los parámetros/resultado como un objeto
    JSON, así que exigir `type == "object"` explícito es una regla simple y
    suficiente para el subconjunto que este cliente soporta.
    """
    return isinstance(schema, dict) and schema.get("type") == "object"


def _normalize_annotations(annotations: Any) -> dict[str, Any] | None:
    """Convierte `annotations` (dict crudo, `ToolAnnotations` Pydantic, o None) a `dict | None`."""
    if annotations is None:
        return None
    if isinstance(annotations, Mapping):
        return dict(annotations)
    model_dump = getattr(annotations, "model_dump", None)
    if callable(model_dump):
        dumped: dict[str, Any] = model_dump(exclude_none=True)
        return dumped
    return None


def parse_tool_descriptor(sdk_tool: Any) -> ToolDescriptor | None:
    """Parsea una Tool cruda (dict JSON-RPC o `mcp.types.Tool`) a un `ToolDescriptor`.

    Devuelve `None` (descarte silencioso, no excepción) si `inputSchema` no es
    un objeto JSON Schema válido: no es un dict, es `None`, o no describe un
    objeto. El llamador (`paginate_tool_descriptors` en `session.py`) filtra
    estos `None` y no ofrece la Tool para invocación.
    """
    name = _field(sdk_tool, "name")
    if not isinstance(name, str) or not name:
        return None

    input_schema = _field(sdk_tool, "inputSchema")
    if not _is_valid_object_json_schema(input_schema):
        return None

    description = _field(sdk_tool, "description")
    if not isinstance(description, str):
        description = ""

    output_schema = _field(sdk_tool, "outputSchema")
    if not isinstance(output_schema, dict):
        output_schema = None

    annotations = _normalize_annotations(_field(sdk_tool, "annotations"))

    return ToolDescriptor(
        name=name,
        description=description,
        input_schema=input_schema,
        output_schema=output_schema,
        annotations=annotations,
    )
