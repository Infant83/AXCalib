"""Smoke-test the embedding/vector port without claiming Qdrant or semantic quality."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from axcalib.retrieval import (  # noqa: E402
    DeterministicFakeEmbedder,
    InMemoryVectorRetriever,
    load_historical_cases,
)


def main() -> int:
    cases = load_historical_cases(ROOT / "fixtures" / "synthetic" / "historical_cases.json")
    embedder = DeterministicFakeEmbedder(dimension=32)
    retriever = InMemoryVectorRetriever(cases, embedder=embedder)
    queries = (
        ("registration", "분자 목표 로드맵 KPI"),
        ("completion", "완료 산출물 KPI 결과 재현 로그"),
    )
    rows = []
    leakage = 0
    for stage, query in queries:
        result = retriever.search(query, stage=stage, limit=5)
        ids = [item.case_id for item in result.hits]
        expected_prefix = (
            "synthetic-reg-" if stage == "registration" else "synthetic-completion-"
        )
        leakage += sum(not item.startswith(expected_prefix) for item in ids)
        rows.append({"stage": stage, "case_ids": ids})
    passed = leakage == 0 and all(row["case_ids"] for row in rows)
    print(
        json.dumps(
            {
                "adapter": "in_memory_fake_dense",
                "embedding_model": embedder.model_id,
                "dimension": embedder.dimension,
                "stage_leakage_count": leakage,
                "rows": rows,
                "passed": passed,
                "quality_claim": (
                    "contract smoke only; no Qdrant, Qwen embedding, rerank, "
                    "or semantic retrieval quality claim"
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
