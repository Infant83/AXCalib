"""Offline retrieval contracts that do not require an embedding model."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class HistoricalCase:
    """A synthetic or approved historical case available for retrieval."""

    case_id: str
    stage: str
    text: str
    corpus_snapshot_id: str


@dataclass(frozen=True, slots=True)
class RetrievalHit:
    """One stage-filtered retrieval hit."""

    case_id: str
    score: float
    matched_terms: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    """Retrieval result with an explicit availability status."""

    status: str
    stage: str
    adapter: str
    corpus_snapshot_id: str | None
    hits: tuple[RetrievalHit, ...]


class CaseRetriever(Protocol):
    """Provider-independent historical case retrieval interface."""

    def search(self, query: str, *, stage: str, limit: int = 5) -> RetrievalResult:
        """Return cases for one review stage."""

        ...


class NullRetriever:
    """Make an unavailable corpus explicit instead of inventing matches."""

    def search(self, query: str, *, stage: str, limit: int = 5) -> RetrievalResult:
        del query, limit
        return RetrievalResult("not_configured", stage, "null", None, ())


class LexicalRetriever:
    """Deterministic token-overlap baseline for synthetic/offline evaluation."""

    def __init__(self, cases: Sequence[HistoricalCase]) -> None:
        self._cases = tuple(cases)

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return set(re.findall(r"[0-9a-zA-Z가-힣_]+", text.casefold()))

    def search(self, query: str, *, stage: str, limit: int = 5) -> RetrievalResult:
        query_tokens = self._tokens(query)
        scored: list[RetrievalHit] = []
        snapshots: set[str] = set()
        for case in self._cases:
            if case.stage != stage:
                continue
            snapshots.add(case.corpus_snapshot_id)
            case_tokens = self._tokens(case.text)
            union = query_tokens | case_tokens
            score = len(query_tokens & case_tokens) / len(union) if union else 0.0
            if score > 0:
                scored.append(
                    RetrievalHit(
                        case_id=case.case_id,
                        score=round(score, 6),
                        matched_terms=tuple(sorted(query_tokens & case_tokens)),
                    )
                )
        scored.sort(key=lambda hit: (-hit.score, hit.case_id))
        snapshot = ",".join(sorted(snapshots)) or None
        return RetrievalResult("completed", stage, "lexical", snapshot, tuple(scored[:limit]))


def load_historical_cases(path: Path) -> tuple[HistoricalCase, ...]:
    """Load a small versioned synthetic/approved lexical corpus."""

    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != "axcalib.historical-cases/v1alpha1":
        raise ValueError("unsupported historical-case corpus schema_version")
    cases = data.get("cases")
    if not isinstance(cases, list):
        raise ValueError("historical-case corpus cases must be an array")
    result: list[HistoricalCase] = []
    for item in cases:
        if not isinstance(item, dict):
            raise ValueError("historical-case entries must be objects")
        case = HistoricalCase(
            case_id=str(item["case_id"]),
            stage=str(item["stage"]),
            text=str(item["text"]),
            corpus_snapshot_id=str(item["corpus_snapshot_id"]),
        )
        if case.stage not in {"registration", "completion"}:
            raise ValueError(f"invalid historical-case stage: {case.stage}")
        result.append(case)
    return tuple(result)
