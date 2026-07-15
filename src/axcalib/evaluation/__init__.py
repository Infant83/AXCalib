"""Deterministic checks, structured evaluation, and scoring policy."""

from axcalib.evaluation.offline import (
    COMPLETION_CRITERIA,
    EVALUATOR_ID,
    REGISTRATION_CRITERIA,
    OfflineEvidenceEvaluator,
)
from axcalib.evaluation.similarity import SimilarityPolicy

__all__ = [
    "COMPLETION_CRITERIA",
    "EVALUATOR_ID",
    "REGISTRATION_CRITERIA",
    "OfflineEvidenceEvaluator",
    "SimilarityPolicy",
]
