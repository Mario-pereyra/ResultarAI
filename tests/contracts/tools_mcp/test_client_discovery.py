"""Tests de contrato: descubrimiento de Tools (`tools/list`) con paginación.

Cubre la Requirement "Descubrimiento de Tools vía tools/list con paginación"
(`openspec/changes/c09-mcp-tools/specs/mcp-tools/spec.md`):

- "Listado completo con paginación": `paginate_tool_descriptors` recorre
  todas las páginas siguiendo `cursor`/`nextCursor` con un `lister` stub
  (sin server real), usando las respuestas canónicas
  `TOOLS_LIST_PAGE_1`/`TOOLS_LIST_PAGE_2` de los fixtures.
- "Descriptor sin inputSchema válido rechazado": `TOOL_DESCRIPTOR_INVALID_
  INPUT_SCHEMA` (`inputSchema: null`) se descarta, tanto vía
  `parse_tool_descriptor` directo como intercalado en una página junto a
  descriptores válidos.
"""

from __future__ import annotations

import anyio

from resultarai.adapters.tools_mcp.descriptors import ToolDescriptor, parse_tool_descriptor
from resultarai.adapters.tools_mcp.session import ToolsPage, paginate_tool_descriptors
from tests.contracts.tools_mcp.fixtures import canonical_responses


class TestPaginationFollowsCursorUntilExhausted:
    """Escenario: 'Listado completo con paginación'."""

    def test_two_pages_yield_the_full_set_of_descriptors(self) -> None:
        seen_cursors: list[str | None] = []

        async def _stub_lister(cursor: str | None) -> ToolsPage:
            seen_cursors.append(cursor)
            if cursor is None:
                return canonical_responses.TOOLS_LIST_PAGE_1["result"]  # type: ignore[no-any-return]
            if cursor == "page-2":
                return canonical_responses.TOOLS_LIST_PAGE_2["result"]  # type: ignore[no-any-return]
            raise AssertionError(f"cursor inesperado: {cursor!r}")

        descriptors = anyio.run(paginate_tool_descriptors, _stub_lister)

        # La paginación se detiene al agotar el nextCursor de la última página.
        assert seen_cursors == [None, "page-2"]
        assert {d.name for d in descriptors} == {"echo", "get_current_time", "calculate"}
        assert all(isinstance(d, ToolDescriptor) for d in descriptors)

    def test_each_descriptor_keeps_its_input_schema(self) -> None:
        async def _stub_lister(cursor: str | None) -> ToolsPage:
            if cursor is None:
                return canonical_responses.TOOLS_LIST_PAGE_1["result"]  # type: ignore[no-any-return]
            return canonical_responses.TOOLS_LIST_PAGE_2["result"]  # type: ignore[no-any-return]

        descriptors = anyio.run(paginate_tool_descriptors, _stub_lister)

        echo = next(d for d in descriptors if d.name == "echo")
        assert echo.input_schema == {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        }


class TestInvalidInputSchemaDescriptorIsRejected:
    """Escenario: 'Descriptor sin inputSchema válido rechazado'."""

    def test_parse_tool_descriptor_returns_none_for_null_input_schema(self) -> None:
        descriptor = parse_tool_descriptor(canonical_responses.TOOL_DESCRIPTOR_INVALID_INPUT_SCHEMA)
        assert descriptor is None

    def test_pagination_discards_invalid_descriptor_among_valid_ones(self) -> None:
        valid_tool = canonical_responses.TOOLS_LIST_PAGE_1["result"]["tools"][0]

        async def _stub_lister(cursor: str | None) -> ToolsPage:
            return {
                "tools": [valid_tool, canonical_responses.TOOL_DESCRIPTOR_INVALID_INPUT_SCHEMA],
                "nextCursor": None,
            }

        descriptors = anyio.run(paginate_tool_descriptors, _stub_lister)

        assert {d.name for d in descriptors} == {"echo"}

    def test_descriptor_with_output_schema_is_parsed_and_kept(self) -> None:
        descriptor = parse_tool_descriptor(canonical_responses.TOOL_DESCRIPTOR_WITH_OUTPUT_SCHEMA)
        assert descriptor is not None
        assert (
            descriptor.output_schema
            == canonical_responses.TOOL_DESCRIPTOR_WITH_OUTPUT_SCHEMA["outputSchema"]
        )
