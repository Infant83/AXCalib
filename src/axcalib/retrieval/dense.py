"""Deterministic fake embedding contract for weak offline vector-path validation."""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Sequence
from typing import Protocol

from axcalib.retrieval.base import (
    HistoricalCase,
    RetrievalHit,
    RetrievalResult,
)


class Embedder(Protocol):
    """Provider-independent embedding contract."""

    model_id: str
    dimension: int

    def embed(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        """Return one fixed-dimension vector per text."""

        ...


class DeterministicFakeEmbedder:
    """Hash tokens into vectors for contract tests; it has no semantic quality claim."""

    model_id = "axcalib.fake-embedding/v1"

    def __init__(self, dimension: int = 32) -> None:
        if dimension < 8 or dimension > 4096:
            raise ValueError("fake embedding dimension must be between 8 and 4096")
        self.dimension = dimension

    def embed(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        return tuple(self._embed_one(text) for text in texts)

    def _embed_one(self, text: str) -> tuple[float, ...]:
        values = [0.0] * self.dimension
        tokens = re.findall(r"[0-9a-zA-Z가-힣_]+", text.casefold())
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            values[index] += 1.0
        norm = math.sqrt(sum(value * value for value in values))
        if norm:
            values = [value / norm for value in values]
        return tuple(values)


class InMemoryVectorRetriever:
    """Stage-filtered dense path used before a real Qdrant adapter is approved."""

    def __init__(
        self,
        cases: Sequence[HistoricalCase],
        *,
        embedder: Embedder | None = None,
    ) -> None:
        self._cases = tuple(cases)
        self._embedder = embedder or DeterministicFakeEmbedder()
        vectors = self._embedder.embed([case.text for case in self._cases])
        self._vectors = dict(zip((case.case_id for case in self._cases), vectors, strict=True))

    def search(self, query: str, *, stage: str, limit: int = 5) -> RetrievalResult:
        query_vector = self._embedder.embed([query])[0]
        scored: list[RetrievalHit] = []
        snapshots: set[str] = set()
        for case in self._cases:
            if case.stage != stage:
                continue
            snapshots.add(case.corpus_snapshot_id)
            score = sum(
                left * right
                for left, right in zip(
                    query_vector,
                    self._vectors[case.case_id],
                    strict=True,
                )
            )
            if score > 0:
                scored.append(
                    RetrievalHit(
                        case_id=case.case_id,
                        score=round(score, 6),
                        matched_terms=(),
                    )
                )
        scored.sort(key=lambda hit: (-hit.score, hit.case_id))
        return RetrievalResult(
            status="completed",
            stage=stage,
            adapter="in_memory_fake_dense",
            corpus_snapshot_id=",".join(sorted(snapshots)) or None,
            hits=tuple(scored[:limit]),
        )


__all__ = ["DeterministicFakeEmbedder", "Embedder", "InMemoryVectorRetriever"]
