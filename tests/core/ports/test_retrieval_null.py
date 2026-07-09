"""Tests for NullRetrievalAdapter."""

from resultarai.core.ports import NullRetrievalAdapter, RetrievalPort


def test_null_retrieval_adapter() -> None:
    """Verify that NullRetrievalAdapter returns empty lists and does no I/O."""
    adapter: RetrievalPort = NullRetrievalAdapter()

    # Verify it implements RetrievalPort methods and returns empty list
    assert adapter.retrieve("search query") == []
    assert adapter.retrieve("another query", limit=5) == []

    # Verify docstring contains the expected design note
    assert adapter.__doc__ is not None
    assert "RAG no implementado — puerta abierta (docs/07 decisión 5)" in adapter.__doc__
