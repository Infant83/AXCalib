"""Provider-neutral evaluator contract shared by offline and model adapters."""

from __future__ import annotations

from typing import Protocol

from axcalib.policies import ResolvedReviewProfile
from axcalib.schemas import EvaluationReport, EvidenceDocument, ProjectDossier, SnapshotRef


class EvidenceEvaluator(Protocol):
    """Evaluate both gates with the exact policy frozen into a dossier."""

    def evaluate_registration(
        self,
        dossier: ProjectDossier,
        snapshot: SnapshotRef,
        evidence: EvidenceDocument,
        profile: ResolvedReviewProfile | None = None,
    ) -> EvaluationReport:
        """Produce a non-binding registration report."""

        ...

    def evaluate_completion(
        self,
        dossier: ProjectDossier,
        snapshot: SnapshotRef,
        evidence: EvidenceDocument,
        registration_report: EvaluationReport,
        profile: ResolvedReviewProfile | None = None,
    ) -> EvaluationReport:
        """Produce a non-binding completion report."""

        ...


__all__ = ["EvidenceEvaluator"]
