"""Typed education-program and enrollment contracts built above project dossiers."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import Field, model_validator

from axcalib.schemas.domain import FrozenModel, utc_now

IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"
SEMVER_PATTERN = r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$"


class ProgramStatus(StrEnum):
    """Lifecycle of a program definition, not a learner certification decision."""

    DRAFT = "draft"
    OFFLINE_REFERENCE = "offline_reference"
    PUBLISHED = "published"
    RETIRED = "retired"


class MilestoneKind(StrEnum):
    """Allowlisted milestone capabilities available to a course designer."""

    LEARNING_ACTIVITY = "learning_activity"
    PROJECT_CERTIFICATION = "project_certification"
    ASSESSMENT = "assessment"


class MilestoneProgressStatus(StrEnum):
    """Runtime status of one generated learner goal."""

    LOCKED = "locked"
    AVAILABLE = "available"
    IN_PROGRESS = "in_progress"
    WAITING_REVIEW = "waiting_review"
    NEEDS_ACTION = "needs_action"
    COMPLETED = "completed"


class EnrollmentStatus(StrEnum):
    """Program progression state with a mandatory human completion gate."""

    ACTIVE = "active"
    COMPLETION_HITL_PENDING = "completion_hitl_pending"
    COMPLETED = "completed"
    RETURNED_FOR_REVISION = "returned_for_revision"
    WITHDRAWN = "withdrawn"


class ManualConfirmationRequirement(FrozenModel):
    """An instructor, mentor, or administrator confirms an activity."""

    kind: Literal["manual_confirmation"] = "manual_confirmation"
    requirement_id: str = Field(pattern=IDENTIFIER_PATTERN)
    title: str = Field(min_length=1, max_length=300)
    required_role: Literal["instructor", "mentor", "administrator"] = "instructor"
    points: float = Field(default=1.0, gt=0.0, le=1000.0)


class ScoreRequirement(FrozenModel):
    """A trusted evaluator records a score against an explicit threshold."""

    kind: Literal["score_at_least"] = "score_at_least"
    requirement_id: str = Field(pattern=IDENTIFIER_PATTERN)
    title: str = Field(min_length=1, max_length=300)
    passing_score: float = Field(ge=0.0, le=100.0)
    required_role: Literal["instructor", "mentor", "administrator"] = "instructor"
    points: float = Field(default=1.0, gt=0.0, le=1000.0)


class ProjectStatusRequirement(FrozenModel):
    """A milestone condition derived from an actual AXCalib project dossier."""

    kind: Literal["project_status"] = "project_status"
    requirement_id: str = Field(pattern=IDENTIFIER_PATTERN)
    title: str = Field(min_length=1, max_length=300)
    required_status: Literal["registration_approved", "completion_accepted"] = (
        "completion_accepted"
    )
    points: float = Field(default=1.0, gt=0.0, le=1000.0)


RequirementSpec = Annotated[
    ManualConfirmationRequirement | ScoreRequirement | ProjectStatusRequirement,
    Field(discriminator="kind"),
]


class MilestoneCompletionRule(FrozenModel):
    """Small allowlisted rule; arbitrary expressions are intentionally unsupported."""

    mode: Literal["all_required", "minimum_points"] = "all_required"
    minimum_points: float | None = Field(default=None, gt=0.0, le=10000.0)

    @model_validator(mode="after")
    def validate_threshold(self) -> MilestoneCompletionRule:
        if self.mode == "minimum_points" and self.minimum_points is None:
            raise ValueError("minimum_points is required for minimum_points mode")
        if self.mode == "all_required" and self.minimum_points is not None:
            raise ValueError("minimum_points is not used by all_required mode")
        return self


class MilestoneSpec(FrozenModel):
    """One versioned, composable learner milestone."""

    milestone_id: str = Field(pattern=IDENTIFIER_PATTERN)
    title: str = Field(min_length=1, max_length=300)
    sequence: int = Field(ge=1)
    kind: MilestoneKind
    prerequisites: tuple[str, ...] = ()
    pipeline_id: str = Field(pattern=r"^[a-z][a-z0-9._-]{2,127}$")
    pipeline_version: str = Field(pattern=r"^v[0-9A-Za-z._-]+$")
    requirements: tuple[RequirementSpec, ...] = Field(min_length=1)
    completion_rule: MilestoneCompletionRule = Field(
        default_factory=MilestoneCompletionRule
    )
    required_for_program_completion: bool = True

    @model_validator(mode="after")
    def validate_requirements(self) -> MilestoneSpec:
        ids = [item.requirement_id for item in self.requirements]
        if len(ids) != len(set(ids)):
            raise ValueError("milestone requirement IDs must be unique")
        project_requirements = [
            item for item in self.requirements if isinstance(item, ProjectStatusRequirement)
        ]
        if self.kind is MilestoneKind.PROJECT_CERTIFICATION and len(project_requirements) != 1:
            raise ValueError(
                "project_certification requires exactly one project_status requirement"
            )
        available_points = sum(item.points for item in self.requirements)
        if (
            self.completion_rule.mode == "minimum_points"
            and (self.completion_rule.minimum_points or 0.0) > available_points
        ):
            raise ValueError("minimum_points exceeds the milestone's available points")
        return self


class ProgramLevelSpec(FrozenModel):
    """Ordered group of milestones representing one course level."""

    level_id: str = Field(pattern=IDENTIFIER_PATTERN)
    title: str = Field(min_length=1, max_length=300)
    sequence: int = Field(ge=1)
    milestones: tuple[MilestoneSpec, ...] = Field(min_length=1)


class EducationProgram(FrozenModel):
    """Immutable program blueprint selected when a learner enrolls."""

    schema_version: Literal["axcalib.education-program/v1alpha1"] = (
        "axcalib.education-program/v1alpha1"
    )
    program_id: str = Field(pattern=IDENTIFIER_PATTERN)
    version: str = Field(pattern=SEMVER_PATTERN)
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(min_length=1, max_length=4000)
    status: ProgramStatus = ProgramStatus.DRAFT
    owner_ref: str = Field(min_length=1, max_length=300)
    levels: tuple[ProgramLevelSpec, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_graph(self) -> EducationProgram:
        level_ids = [level.level_id for level in self.levels]
        level_sequences = [level.sequence for level in self.levels]
        if len(level_ids) != len(set(level_ids)):
            raise ValueError("program level IDs must be unique")
        if len(level_sequences) != len(set(level_sequences)):
            raise ValueError("program level sequences must be unique")

        positions: dict[str, tuple[int, int]] = {}
        for level in self.levels:
            milestone_sequences = [item.sequence for item in level.milestones]
            if len(milestone_sequences) != len(set(milestone_sequences)):
                raise ValueError("milestone sequences must be unique within a level")
            for milestone in level.milestones:
                if milestone.milestone_id in positions:
                    raise ValueError("milestone IDs must be unique across a program")
                positions[milestone.milestone_id] = (level.sequence, milestone.sequence)

        for level in self.levels:
            for milestone in level.milestones:
                current = positions[milestone.milestone_id]
                for prerequisite in milestone.prerequisites:
                    prior = positions.get(prerequisite)
                    if prior is None:
                        raise ValueError(f"unknown milestone prerequisite: {prerequisite}")
                    if prior >= current:
                        raise ValueError("a prerequisite must precede its dependent milestone")
        return self

    def milestones(self) -> tuple[tuple[str, MilestoneSpec], ...]:
        """Return level/milestone pairs in deterministic execution order."""

        pairs = [
            (level.level_id, milestone)
            for level in sorted(self.levels, key=lambda item: item.sequence)
            for milestone in sorted(level.milestones, key=lambda item: item.sequence)
        ]
        return tuple(pairs)


class ProgramRef(FrozenModel):
    """Hash-bound program version used by one enrollment."""

    program_id: str = Field(pattern=IDENTIFIER_PATTERN)
    version: str = Field(pattern=SEMVER_PATTERN)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_uri: str

    @property
    def selector(self) -> str:
        return f"{self.program_id}@{self.version}"


class RequirementResult(FrozenModel):
    """Auditable observation for one configured requirement."""

    requirement_id: str = Field(pattern=IDENTIFIER_PATTERN)
    satisfied: bool
    points_awarded: float = Field(ge=0.0, le=1000.0)
    source: Literal["manual_confirmation", "score", "project_dossier"]
    actor_id: str
    actor_role: str
    evidence_ref: str
    observed_value: str
    recorded_at: datetime = Field(default_factory=utc_now)


class MilestoneProgress(FrozenModel):
    """Generated learner goal and its current evidence state."""

    milestone_id: str = Field(pattern=IDENTIFIER_PATTERN)
    level_id: str = Field(pattern=IDENTIFIER_PATTERN)
    goal_title: str = Field(min_length=1, max_length=300)
    pipeline_id: str
    pipeline_version: str
    status: MilestoneProgressStatus
    bound_project_id: str | None = None
    requirement_results: tuple[RequirementResult, ...] = ()
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @model_validator(mode="after")
    def validate_progress_integrity(self) -> MilestoneProgress:
        requirement_ids = [item.requirement_id for item in self.requirement_results]
        if len(requirement_ids) != len(set(requirement_ids)):
            raise ValueError("milestone requirement results must be unique")
        if self.status is MilestoneProgressStatus.COMPLETED and self.completed_at is None:
            raise ValueError("a completed milestone requires completed_at")
        if self.status is not MilestoneProgressStatus.COMPLETED and self.completed_at is not None:
            raise ValueError("only a completed milestone may have completed_at")
        return self


class ProgramNotificationRecord(FrozenModel):
    """Administrator completion request retained on the enrollment."""

    event_type: str = "education_program_completion_approval_requested"
    required_role: str = "administrator"
    enrollment_revision: int = Field(ge=1)
    delivery_status: Literal["recorded"] = "recorded"
    recorded_at: datetime = Field(default_factory=utc_now)


class ProgramCompletionDecision(FrozenModel):
    """Explicit administrator decision, separate from condition evaluation."""

    command: Literal["approve", "return_for_revision"]
    actor_id: str
    actor_role: Literal["administrator"] = "administrator"
    rationale: str = Field(min_length=1, max_length=4000)
    decided_at: datetime = Field(default_factory=utc_now)
    source: str = "explicit_command_input"
    authority_context: str = "offline_unverified_actor"


class ProgramAuditEvent(FrozenModel):
    """Small append-only event for enrollment progression."""

    event_id: str
    enrollment_id: str = Field(pattern=IDENTIFIER_PATTERN)
    event_type: str
    actor_id: str
    actor_role: str
    enrollment_revision: int = Field(ge=1)
    occurred_at: datetime = Field(default_factory=utc_now)
    details: dict[str, Any] = Field(default_factory=dict)


class EducationEnrollment(FrozenModel):
    """Mutable learner progress record pinned to one immutable program version."""

    schema_version: Literal["axcalib.education-enrollment/v1alpha1"] = (
        "axcalib.education-enrollment/v1alpha1"
    )
    enrollment_id: str = Field(pattern=IDENTIFIER_PATTERN)
    learner_ref: str = Field(min_length=1, max_length=300)
    program: ProgramRef
    revision: int = Field(ge=1)
    status: EnrollmentStatus = EnrollmentStatus.ACTIVE
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    milestones: tuple[MilestoneProgress, ...]
    notifications: tuple[ProgramNotificationRecord, ...] = ()
    completion_decisions: tuple[ProgramCompletionDecision, ...] = ()
    audit_event_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_enrollment_integrity(self) -> EducationEnrollment:
        milestone_ids = [item.milestone_id for item in self.milestones]
        if len(milestone_ids) != len(set(milestone_ids)):
            raise ValueError("enrollment milestone IDs must be unique")
        if self.status is EnrollmentStatus.COMPLETION_HITL_PENDING and not self.notifications:
            raise ValueError("program completion HITL requires a notification record")
        if self.status is EnrollmentStatus.COMPLETED:
            if not self.completion_decisions:
                raise ValueError("completed enrollment requires an administrator decision")
            if self.completion_decisions[-1].command != "approve":
                raise ValueError("completed enrollment requires a final approve decision")
        if self.status is EnrollmentStatus.RETURNED_FOR_REVISION:
            if not self.completion_decisions:
                raise ValueError("returned enrollment requires an administrator decision")
            if self.completion_decisions[-1].command != "return_for_revision":
                raise ValueError("returned enrollment requires a return decision")
        return self


class EducationPipelineResult(FrozenModel):
    """Transport-neutral result for future CLI/API/Web adapters."""

    pipeline_id: str
    pipeline_version: str
    status: Literal["succeeded", "waiting_human", "blocked", "stale"]
    enrollment_id: str
    enrollment_status: EnrollmentStatus
    enrollment_revision: int = Field(ge=1)
    enrollment_uri: str
    active_milestone_ids: tuple[str, ...] = ()
    allowed_commands: tuple[str, ...] = ()
    message: str


__all__ = [
    "EducationEnrollment",
    "EducationPipelineResult",
    "EducationProgram",
    "EnrollmentStatus",
    "ManualConfirmationRequirement",
    "MilestoneCompletionRule",
    "MilestoneKind",
    "MilestoneProgress",
    "MilestoneProgressStatus",
    "MilestoneSpec",
    "ProgramCompletionDecision",
    "ProgramAuditEvent",
    "ProgramLevelSpec",
    "ProgramNotificationRecord",
    "ProgramRef",
    "ProgramStatus",
    "ProjectStatusRequirement",
    "RequirementResult",
    "RequirementSpec",
    "ScoreRequirement",
]
