"""Read-only project case views derived from the latest dossier revision."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field

from axcalib.schemas.domain import (
    AgentRecommendation,
    Assessment,
    FrozenModel,
    ReviewContext,
    ReviewStage,
)
from axcalib.workflows.two_gate import ProjectStatus


class CaseLifecycleStage(StrEnum):
    """Human-facing lifecycle section containing the current project status."""

    REGISTRATION = "registration"
    EXECUTION = "execution"
    COMPLETION = "completion"


class CaseNextAction(FrozenModel):
    """One domain-valid next action without claiming caller authorization."""

    action_id: str
    required_role: str
    description: str


class AssessmentCount(FrozenModel):
    """Count for one criterion assessment category."""

    assessment: Assessment
    count: int = Field(ge=0)


class CaseEvidenceView(FrozenModel):
    """Evidence locator with storage paths removed from the read projection."""

    artifact_id: str
    locator: str
    excerpt: str
    source: str


class CriterionReviewView(FrozenModel):
    """Agent assessment and any explicit human correction for one criterion."""

    criterion_id: str
    title: str
    agent_assessment: Assessment
    effective_assessment: Assessment
    human_adjusted: bool = False
    observation: str | None = None
    evidence_refs: tuple[CaseEvidenceView, ...] = ()
    adjustment_reason: str | None = None


class HumanDecisionView(FrozenModel):
    """Human decision kept visibly separate from the Agent recommendation."""

    command: str
    decided_at: datetime
    adjustment_count: int
    actor_id: str | None = None
    rationale: str | None = None
    authority_context: str | None = None


class GateReviewView(FrozenModel):
    """Current read projection for one registration or completion review gate."""

    stage: ReviewStage
    report_id: str | None = None
    report_base_revision: int | None = None
    snapshot_id: str | None = None
    agent_recommendation: AgentRecommendation | None = None
    agent_summary: str | None = None
    human_decision: HumanDecisionView | None = None
    agent_assessments: tuple[AssessmentCount, ...] = ()
    effective_assessments: tuple[AssessmentCount, ...] = ()
    adjusted_criterion_count: int = 0
    criteria: tuple[CriterionReviewView, ...] = ()


class CaseStatus(FrozenModel):
    """Small operational answer to "where is this case now?"."""

    schema_version: Literal["axcalib.case-status/v1alpha1"] = "axcalib.case-status/v1alpha1"
    project_id: str
    display_id: str
    title: str
    revision: int
    dossier_status: ProjectStatus
    lifecycle_stage: CaseLifecycleStage
    terminal: bool
    waiting_for: str | None = None
    next_actions: tuple[CaseNextAction, ...] = ()
    latest_review: GateReviewView | None = None
    updated_at: datetime


class ExecutionSummary(FrozenModel):
    """Safe-by-default execution digest; note text is verbose-only."""

    started_at: datetime | None = None
    completion_submitted_at: datetime | None = None
    mentor_assigned: bool = False
    progress_note_count: int = 0
    progress_notes: tuple[str, ...] = ()


class CaseArtifactView(FrozenModel):
    """Artifact metadata without a local or remote storage URI."""

    artifact_id: str
    role: str
    media_type: str
    sha256: str
    byte_size: int


class CaseNotificationView(FrozenModel):
    """Approval-request delivery fact without notification payload content."""

    stage: ReviewStage
    event_type: str
    required_role: str
    report_id: str
    dossier_revision: int
    delivery_status: str
    recorded_at: datetime


class CaseSummary(FrozenModel):
    """Lifecycle digest joining both immutable reports with human decisions."""

    schema_version: Literal["axcalib.case-summary/v1alpha1"] = "axcalib.case-summary/v1alpha1"
    project_id: str
    display_id: str
    title: str
    revision: int
    dossier_status: ProjectStatus
    lifecycle_stage: CaseLifecycleStage
    terminal: bool
    review_profile: str | None = None
    review_profile_sha256: str | None = None
    review_context: ReviewContext
    registration: GateReviewView
    execution: ExecutionSummary
    completion: GateReviewView
    artifact_count: int
    artifacts: tuple[CaseArtifactView, ...] = ()
    notification_count: int
    notifications: tuple[CaseNotificationView, ...] = ()
    audit_event_count: int
    audit_event_ids: tuple[str, ...] = ()
    updated_at: datetime


__all__ = [
    "AssessmentCount",
    "CaseArtifactView",
    "CaseEvidenceView",
    "CaseLifecycleStage",
    "CaseNextAction",
    "CaseNotificationView",
    "CaseStatus",
    "CaseSummary",
    "CriterionReviewView",
    "ExecutionSummary",
    "GateReviewView",
    "HumanDecisionView",
]
