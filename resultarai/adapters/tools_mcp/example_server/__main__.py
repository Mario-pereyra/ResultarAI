"""Punto de entrada de proceso del MCP Server de ejemplo de fábrica.

Permite lanzarlo como subproceso por transport stdio con:

    python -m resultarai.adapters.tools_mcp.example_server

El cliente MCP (adapter `tools_mcp`) usa exactamente este comando para
conectarse por stdio al server de ejemplo en los tests de contrato.
"""

from resultarai.adapters.tools_mcp.example_server.server import mcp_app

if __name__ == "__main__":
    mcp_app.run(transport="stdio")
