"""Allowlisted command pipeline for education enrollment progression."""

from __future__ import annotations

import asyncio
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from axcalib.pipelines.base import PipelineContext
from axcalib.programs import EducationProgramService
from axcalib.schemas import EducationPipelineResult

PIPELINE_ID = "education-program-runtime"
PIPELINE_VERSION = "v1alpha1"
IDEMPOTENCY_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"


class EducationCommandBase(BaseModel):
    """Strict base for future JSON/OpenAPI command adapters."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    idempotency_key: str | None = Field(default=None, pattern=IDEMPOTENCY_PATTERN)
    authority_context: str = "offline_unverified_actor"


class EnrollCommand(EducationCommandBase):
    action: Literal["enroll"] = "enroll"
    program_selector: str
    learner_ref: str
    enrollment_id: str | None = None
    organization_id: str | None = None
    actor_id: str | None = None


class StartMilestoneCommand(EducationCommandBase):
    action: Literal["start_milestone"] = "start_milestone"
    enrollment_id: str
    milestone_id: str
    actor_id: str
    expected_revision: int | None = Field(default=None, ge=1)


class ManualConfirmationCommand(EducationCommandBase):
    action: Literal["record_manual_confirmation"] = "record_manual_confirmation"
    enrollment_id: str
    milestone_id: str
    requirement_id: str
    actor_id: str
    actor_role: Literal["instructor", "mentor", "administrator"]
    evidence_ref: str
    expected_revision: int | None = Field(default=None, ge=1)


class RecordScoreCommand(EducationCommandBase):
    action: Literal["record_score"] = "record_score"
    enrollment_id: str
    milestone_id: str
    requirement_id: str
    score: float = Field(ge=0.0, le=100.0)
    actor_id: str
    actor_role: Literal["instructor", "mentor", "administrator"]
    evidence_ref: str
    expected_revision: int | None = Field(default=None, ge=1)


class BindProjectCommand(EducationCommandBase):
    action: Literal["bind_project"] = "bind_project"
    enrollment_id: str
    milestone_id: str
    project_id: str
    actor_id: str
    organization_id: str | None = None
    expected_revision: int | None = Field(default=None, ge=1)


class SyncProjectCommand(EducationCommandBase):
    action: Literal["sync_project"] = "sync_project"
    enrollment_id: str
    milestone_id: str
    actor_id: str = "system:education-runtime"
    actor_role: Literal["learner", "mentor", "instructor", "administrator", "system"] = "system"
    organization_id: str | None = None
    expected_revision: int | None = Field(default=None, ge=1)


class DecideProgramCompletionCommand(EducationCommandBase):
    action: Literal["decide_program_completion"] = "decide_program_completion"
    enrollment_id: str
    command: Literal["approve", "return_for_revision"]
    actor_id: str
    actor_role: Literal["administrator"]
    rationale: str
    reopen_milestone_ids: tuple[str, ...] = ()
    expected_revision: int | None = Field(default=None, ge=1)


EducationCommand = Annotated[
    EnrollCommand
    | StartMilestoneCommand
    | ManualConfirmationCommand
    | RecordScoreCommand
    | BindProjectCommand
    | SyncProjectCommand
    | DecideProgramCompletionCommand,
    Field(discriminator="action"),
]


class EducationProgramPipeline:
    """Dispatch only explicitly declared education commands."""

    pipeline_id = PIPELINE_ID
    pipeline_version = PIPELINE_VERSION

    def __init__(self, service: EducationProgramService) -> None:
        self.service = service

    def run(
        self,
        request: EducationCommand,
        *,
        context: PipelineContext | None = None,
    ) -> EducationPipelineResult:
        if context is not None and context.cancellation_requested():
            raise TimeoutError("pipeline execution was cancelled before start")
        if isinstance(request, EnrollCommand):
            return self.service.enroll(
                request.program_selector,
                learner_ref=request.learner_ref,
                enrollment_id=request.enrollment_id,
                organization_id=request.organization_id,
                actor_id=request.actor_id,
                authority_context=request.authority_context,
            )
        if isinstance(request, StartMilestoneCommand):
            return self.service.start_milestone(
                request.enrollment_id,
                request.milestone_id,
                actor_id=request.actor_id,
                expected_revision=request.expected_revision,
                authority_context=request.authority_context,
            )
        if isinstance(request, ManualConfirmationCommand):
            return self.service.record_manual_confirmation(
                request.enrollment_id,
                request.milestone_id,
                request.requirement_id,
                actor_id=request.actor_id,
                actor_role=request.actor_role,
                evidence_ref=request.evidence_ref,
                expected_revision=request.expected_revision,
                authority_context=request.authority_context,
            )
        if isinstance(request, RecordScoreCommand):
            return self.service.record_score(
                request.enrollment_id,
                request.milestone_id,
                request.requirement_id,
                score=request.score,
                actor_id=request.actor_id,
                actor_role=request.actor_role,
                evidence_ref=request.evidence_ref,
                expected_revision=request.expected_revision,
                authority_context=request.authority_context,
            )
        if isinstance(request, BindProjectCommand):
            return self.service.bind_project(
                request.enrollment_id,
                request.milestone_id,
                project_id=request.project_id,
                actor_id=request.actor_id,
                organization_id=request.organization_id,
                expected_revision=request.expected_revision,
                authority_context=request.authority_context,
            )
        if isinstance(request, SyncProjectCommand):
            return self.service.sync_project_milestone(
                request.enrollment_id,
                request.milestone_id,
                actor_id=request.actor_id,
                actor_role=request.actor_role,
                organization_id=request.organization_id,
                expected_revision=request.expected_revision,
                authority_context=request.authority_context,
            )
        if isinstance(request, DecideProgramCompletionCommand):
            return self.service.decide_program_completion(
                request.enrollment_id,
                command=request.command,
                actor_id=request.actor_id,
                rationale=request.rationale,
                reopen_milestone_ids=request.reopen_milestone_ids,
                expected_revision=request.expected_revision,
                authority_context=request.authority_context,
            )
        raise TypeError(f"unsupported education command: {type(request).__name__}")

    async def arun(
        self,
        request: EducationCommand,
        *,
        context: PipelineContext | None = None,
    ) -> EducationPipelineResult:
        return await asyncio.to_thread(self.run, request, context=context)


__all__ = [
    "BindProjectCommand",
    "DecideProgramCompletionCommand",
    "EducationCommand",
    "EducationProgramPipeline",
    "EnrollCommand",
    "ManualConfirmationCommand",
    "RecordScoreCommand",
    "StartMilestoneCommand",
    "SyncProjectCommand",
]
