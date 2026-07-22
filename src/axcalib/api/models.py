"""HTTP-only request and response models for the runtime API slice."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from axcalib.pipelines import PipelineDescriptor
from axcalib.runtime import PipelineExecutionResult, PipelineJobStatus, PipelineRunStatus
from axcalib.schemas import (
    EducationProgram,
    EnrollmentStatus,
    MilestoneProgress,
    ProgramCompletionDecision,
    ProgramNotificationRecord,
    ReviewerAdjustment,
)
from axcalib.workflows.two_gate import ProjectStatus

PPTX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
LOCAL_REFERENCE_FIELDS = frozenset({"destination", "root", "uri"})


def _redact_local_references(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _redact_local_references(nested)
            for key, nested in value.items()
            if key not in LOCAL_REFERENCE_FIELDS
            and not key.endswith("_path")
            and not key.endswith("_uri")
        }
    if isinstance(value, list):
        return [_redact_local_references(item) for item in value]
    return value


class PipelineCatalogResponse(BaseModel):
    """Deterministic catalog of allowlisted local pipelines."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "axcalib.api-pipeline-catalog/v1alpha1"
    pipelines: tuple[PipelineDescriptor, ...]
    execution_modes: dict[str, Literal["inline", "queued"]] = Field(default_factory=dict)


class PipelineRunRequest(BaseModel):
    """Transport options plus one pipeline-specific JSON payload."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
    )
    idempotency_key: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
    )
    expected_revision: int | None = Field(default=None, ge=1)
    payload: dict[str, Any]


class PipelineRunView(BaseModel):
    """Filesystem-neutral execution result safe for HTTP delivery."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "axcalib.api-pipeline-run/v1alpha1"
    run_id: str
    pipeline_id: str
    pipeline_version: str
    status: PipelineRunStatus
    attempt: int = Field(ge=0)
    output: dict[str, Any] | None = None
    error_code: str | None = None
    replayed: bool = False
    queue_status: PipelineJobStatus | None = None
    updated_at: datetime | None = None

    @classmethod
    def from_execution(
        cls,
        value: PipelineExecutionResult,
        *,
        queue_status: PipelineJobStatus | None = None,
        updated_at: datetime | None = None,
    ) -> PipelineRunView:
        """Remove local checkpoint paths from a transport-neutral result."""

        return cls(
            run_id=value.run_id,
            pipeline_id=value.pipeline_id,
            pipeline_version=value.pipeline_version,
            status=value.status,
            attempt=value.attempt,
            output=_redact_local_references(value.output),
            error_code=value.error_code,
            replayed=value.replayed,
            queue_status=queue_status,
            updated_at=updated_at,
        )


class CancelRunResponse(BaseModel):
    """Acknowledgement of a cooperative cancellation request."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "axcalib.api-cancel/v1alpha1"
    run_id: str
    status: PipelineRunStatus
    cancellation_requested: bool = True


class StagedArtifactRef(BaseModel):
    """Opaque reference to bytes already accepted by a deployment staging service."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    artifact_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    byte_size: int = Field(ge=1)
    media_type: str = Field(min_length=1, max_length=200)


class ProjectRegistrationRequest(BaseModel):
    """Register a staged PPTX without accepting a caller-controlled local path."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    title: str = Field(min_length=1, max_length=300)
    proposal: StagedArtifactRef
    sidecar: StagedArtifactRef | None = None
    review_profile: str | None = Field(
        default=None,
        pattern=r"^[a-z0-9][a-z0-9._-]{2,127}@\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$",
    )
    certification_level: str | None = Field(default=None, min_length=1, max_length=100)


class ProjectArtifactView(BaseModel):
    """Hash metadata safe to return without a deployment-local URI."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    artifact_id: str
    role: str
    media_type: str
    sha256: str
    byte_size: int = Field(ge=0)


class ProjectRegistrationResponse(BaseModel):
    """Filesystem-neutral result of one principal-bound project registration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "axcalib.api-project/v1alpha1"
    project_id: str
    display_id: str
    title: str
    status: ProjectStatus
    revision: int = Field(ge=1)
    proposer_org_id: str
    artifact: ProjectArtifactView
    replayed: bool = False


class ProjectStageView(BaseModel):
    """Review-gate state without report paths, snapshots, rationale, or source text."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    submission_artifact_id: str | None = None
    report_id: str | None = None
    review_profile_selector: str | None = None
    review_profile_sha256: str | None = Field(
        default=None,
        pattern=r"^[a-f0-9]{64}$",
    )
    decision_command: str | None = None
    decision_recorded_at: datetime | None = None


class ProjectExecutionView(BaseModel):
    """Progress summary that deliberately excludes free-form notes and mentor identity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    started_at: datetime | None = None
    completion_submitted_at: datetime | None = None
    mentor_assigned: bool = False
    progress_note_count: int = Field(ge=0)


class ProjectResourceView(BaseModel):
    """Authorized current project state with every deployment-local URI removed."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "axcalib.api-project-resource/v1alpha1"
    project_id: str
    display_id: str
    title: str
    status: ProjectStatus
    revision: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime
    proposer_org_id: str
    certification_level: str | None = None
    artifacts: tuple[ProjectArtifactView, ...] = ()
    registration: ProjectStageView
    execution: ProjectExecutionView
    completion: ProjectStageView
    notification_event_types: tuple[str, ...] = ()


class RegistrationDecisionRequest(BaseModel):
    """Administrator registration command; actor identity comes from auth."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    expected_revision: int = Field(ge=1)
    command: Literal["approve", "reject"]
    rationale: str = Field(min_length=1, max_length=4000)
    adjustments: tuple[ReviewerAdjustment, ...] = ()


class CompletionDecisionRequest(BaseModel):
    """Administrator completion command; actor identity comes from auth."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    expected_revision: int = Field(ge=1)
    command: Literal["accept", "not_accept"]
    rationale: str = Field(min_length=1, max_length=4000)
    adjustments: tuple[ReviewerAdjustment, ...] = ()


class ProjectCommandResponse(BaseModel):
    """Filesystem-neutral domain command result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "axcalib.api-project-command/v1alpha1"
    project_id: str
    status: str
    dossier_status: ProjectStatus
    dossier_revision: int = Field(ge=1)
    report_id: str | None = None
    allowed_commands: tuple[str, ...] = ()
    message: str


class EducationProgramView(BaseModel):
    """Immutable education program without a deployment-local source path."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "axcalib.api-education-program/v1alpha1"
    selector: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    program: EducationProgram


class EducationEnrollmentCreateRequest(BaseModel):
    """Enroll the authenticated learner in one exact program artifact."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    expected_program_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class EducationRevisionRequest(BaseModel):
    """Shared optimistic-concurrency input for enrollment mutations."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    expected_revision: int = Field(ge=1)


class EducationManualConfirmationRequest(EducationRevisionRequest):
    """Record an allowlisted manual requirement using an opaque evidence ID."""

    requirement_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
    evidence_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")


class EducationScoreRequest(EducationManualConfirmationRequest):
    """Record an authorized score against one configured requirement."""

    score: float = Field(ge=0.0, le=100.0)


class EducationProjectBindRequest(EducationRevisionRequest):
    """Bind one existing project dossier to an enrollment milestone."""

    project_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")


class EducationCompletionDecisionRequest(EducationRevisionRequest):
    """Administrator-only final education completion command."""

    command: Literal["approve", "return_for_revision"]
    rationale: str = Field(min_length=1, max_length=4000)
    reopen_milestone_ids: tuple[str, ...] = ()


class EducationCommandResponse(BaseModel):
    """Filesystem-neutral education command result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "axcalib.api-education-command/v1alpha1"
    enrollment_id: str
    enrollment_status: EnrollmentStatus
    enrollment_revision: int = Field(ge=1)
    active_milestone_ids: tuple[str, ...] = ()
    allowed_commands: tuple[str, ...] = ()
    status: Literal["succeeded", "waiting_human", "blocked", "stale"]
    message: str


class EducationEnrollmentView(BaseModel):
    """Authorized enrollment view with local repository paths removed."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "axcalib.api-education-enrollment/v1alpha1"
    enrollment_id: str
    learner_ref: str
    organization_id: str
    program_selector: str
    program_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    revision: int = Field(ge=1)
    status: EnrollmentStatus
    created_at: datetime
    updated_at: datetime
    milestones: tuple[MilestoneProgress, ...]
    notifications: tuple[ProgramNotificationRecord, ...] = ()
    completion_decisions: tuple[ProgramCompletionDecision, ...] = ()


class ValidationIssue(BaseModel):
    """Redacted validation location and code without rejected input values."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    location: str
    code: str


class Problem(BaseModel):
    """RFC 9457-shaped error body with AXCalib-stable machine codes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: str
    title: str
    status: int
    code: str
    detail: str | None = None
    issues: tuple[ValidationIssue, ...] = ()


__all__ = [
    "CancelRunResponse",
    "CompletionDecisionRequest",
    "EducationCommandResponse",
    "EducationCompletionDecisionRequest",
    "EducationEnrollmentCreateRequest",
    "EducationEnrollmentView",
    "EducationManualConfirmationRequest",
    "EducationProgramView",
    "EducationProjectBindRequest",
    "EducationRevisionRequest",
    "EducationScoreRequest",
    "PipelineCatalogResponse",
    "PipelineRunRequest",
    "PipelineRunView",
    "Problem",
    "ProjectArtifactView",
    "ProjectCommandResponse",
    "ProjectExecutionView",
    "ProjectRegistrationRequest",
    "ProjectRegistrationResponse",
    "ProjectResourceView",
    "ProjectStageView",
    "PPTX_MEDIA_TYPE",
    "RegistrationDecisionRequest",
    "StagedArtifactRef",
    "ValidationIssue",
]
