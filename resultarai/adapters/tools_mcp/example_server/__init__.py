"""MCP Server de ejemplo de fábrica (`example_utilities_server`).

Paquete ejecutable por stdio (`python -m
resultarai.adapters.tools_mcp.example_server`) que expone Tools de utilidades
sin efecto en el ERP ni en red externa. Ver `server.py` para el detalle de
cada Tool y `__main__.py` para el punto de entrada del proceso.
"""

from resultarai.adapters.tools_mcp.example_server.server import mcp_app

__all__ = ["mcp_app"]
