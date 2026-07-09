"""Test de humo: `core` importa limpio, sin red y sin frameworks."""

import sys


def test_core_and_subpackages_import_clean() -> None:
    """Los subpaquetes del nucleo importan sin error ni efectos secundarios de I/O."""
    import resultarai.core
    import resultarai.core.manifests
    import resultarai.core.policy
    import resultarai.core.ports
    import resultarai.core.registries
    import resultarai.core.routing

    for module in (
        resultarai.core,
        resultarai.core.manifests,
        resultarai.core.policy,
        resultarai.core.ports,
        resultarai.core.registries,
        resultarai.core.routing,
    ):
        assert module is not None


def test_core_import_does_not_pull_in_frameworks() -> None:
    """Importar `resultarai.core` no debe cargar los adapters prohibidos (regla dura 1)."""
    forbidden_prefixes = ("langgraph", "litellm", "langfuse", "fastapi", "httpx")

    # Clean sys.modules of forbidden prefixes so that test order does not affect this test
    for prefix in forbidden_prefixes:
        for name in list(sys.modules.keys()):
            if name.startswith(prefix):
                sys.modules.pop(name, None)

    import resultarai.core  # noqa: F401

    leaked = {name for name in sys.modules if name.startswith(forbidden_prefixes)}
    assert not leaked, f"Importar core cargo modulos de framework prohibidos: {leaked}"


def test_pydantic_is_importable() -> None:
    """Pydantic es la unica dependencia permitida del nucleo (regla dura 1)."""
    import pydantic

    assert pydantic.VERSION.startswith("2")
