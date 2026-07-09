"""Helper de prueba: MCP Server mínimo servido por Streamable HTTP en localhost.

Levanta un `FastMCP` con una única Tool `ping` (lectura, sin efecto), lo monta
como app Streamable HTTP (`streamable_http_app()`) y lo sirve con `uvicorn`
en un hilo de fondo sobre un puerto efímero de `127.0.0.1`. No toca red
externa: todo el tráfico queda dentro de la máquina de pruebas.

Uso:

    with run_http_test_server() as base_url:
        # base_url ya acepta conexiones, p. ej. "http://127.0.0.1:54321/mcp"
        ...
"""

from __future__ import annotations

import contextlib
import socket
import threading
import time
from collections.abc import Iterator

import uvicorn
from mcp.server.fastmcp import FastMCP

__all__ = ["run_http_test_server"]

_HOST = "127.0.0.1"
_STARTUP_TIMEOUT_SECONDS = 5.0
_SHUTDOWN_TIMEOUT_SECONDS = 5.0


def _build_ping_app() -> FastMCP:
    """Construye el FastMCP mínimo de prueba con la única Tool `ping`."""
    app = FastMCP("mcp_http_test_server")

    @app.tool()
    def ping() -> str:
        """Responde 'pong'; sirve solo para verificar que el server de prueba está vivo."""
        return "pong"

    return app


def _wait_until_started(server: uvicorn.Server, timeout: float) -> None:
    """Espera (polling) a que `uvicorn.Server` termine su startup."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if server.started:
            return
        time.sleep(0.02)
    raise TimeoutError(f"El MCP Server de prueba HTTP no arrancó en {timeout}s")


def _wait_until_accepting_connections(host: str, port: int, timeout: float) -> None:
    """Espera (polling) a que el puerto acepte conexiones TCP antes de hacer yield."""
    deadline = time.monotonic() + timeout
    last_error: OSError | None = None
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.2):
                return
        except OSError as exc:  # pragma: no cover - depende de timing del SO
            last_error = exc
            time.sleep(0.02)
    raise TimeoutError(
        f"El MCP Server de prueba HTTP no aceptó conexiones en {host}:{port} tras {timeout}s"
    ) from last_error


@contextlib.contextmanager
def run_http_test_server() -> Iterator[str]:
    """Context manager que levanta el MCP Server de prueba por Streamable HTTP.

    Hace yield de la URL base del endpoint MCP (p. ej.
    "http://127.0.0.1:54321/mcp") solo después de confirmar que el puerto
    acepta conexiones, y apaga el server de forma ordenada al salir.
    """
    app = _build_ping_app()
    starlette_app = app.streamable_http_app()

    # port=0: el SO asigna un puerto efímero libre; se lee el puerto real tras
    # el arranque desde el socket ya bindeado (evita condiciones de carrera).
    config = uvicorn.Config(starlette_app, host=_HOST, port=0, log_level="warning")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    try:
        _wait_until_started(server, _STARTUP_TIMEOUT_SECONDS)
        bound_socket = server.servers[0].sockets[0]
        port = bound_socket.getsockname()[1]
        _wait_until_accepting_connections(_HOST, port, _STARTUP_TIMEOUT_SECONDS)

        base_url = f"http://{_HOST}:{port}{app.settings.streamable_http_path}"
        yield base_url
    finally:
        server.should_exit = True
        thread.join(timeout=_SHUTDOWN_TIMEOUT_SECONDS)
