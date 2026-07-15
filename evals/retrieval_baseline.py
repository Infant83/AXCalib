"""Measure the synthetic stage-aware lexical retrieval reference baseline."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from axcalib.retrieval import LexicalRetriever, load_historical_cases  # noqa: E402


def _ndcg_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    dcg = sum(
        1.0 / math.log2(index + 2)
        for index, case_id in enumerate(ranked[:k])
        if case_id in relevant
    )
    ideal_count = min(len(relevant), k)
    ideal = sum(1.0 / math.log2(index + 2) for index in range(ideal_count))
    return dcg / ideal if ideal else 1.0


def main() -> int:
    """Print metric evidence without claiming vector or semantic retrieval quality."""

    corpus = load_historical_cases(ROOT / "fixtures" / "synthetic" / "historical_cases.json")
    dataset = json.loads(
        (ROOT / "evals" / "datasets" / "retrieval_queries.json").read_text(
            encoding="utf-8"
        )
    )
    retriever = LexicalRetriever(corpus)
    case_stages = {case.case_id: case.stage for case in corpus}
    recalls: list[float] = []
    ndcgs: list[float] = []
    leakage = 0
    rows = []
    for query in dataset["queries"]:
        result = retriever.search(query["text"], stage=query["stage"], limit=5)
        ranked = [hit.case_id for hit in result.hits]
        relevant = set(query["relevant_case_ids"])
        found = len(relevant.intersection(ranked))
        recall = found / len(relevant) if relevant else 1.0
        ndcg = _ndcg_at_k(ranked, relevant, 5)
        wrong_stage = [
            case_id
            for case_id in ranked
            if case_stages.get(case_id) != query["stage"]
        ]
        leakage += len(wrong_stage)
        recalls.append(recall)
        ndcgs.append(ndcg)
        rows.append(
            {
                "query_id": query["query_id"],
                "top_case_id": ranked[0] if ranked else None,
                "recall_at_5": round(recall, 4),
                "ndcg_at_5": round(ndcg, 4),
            }
        )
    recall_at_5 = sum(recalls) / len(recalls)
    ndcg_at_5 = sum(ndcgs) / len(ndcgs)
    passed = recall_at_5 >= 0.8 and leakage == 0
    print(
        json.dumps(
            {
                "dataset": "evals/datasets/retrieval_queries.json",
                "adapter": "lexical",
                "query_count": len(rows),
                "recall_at_5": round(recall_at_5, 4),
                "ndcg_at_5": round(ndcg_at_5, 4),
                "stage_leakage_count": leakage,
                "rows": rows,
                "passed": passed,
                "quality_claim": (
                    "synthetic lexical reference baseline only; no embedding, rerank, "
                    "Qdrant, or production retrieval claim"
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
