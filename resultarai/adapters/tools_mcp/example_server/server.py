"""MCP Server de ejemplo de fábrica: `example_utilities_server`.

Server de utilidades genérico, sin dependencias de red externa ni acceso al
ERP, ejecutable por transport stdio (ver `__main__.py`). Sirve de plantilla
para los MCP Servers reales de la Etapa P (personalización Protheus): cada
Tool declara su `inputSchema` vía type hints (FastMCP los genera a partir de
la firma) y su descripción vía docstring.

Expone dos tipos de Tool según la clasificación de gobernanza (`docs/06-
seguridad-gobernanza.md`):

- Lectura (`echo`, `get_current_time`, `calculate`): no tienen efecto en
  ningún sistema, solo devuelven datos derivados de sus argumentos.
- Escritura simulada (`record_note`): NO escribe archivos ni toca red ni
  sistemas — devuelve una confirmación textual que deja explícito que es
  simulada. Existe para ejercer el camino `escalate_hitl` del Policy Gate
  (regla dura 4) sin ningún efecto real.

Los nombres de las Tools son exactamente los nombres de las funciones
decoradas: `echo`, `get_current_time`, `calculate`, `record_note`. El
`ToolManifest` `example_echo` (`manifests/tools/example_echo.yaml`) bindea
`tool_name: echo` contra el server conceptual `example_utilities_server`
definido aquí.
"""

from __future__ import annotations

import ast
import operator
from collections.abc import Callable
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from mcp.server.fastmcp import FastMCP

__all__ = ["mcp_app"]

# Instancia FastMCP: nombre conceptual del server de fábrica (ver `mcp.server`
# en `manifests/tools/example_echo.yaml`).
mcp_app: FastMCP = FastMCP("example_utilities_server")


# --- Tool de lectura: echo -------------------------------------------------


@mcp_app.tool()
def echo(text: str) -> str:
    """Devuelve exactamente el texto recibido, sin transformarlo.

    Tool de lectura: no tiene efecto en ningún sistema.
    """
    return text


# --- Tool de lectura: get_current_time --------------------------------------


@mcp_app.tool()
def get_current_time(timezone: str = "UTC") -> str:
    """Devuelve la fecha y hora actual en formato ISO 8601 para el timezone dado.

    Tool de lectura: no tiene efecto en ningún sistema. `timezone` debe ser un
    nombre de zona horaria IANA (p. ej. "UTC", "America/La_Paz"); si no es
    válido se lanza un `ValueError` accionable.
    """
    try:
        zona = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(
            f"Timezone inválido: {timezone!r}. Debe ser un nombre de zona horaria "
            "IANA válido, por ejemplo 'UTC' o 'America/La_Paz'."
        ) from exc
    return datetime.now(zona).isoformat()


# --- Tool de lectura: calculate ---------------------------------------------

# Solo operadores aritméticos simples: evaluación segura vía `ast`, PROHIBIDO
# `eval()`/`exec()`. Ver Requirement "MCP Server de ejemplo de fábrica" en
# openspec/changes/c09-mcp-tools/specs/mcp-tools/spec.md.
_ALLOWED_BINARY_OPS: dict[type[ast.operator], Callable[[float, float], float]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_ALLOWED_UNARY_OPS: dict[type[ast.unaryop], Callable[[float], float]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _eval_arithmetic_node(node: ast.AST) -> float:
    """Evalúa recursivamente un nodo `ast` restringido a aritmética simple.

    Solo acepta constantes numéricas, operadores binarios/unarios permitidos
    y paréntesis (implícitos en el árbol). Cualquier otro nodo (nombres,
    llamadas, atributos, comprensiones, etc.) lanza `ValueError`.
    """
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, int | float):
            raise ValueError(
                f"Solo se permiten números en la expresión, se recibió: {node.value!r}"
            )
        return node.value

    if isinstance(node, ast.BinOp):
        binary_op_func = _ALLOWED_BINARY_OPS.get(type(node.op))
        if binary_op_func is None:
            raise ValueError(f"Operador no permitido: {type(node.op).__name__}")
        left = _eval_arithmetic_node(node.left)
        right = _eval_arithmetic_node(node.right)
        try:
            return binary_op_func(left, right)
        except ZeroDivisionError as exc:
            raise ValueError("División por cero en la expresión.") from exc

    if isinstance(node, ast.UnaryOp):
        unary_op_func = _ALLOWED_UNARY_OPS.get(type(node.op))
        if unary_op_func is None:
            raise ValueError(f"Operador unario no permitido: {type(node.op).__name__}")
        return unary_op_func(_eval_arithmetic_node(node.operand))

    raise ValueError(f"Expresión no soportada: elemento '{type(node).__name__}' no permitido")


@mcp_app.tool()
def calculate(expression: str) -> str:
    """Evalúa una expresión aritmética simple y devuelve el resultado como texto.

    Tool de lectura: no tiene efecto en ningún sistema. Soporta únicamente
    números, paréntesis, `+ - * / // % **` y el signo unario `+`/`-`. La
    evaluación es segura (recorrido de `ast`, sin `eval()`/`exec()`); una
    expresión inválida o no soportada lanza `ValueError` con un mensaje
    accionable.
    """
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ValueError(
            f"Expresión aritmética inválida: {expression!r}. Usa solo números, "
            "paréntesis y los operadores + - * / // % **."
        ) from exc

    result = _eval_arithmetic_node(tree.body)
    return str(result)


# --- Tool de "escritura" simulada: record_note ------------------------------


@mcp_app.tool()
def record_note(note: str) -> str:
    """Simula el registro de una nota, SIN efecto real alguno.

    Tool de escritura simulada: no escribe archivos, no abre conexiones de
    red ni toca ningún sistema externo. Existe únicamente para ejercer el
    camino de gobernanza `escalate_hitl` (regla dura 4): el Policy Gate SHALL
    escalar siempre esta invocación antes de llegar aquí. La respuesta deja
    explícito que la operación es simulada.
    """
    return f"nota registrada (simulado, sin efecto real): {note}"
