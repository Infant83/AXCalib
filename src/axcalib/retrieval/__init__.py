"""Stage-aware historical-case retrieval contracts."""

from axcalib.retrieval.base import (
    CaseRetriever,
    HistoricalCase,
    LexicalRetriever,
    NullRetriever,
    RetrievalHit,
    RetrievalResult,
    load_historical_cases,
)
from axcalib.retrieval.dense import (
    DeterministicFakeEmbedder,
    Embedder,
    InMemoryVectorRetriever,
)

__all__ = [
    "CaseRetriever",
    "HistoricalCase",
    "DeterministicFakeEmbedder",
    "Embedder",
    "InMemoryVectorRetriever",
    "LexicalRetriever",
    "NullRetriever",
    "RetrievalHit",
    "RetrievalResult",
    "load_historical_cases",
]
