from pathlib import Path

from axcalib.retrieval import (
    DeterministicFakeEmbedder,
    InMemoryVectorRetriever,
    load_historical_cases,
)

ROOT = Path(__file__).resolve().parents[2]


def test_fake_embedding_is_deterministic_and_stage_filtered() -> None:
    cases = load_historical_cases(ROOT / "fixtures" / "synthetic" / "historical_cases.json")
    embedder = DeterministicFakeEmbedder(dimension=32)
    assert embedder.embed(["분자 KPI"])[0] == embedder.embed(["분자 KPI"])[0]
    retriever = InMemoryVectorRetriever(cases, embedder=embedder)

    registration = retriever.search("분자 목표 방법 KPI", stage="registration")
    completion = retriever.search("산출물 결과 재현 로그", stage="completion")

    assert registration.adapter == "in_memory_fake_dense"
    assert registration.hits
    assert completion.hits
    assert all(hit.case_id.startswith("synthetic-reg-") for hit in registration.hits)
    assert all(
        hit.case_id.startswith("synthetic-completion-") for hit in completion.hits
    )
