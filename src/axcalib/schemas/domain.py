"""Typed records shared by the offline AXCalib vertical slice."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from axcalib.workflows.two_gate import ProjectStatus


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""

    return datetime.now(UTC)


class FrozenModel(BaseModel):
    """Strict immutable value object."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ReviewStage(StrEnum):
    """The two evaluation gates."""

    REGISTRATION = "registration"
    COMPLETION = "completion"


class Assessment(StrEnum):
    """One criterion assessment without a final certification decision."""

    MET = "met"
    PARTIALLY_MET = "partially_met"
    NOT_MET = "not_met"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    NOT_APPLICABLE = "not_applicable"


class AgentRecommendation(StrEnum):
    """Non-binding evaluator recommendation."""

    PASS = "pass"
    NEEDS_CHANGES = "needs_changes"
    REJECT = "reject"
    ACCEPT = "accept"
    NOT_ACCEPT = "not_accept"


class PipelineStatus(StrEnum):
    """Statuses that remain distinct from business approval states."""

    SUCCEEDED = "succeeded"
    WAITING_HUMAN = "waiting_human"
    BLOCKED = "blocked"
    STALE = "stale"
    RETRYABLE_FAILURE = "retryable_failure"
    TERMINAL_FAILURE = "terminal_failure"
    CANCELLED = "cancelled"


class ArtifactRef(FrozenModel):
    """Content-addressed artifact reference; bytes are not embedded in a dossier."""

    artifact_id: str
    role: str
    uri: str
    media_type: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    byte_size: int = Field(ge=0)
    metadata: dict[str, str] = Field(default_factory=dict)


class SnapshotRef(FrozenModel):
    """Immutable dossier revision used by one evaluation."""

    snapshot_id: str
    dossier_revision: int = Field(ge=1)
    dossier_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    uri: str


class EvidenceLocator(FrozenModel):
    """Auditable source location with a short allowed excerpt."""

    artifact_id: str
    locator: str
    excerpt: str = Field(max_length=500)
    source: str


class SlideEvidence(FrozenModel):
    """Text and tags available for one PPTX slide."""

    slide_number: int = Field(ge=1)
    text: str
    tags: tuple[str, ...] = ()
    text_source: str
    image_count: int = Field(ge=0)
    is_blank: bool = False


class EvidenceDocument(FrozenModel):
    """Normalized PPTX evidence without model-generated content."""

    artifact: ArtifactRef
    slides: tuple[SlideEvidence, ...]
    warnings: tuple[str, ...] = ()
    parser_id: str = "axcalib.pptx-ooxml/v1"

    @property
    def text(self) -> str:
        """Return slide text in presentation order."""

        return "\n".join(slide.text for slide in self.slides if slide.text)


class CriterionResult(FrozenModel):
    """Evidence-bound assessment for one versioned criterion."""

    criterion_id: str
    title: str
    assessment: Assessment
    observation: str
    evidence_refs: tuple[EvidenceLocator, ...] = ()
    risk_flags: tuple[str, ...] = ()
    follow_up_questions: tuple[str, ...] = ()


class RetrievalSummary(FrozenModel):
    """Explicit retrieval status; similarity never becomes a final decision."""

    status: str
    adapter: str
    similarity_portion: float = Field(ge=0.0, le=0.25)
    corpus_snapshot_id: str | None = None
    case_ids: tuple[str, ...] = ()


class EvaluationReport(FrozenModel):
    """Immutable Agent proposal report for one review gate."""

    schema_version: str = "axcalib.evaluation-report/v1alpha1"
    report_id: str
    run_id: str
    project_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
    stage: ReviewStage
    base_revision: int = Field(ge=1)
    snapshot: SnapshotRef
    rubric_id: str
    rubric_version: str
    evaluator_id: str
    generated_at: datetime = Field(default_factory=utc_now)
    criteria: tuple[CriterionResult, ...]
    recommendation: AgentRecommendation
    recommendation_summary: str
    retrieval: RetrievalSummary
    baseline_report_id: str | None = None
    proposal_artifact_sha256: str | None = None
    evaluated_artifact_sha256: str
    limitations: tuple[str, ...] = ()


class HumanDecision(FrozenModel):
    """Administrator decision stored separately from the Agent report."""

    stage: ReviewStage
    command: str
    actor_id: str
    actor_role: str
    rationale: str = Field(min_length=1, max_length=4000)
    report_id: str
    decided_at: datetime = Field(default_factory=utc_now)
    source: str = "explicit_human_command"


class NotificationRecord(FrozenModel):
    """Recorded administrator approval request."""

    event_type: str
    stage: ReviewStage
    required_role: str
    report_id: str
    dossier_revision: int = Field(ge=1)
    delivery_status: str = "recorded"
    recorded_at: datetime = Field(default_factory=utc_now)


class StageReview(FrozenModel):
    """Dossier section for one gate."""

    submission_artifact_id: str | None = None
    snapshot: SnapshotRef | None = None
    report_id: str | None = None
    report_json_uri: str | None = None
    report_markdown_uri: str | None = None
    decision: HumanDecision | None = None


class ExecutionRecord(FrozenModel):
    """Minimal execution history for the first vertical slice."""

    started_at: datetime | None = None
    completion_submitted_at: datetime | None = None
    mentor_ref: str | None = None
    notes: tuple[str, ...] = ()


class ProjectDossier(FrozenModel):
    """Single mutable project record; evaluation inputs are frozen snapshots."""

    schema_version: str = "axcalib.dossier/v1alpha1"
    project_id: str
    display_id: str
    title: str = Field(min_length=1, max_length=300)
    revision: int = Field(ge=1)
    status: ProjectStatus
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    artifacts: tuple[ArtifactRef, ...] = ()
    registration: StageReview = Field(default_factory=StageReview)
    execution: ExecutionRecord = Field(default_factory=ExecutionRecord)
    completion: StageReview = Field(default_factory=StageReview)
    notifications: tuple[NotificationRecord, ...] = ()
    audit_event_ids: tuple[str, ...] = ()


class AuditEvent(FrozenModel):
    """Small append-only event without raw source content."""

    event_id: str
    project_id: str
    event_type: str
    actor_id: str
    actor_role: str
    dossier_revision: int = Field(ge=1)
    occurred_at: datetime = Field(default_factory=utc_now)
    details: dict[str, Any] = Field(default_factory=dict)


class PipelineResult(FrozenModel):
    """Transport-neutral result returned by local pipelines and clients."""

    pipeline_id: str
    pipeline_version: str
    status: PipelineStatus
    project_id: str
    dossier_status: ProjectStatus
    dossier_revision: int = Field(ge=1)
    dossier_uri: str
    report_id: str | None = None
    report_json_uri: str | None = None
    report_markdown_uri: str | None = None
    allowed_commands: tuple[str, ...] = ()
    message: str


class WorkflowRunSummary(FrozenModel):
    """User-facing summary for a two-gate local run."""

    project_id: str
    final_status: ProjectStatus
    dossier_uri: str
    registration_report_uri: str
    completion_report_uri: str | None = None
    registration_decision: HumanDecision | None = None
    completion_decision: HumanDecision | None = None
    notification_count: int = Field(ge=0)
    audit_uri: str
