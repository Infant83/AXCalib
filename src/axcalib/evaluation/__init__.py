"""Deterministic checks, structured evaluation, and scoring policy."""

from axcalib.evaluation.base import EvidenceEvaluator
from axcalib.evaluation.evidence_quality import (
    EvidenceGoldDataset,
    EvidenceGoldError,
    EvidenceGoldItem,
    EvidenceQualityReport,
    evaluate_evidence_quality,
    load_evidence_gold,
)
from axcalib.evaluation.model import (
    MODEL_EVALUATOR_ID,
    ModelCriterionFinding,
    ModelReviewOutput,
    StructuredModelEvaluator,
    StructuredModelOutputError,
)
from axcalib.evaluation.offline import (
    COMPLETION_CRITERIA,
    EVALUATOR_ID,
    REGISTRATION_CRITERIA,
    OfflineEvidenceEvaluator,
    evidence_sha256,
)
from axcalib.evaluation.similarity import SimilarityPolicy

__all__ = [
    "COMPLETION_CRITERIA",
    "EVALUATOR_ID",
    "EvidenceGoldDataset",
    "EvidenceGoldError",
    "EvidenceGoldItem",
    "EvidenceEvaluator",
    "EvidenceQualityReport",
    "REGISTRATION_CRITERIA",
    "OfflineEvidenceEvaluator",
    "evidence_sha256",
    "evaluate_evidence_quality",
    "load_evidence_gold",
    "SimilarityPolicy",
    "MODEL_EVALUATOR_ID",
    "ModelCriterionFinding",
    "ModelReviewOutput",
    "StructuredModelEvaluator",
    "StructuredModelOutputError",
]
