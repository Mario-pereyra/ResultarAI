"""Tests de tabla para la intersección de toolset ejecutable."""

from __future__ import annotations

import pytest

from resultarai.core.skills.toolset import resolve_executable_toolset


@pytest.mark.parametrize(
    ("package_tools", "manifest_tools", "expected"),
    [
        # Tool en ambos → en el resultado
        (["echo", "search"], ["echo", "format"], frozenset({"echo"})),
        # Tool solo en paquete → no en el resultado
        (["echo", "search"], ["format"], frozenset()),
        # Tool solo en manifiesto → no en el resultado
        (["echo"], ["search", "format"], frozenset()),
        # Ambas listas vacías → vacío
        ([], [], frozenset()),
        # Paquete vacío → vacío
        ([], ["echo"], frozenset()),
        # Manifiesto vacío → vacío (no debería pasar por schema, pero la función es robusta)
        (["echo"], [], frozenset()),
        # Intersección completa (todas coinciden)
        (["echo", "search"], ["echo", "search"], frozenset({"echo", "search"})),
        # Múltiples en ambos, intersección parcial
        (
            ["echo", "search", "format"],
            ["search", "delete", "format"],
            frozenset({"search", "format"}),
        ),
        # Un solo tool en ambos
        (["echo"], ["echo"], frozenset({"echo"})),
        # Duplicados en la entrada no afectan el resultado
        (["echo", "echo"], ["echo", "echo"], frozenset({"echo"})),
    ],
    ids=[
        "tool_in_both",
        "tool_only_in_package",
        "tool_only_in_manifest",
        "both_empty",
        "package_empty",
        "manifest_empty",
        "full_intersection",
        "partial_intersection",
        "single_match",
        "duplicates_ignored",
    ],
)
def test_resolve_executable_toolset(
    package_tools: list[str],
    manifest_tools: list[str],
    expected: frozenset[str],
) -> None:
    """La intersección produce exactamente los tool ids comunes a ambas listas."""
    result = resolve_executable_toolset(package_tools, manifest_tools)
    assert result == expected
    assert isinstance(result, frozenset)
