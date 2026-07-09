"""Adapter de cliente MCP: implementa `ToolPort` sobre la spec MCP 2025-11-25.

Ver `openspec/changes/c09-mcp-tools/` (proposal, design, specs) para el
contrato completo. El MCP Server de ejemplo de fábrica vive en
`example_server/` (subpaquete separado, ejecutable como proceso propio).
"""

from resultarai.adapters.tools_mcp.client import McpToolClient, ToolExecutionRejected
from resultarai.adapters.tools_mcp.descriptors import ToolDescriptor, parse_tool_descriptor
from resultarai.adapters.tools_mcp.errors import (
    McpCapabilityError,
    McpToolClientError,
    ToolArgumentValidationError,
    UnknownToolError,
)
from resultarai.adapters.tools_mcp.session import (
    McpToolSession,
    ToolCallOutcome,
    ensure_tools_capability,
    paginate_tool_descriptors,
)
from resultarai.adapters.tools_mcp.transports import (
    StdioTransportConfig,
    StreamableHttpTransportConfig,
    TransportConfig,
    open_transport,
)

__all__ = [
    "McpCapabilityError",
    "McpToolClient",
    "McpToolClientError",
    "McpToolSession",
    "StdioTransportConfig",
    "StreamableHttpTransportConfig",
    "ToolArgumentValidationError",
    "ToolCallOutcome",
    "ToolDescriptor",
    "ToolExecutionRejected",
    "TransportConfig",
    "UnknownToolError",
    "ensure_tools_capability",
    "open_transport",
    "paginate_tool_descriptors",
    "parse_tool_descriptor",
]
