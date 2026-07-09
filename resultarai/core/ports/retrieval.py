"""RetrievalPort and NullRetrievalAdapter definition."""

from typing import Any, Protocol


class RetrievalPort(Protocol):
    """Protocol for RAG retrieval."""

    def retrieve(self, query: str, limit: int = 10) -> list[Any]:
        """Retrieve relevant context for a query."""
        ...


class NullRetrievalAdapter:
    """Null adapter implementing RetrievalPort.

    RAG no implementado — puerta abierta (docs/07 decisión 5).
    """

    def retrieve(self, query: str, limit: int = 10) -> list[Any]:
        """Always returns an empty list, doing no I/O."""
        return []
