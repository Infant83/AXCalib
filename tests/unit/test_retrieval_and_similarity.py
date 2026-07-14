from __future__ import annotations

from axcalib.evaluation.similarity import SimilarityPolicy
from axcalib.retrieval import HistoricalCase, LexicalRetriever, NullRetriever


def test_null_retriever_reports_not_configured() -> None:
    result = NullRetriever().search("과제", stage="registration")
    assert result.status == "not_configured"
    assert result.hits == ()


def test_lexical_retriever_never_leaks_completion_into_registration() -> None:
    retriever = LexicalRetriever(
        [
            HistoricalCase("reg-1", "registration", "고객 문의 자동 분류 KPI", "reg-v1"),
            HistoricalCase("comp-1", "completion", "고객 문의 자동 분류 KPI 달성", "comp-v1"),
        ]
    )
    result = retriever.search("고객 문의 KPI", stage="registration")
    assert [hit.case_id for hit in result.hits] == ["reg-1"]


def test_positive_similarity_portion_requires_retrieval_adapter() -> None:
    policy = SimilarityPolicy("disabled", "registration", 0.2)
    assert policy.errors()


def test_high_similarity_portion_is_warning_not_silent() -> None:
    policy = SimilarityPolicy("vector", "completion", 0.4)
    assert policy.errors() == []
    assert policy.warnings()

