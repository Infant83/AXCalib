"""Application service for versioned education programs and rolling enrollments."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from axcalib.audit import AuditLog
from axcalib.dossier import DossierRepository
from axcalib.notifications.base import NotificationEvent, NotificationPort
from axcalib.notifications.outbox import DurableNotificationOutbox
from axcalib.programs.repository import EnrollmentRepository, ProgramRepository
from axcalib.runtime.enrollment_transactions import EnrollmentTransactionCoordinator
from axcalib.schemas import (
    EducationEnrollment,
    EducationPipelineResult,
    EducationProgram,
    EnrollmentStatus,
    ManualConfirmationRequirement,
    MilestoneProgress,
    MilestoneProgressStatus,
    MilestoneSpec,
    ProgramAuditEvent,
    ProgramCompletionDecision,
    ProgramNotificationRecord,
    ProgramRef,
    ProgramStatus,
    ProjectDossier,
    ProjectStatusRequirement,
    RequirementResult,
    ScoreRequirement,
)
from axcalib.workflows.two_gate import ProjectStatus

PIPELINE_ID = "education-program-runtime"
PIPELINE_VERSION = "v1alpha1"
ALLOWED_MILESTONE_PIPELINES = frozenset(
    {
        ("education.manual-confirmation", "v1alpha1"),
        ("education.score-assessment", "v1alpha1"),
        ("two-gate-pptx", "v1alpha1"),
    }
)


class EducationProgramError(ValueError):
    """Raised when progression would violate the selected program contract."""


class EducationProgramService:
    """Manage program definitions and learner progress above project dossiers."""

    def __init__(
        self,
        workspace: Path,
        *,
        dossiers: DossierRepository,
        notifier: NotificationPort,
    ) -> None:
        self.workspace = workspace.resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.programs = ProgramRepository(self.workspace / "programs")
        self.enrollments = EnrollmentRepository(self.workspace / "enrollments")
        self.dossiers = dossiers
        self.notifier = notifier
        self.audit = AuditLog(self.workspace / "audit" / "education-events.jsonl")
        self.transactions = EnrollmentTransactionCoordinator(
            self.workspace,
            enrollments=self.enrollments,
            audit=self.audit,
        )

    def publish_program(self, program: EducationProgram) -> ProgramRef:
        """Publish one immutable reference or idempotently return the same version."""

        if program.status not in {ProgramStatus.OFFLINE_REFERENCE, ProgramStatus.PUBLISHED}:
            raise EducationProgramError(
                "only offline_reference or published programs may accept enrollments"
            )
        unsupported = {
            (milestone.pipeline_id, milestone.pipeline_version)
            for _, milestone in program.milestones()
            if (milestone.pipeline_id, milestone.pipeline_version)
            not in ALLOWED_MILESTONE_PIPELINES
        }
        if unsupported:
            raise EducationProgramError(
                f"program contains non-allowlisted pipelines: {sorted(unsupported)}"
            )
        return self.programs.publish(program)

    def enroll(
        self,
        program_selector: str,
        *,
        learner_ref: str,
        enrollment_id: str | None = None,
        organization_id: str | None = None,
        actor_id: str | None = None,
        authority_context: str = "offline_unverified_actor",
    ) -> EducationPipelineResult:
        """Pin a learner to one program version and generate milestone goals."""

        program, reference = self.programs.resolve(program_selector)
        if program.status not in {ProgramStatus.OFFLINE_REFERENCE, ProgramStatus.PUBLISHED}:
            raise EducationProgramError("the selected program is not open for enrollment")
        identifier = enrollment_id or str(uuid.uuid4())
        event_id = self._event_id()
        progress = tuple(
            MilestoneProgress(
                milestone_id=milestone.milestone_id,
                level_id=level_id,
                goal_title=milestone.title,
                pipeline_id=milestone.pipeline_id,
                pipeline_version=milestone.pipeline_version,
                status=(
                    MilestoneProgressStatus.LOCKED
                    if milestone.prerequisites
                    else MilestoneProgressStatus.AVAILABLE
                ),
            )
            for level_id, milestone in program.milestones()
        )
        enrollment = EducationEnrollment(
            enrollment_id=identifier,
            learner_ref=learner_ref,
            program=reference,
            revision=1,
            milestones=progress,
            audit_event_ids=(event_id,),
        )
        event = self._event(
            event_id,
            enrollment.enrollment_id,
            1,
            "learner_enrolled",
            actor_id=actor_id or learner_ref,
            actor_role="learner",
            details={
                "program": reference.selector,
                "program_sha256": reference.sha256,
                "organization_id": organization_id or "",
                "authority_context": authority_context,
            },
        )
        saved = self.transactions.execute_create(
            enrollment,
            event,
            command="learner_enrolled",
            idempotency_key=event_id,
        )
        return self._result(saved, "교육 프로그램 가입과 단계별 목표 생성이 완료됐습니다.")

    def start_milestone(
        self,
        enrollment_id: str,
        milestone_id: str,
        *,
        actor_id: str,
        expected_revision: int | None = None,
        authority_context: str = "offline_unverified_actor",
    ) -> EducationPipelineResult:
        """Start one available or returned milestone."""

        enrollment = self.enrollments.load(enrollment_id)
        self._require_revision(enrollment, expected_revision)
        self._require_active(enrollment)
        progress = self._progress(enrollment, milestone_id)
        if progress.status not in {
            MilestoneProgressStatus.AVAILABLE,
            MilestoneProgressStatus.NEEDS_ACTION,
        }:
            raise EducationProgramError(
                f"milestone cannot start from status {progress.status.value}"
            )
        updated_progress = progress.model_copy(
            update={
                "status": MilestoneProgressStatus.IN_PROGRESS,
                "started_at": progress.started_at or datetime.now(UTC),
            }
        )
        saved = self._save_progress_event(
            enrollment,
            updated_progress,
            "milestone_started",
            actor_id=actor_id,
            actor_role="learner",
            details={
                "milestone_id": milestone_id,
                "authority_context": authority_context,
            },
        )
        return self._result(saved, "마일스톤 수행을 시작했습니다.")

    def record_manual_confirmation(
        self,
        enrollment_id: str,
        milestone_id: str,
        requirement_id: str,
        *,
        actor_id: str,
        actor_role: Literal["instructor", "mentor", "administrator"],
        evidence_ref: str,
        expected_revision: int | None = None,
        authority_context: str = "offline_unverified_actor",
    ) -> EducationPipelineResult:
        """Record one configured activity confirmation."""

        enrollment, program, milestone = self._context(enrollment_id, milestone_id)
        self._require_revision(enrollment, expected_revision)
        self._require_active(enrollment)
        requirement = self._requirement(milestone, requirement_id)
        if not isinstance(requirement, ManualConfirmationRequirement):
            raise EducationProgramError("requirement is not a manual confirmation")
        self._require_role(requirement.required_role, actor_role)
        result = RequirementResult(
            requirement_id=requirement_id,
            satisfied=True,
            points_awarded=requirement.points,
            source="manual_confirmation",
            actor_id=actor_id,
            actor_role=actor_role,
            evidence_ref=evidence_ref,
            observed_value="confirmed",
        )
        return self._record_requirement(
            enrollment,
            program,
            milestone,
            result,
            actor_id=actor_id,
            actor_role=actor_role,
            authority_context=authority_context,
        )

    def record_score(
        self,
        enrollment_id: str,
        milestone_id: str,
        requirement_id: str,
        *,
        score: float,
        actor_id: str,
        actor_role: Literal["instructor", "mentor", "administrator"],
        evidence_ref: str,
        expected_revision: int | None = None,
        authority_context: str = "offline_unverified_actor",
    ) -> EducationPipelineResult:
        """Record a score and evaluate its configured threshold."""

        enrollment, program, milestone = self._context(enrollment_id, milestone_id)
        self._require_revision(enrollment, expected_revision)
        self._require_active(enrollment)
        requirement = self._requirement(milestone, requirement_id)
        if not isinstance(requirement, ScoreRequirement):
            raise EducationProgramError("requirement is not a score threshold")
        self._require_role(requirement.required_role, actor_role)
        if not 0.0 <= score <= 100.0:
            raise EducationProgramError("score must be between 0 and 100")
        satisfied = score >= requirement.passing_score
        result = RequirementResult(
            requirement_id=requirement_id,
            satisfied=satisfied,
            points_awarded=requirement.points if satisfied else 0.0,
            source="score",
            actor_id=actor_id,
            actor_role=actor_role,
            evidence_ref=evidence_ref,
            observed_value=f"{score:g}/100",
        )
        return self._record_requirement(
            enrollment,
            program,
            milestone,
            result,
            actor_id=actor_id,
            actor_role=actor_role,
            authority_context=authority_context,
        )

    def bind_project(
        self,
        enrollment_id: str,
        milestone_id: str,
        *,
        project_id: str,
        actor_id: str,
        organization_id: str | None = None,
        expected_revision: int | None = None,
        authority_context: str = "offline_unverified_actor",
    ) -> EducationPipelineResult:
        """Bind exactly one AXCalib project dossier to a project milestone."""

        enrollment, program, milestone = self._context(enrollment_id, milestone_id)
        self._require_revision(enrollment, expected_revision)
        self._require_active(enrollment)
        if milestone.kind.value != "project_certification":
            raise EducationProgramError("only a project milestone may bind a dossier")
        dossier = self.dossiers.load(project_id)
        self._require_project_context(
            dossier,
            enrollment,
            program,
            milestone,
            organization_id=organization_id,
        )
        progress = self._progress(enrollment, milestone_id)
        if progress.bound_project_id and progress.bound_project_id != project_id:
            raise EducationProgramError("milestone already has a different project dossier")
        if progress.status not in {
            MilestoneProgressStatus.AVAILABLE,
            MilestoneProgressStatus.IN_PROGRESS,
            MilestoneProgressStatus.NEEDS_ACTION,
        }:
            raise EducationProgramError("project cannot be bound at the current milestone status")
        updated = progress.model_copy(
            update={
                "bound_project_id": project_id,
                "status": MilestoneProgressStatus.IN_PROGRESS,
                "started_at": progress.started_at or datetime.now(UTC),
            }
        )
        saved = self._save_progress_event(
            enrollment,
            updated,
            "project_bound",
            actor_id=actor_id,
            actor_role="learner",
            details={
                "milestone_id": milestone_id,
                "project_id": project_id,
                "authority_context": authority_context,
            },
        )
        return self._result(saved, "프로젝트 dossier가 교육 마일스톤에 연결됐습니다.")

    def sync_project_milestone(
        self,
        enrollment_id: str,
        milestone_id: str,
        *,
        actor_id: str = "system:education-runtime",
        actor_role: str = "system",
        organization_id: str | None = None,
        expected_revision: int | None = None,
        authority_context: str = "offline_unverified_actor",
    ) -> EducationPipelineResult:
        """Derive project requirement evidence from the trusted local dossier."""

        enrollment, program, milestone = self._context(enrollment_id, milestone_id)
        self._require_revision(enrollment, expected_revision)
        self._require_active(enrollment)
        progress = self._progress(enrollment, milestone_id)
        if not progress.bound_project_id:
            raise EducationProgramError("project milestone has no bound dossier")
        dossier = self.dossiers.load(progress.bound_project_id)
        self._require_project_context(
            dossier,
            enrollment,
            program,
            milestone,
            organization_id=organization_id,
        )
        requirement = next(
            (item for item in milestone.requirements if isinstance(item, ProjectStatusRequirement)),
            None,
        )
        if requirement is None:
            raise EducationProgramError("project milestone has no project status requirement")
        satisfied = self._project_status_satisfies(
            dossier.status,
            requirement.required_status,
        )
        result = RequirementResult(
            requirement_id=requirement.requirement_id,
            satisfied=satisfied,
            points_awarded=requirement.points if satisfied else 0.0,
            source="project_dossier",
            actor_id="system:education-runtime",
            actor_role="system",
            evidence_ref=(
                f"{self.dossiers.path_for(dossier.project_id)}#revision={dossier.revision}"
            ),
            observed_value=dossier.status.value,
        )
        return self._record_requirement(
            enrollment,
            program,
            milestone,
            result,
            actor_id=actor_id,
            actor_role=actor_role,
            authority_context=authority_context,
        )

    def decide_program_completion(
        self,
        enrollment_id: str,
        *,
        command: Literal["approve", "return_for_revision"],
        actor_id: str,
        rationale: str,
        reopen_milestone_ids: tuple[str, ...] = (),
        expected_revision: int | None = None,
        authority_context: str = "offline_unverified_actor",
    ) -> EducationPipelineResult:
        """Apply the mandatory administrator decision for program completion."""

        enrollment = self.enrollments.load(enrollment_id)
        self._require_revision(enrollment, expected_revision)
        if enrollment.status is not EnrollmentStatus.COMPLETION_HITL_PENDING:
            raise EducationProgramError("program completion is not awaiting an administrator")
        if not rationale.strip():
            raise EducationProgramError("administrator rationale must not be empty")
        decision = ProgramCompletionDecision(
            command=command,
            actor_id=actor_id,
            rationale=rationale.strip(),
            authority_context=authority_context,
        )
        milestones = enrollment.milestones
        status = EnrollmentStatus.COMPLETED
        if command == "return_for_revision":
            if not reopen_milestone_ids:
                raise EducationProgramError(
                    "return_for_revision requires at least one reopened milestone"
                )
            unknown = set(reopen_milestone_ids).difference(item.milestone_id for item in milestones)
            if unknown:
                raise EducationProgramError(f"unknown reopened milestones: {sorted(unknown)}")
            milestones = tuple(
                item.model_copy(
                    update={
                        "status": MilestoneProgressStatus.NEEDS_ACTION,
                        "completed_at": None,
                        "requirement_results": (),
                    }
                )
                if item.milestone_id in reopen_milestone_ids
                else item
                for item in milestones
            )
            status = EnrollmentStatus.RETURNED_FOR_REVISION
        event_id = self._event_id()
        candidate = enrollment.model_copy(
            update={
                "status": status,
                "milestones": milestones,
                "completion_decisions": (*enrollment.completion_decisions, decision),
                "audit_event_ids": (*enrollment.audit_event_ids, event_id),
            }
        )
        event = self._event(
            event_id,
            enrollment.enrollment_id,
            enrollment.revision + 1,
            "program_completion_decided",
            actor_id=actor_id,
            actor_role="administrator",
            details={
                "command": command,
                "reopened_milestones": ",".join(reopen_milestone_ids),
                "authority_context": authority_context,
            },
        )
        saved = self.transactions.execute_update(
            candidate,
            expected_revision=enrollment.revision,
            event=event,
            command="program_completion_decided",
            idempotency_key=event_id,
        )
        message = "교육 프로그램 완료가 관리자에 의해 확정됐습니다."
        if command == "return_for_revision":
            message = "보완할 마일스톤이 다시 열렸습니다."
        return self._result(saved, message)

    def _record_requirement(
        self,
        enrollment: EducationEnrollment,
        program: EducationProgram,
        milestone: MilestoneSpec,
        result: RequirementResult,
        *,
        actor_id: str,
        actor_role: str,
        authority_context: str,
    ) -> EducationPipelineResult:
        progress = self._progress(enrollment, milestone.milestone_id)
        if progress.status not in {
            MilestoneProgressStatus.AVAILABLE,
            MilestoneProgressStatus.IN_PROGRESS,
            MilestoneProgressStatus.WAITING_REVIEW,
            MilestoneProgressStatus.NEEDS_ACTION,
        }:
            raise EducationProgramError("requirement cannot be recorded at this milestone status")
        existing = {item.requirement_id: item for item in progress.requirement_results}
        existing[result.requirement_id] = result
        updated = progress.model_copy(
            update={
                "status": MilestoneProgressStatus.IN_PROGRESS,
                "started_at": progress.started_at or datetime.now(UTC),
                "requirement_results": tuple(existing[key] for key in sorted(existing)),
            }
        )
        updated = self._evaluate_milestone(updated, milestone)
        milestones = self._unlock_dependents(
            self._replace_progress(enrollment.milestones, updated),
            program,
        )
        event_id = self._event_id()
        candidate = enrollment.model_copy(
            update={
                "status": EnrollmentStatus.ACTIVE,
                "milestones": milestones,
                "audit_event_ids": (*enrollment.audit_event_ids, event_id),
            }
        )
        event = self._event(
            event_id,
            enrollment.enrollment_id,
            enrollment.revision + 1,
            "requirement_recorded",
            actor_id=actor_id,
            actor_role=actor_role,
            details={
                "milestone_id": milestone.milestone_id,
                "requirement_id": result.requirement_id,
                "satisfied": result.satisfied,
                "source": result.source,
                "authority_context": authority_context,
            },
        )
        saved = self.transactions.execute_update(
            candidate,
            expected_revision=enrollment.revision,
            event=event,
            command="requirement_recorded",
            idempotency_key=event_id,
        )
        saved = self._request_program_completion_if_ready(saved, program)
        return self._result(saved, "마일스톤 조건과 과정 진행률을 갱신했습니다.")

    def _request_program_completion_if_ready(
        self,
        enrollment: EducationEnrollment,
        program: EducationProgram,
    ) -> EducationEnrollment:
        required_ids = {
            milestone.milestone_id
            for _, milestone in program.milestones()
            if milestone.required_for_program_completion
        }
        completed_ids = {
            item.milestone_id
            for item in enrollment.milestones
            if item.status is MilestoneProgressStatus.COMPLETED
        }
        if not required_ids.issubset(completed_ids):
            return enrollment
        if enrollment.status is EnrollmentStatus.COMPLETION_HITL_PENDING:
            return enrollment
        notification_event = NotificationEvent(
            event_type="education_program_completion_approval_requested",
            project_id=enrollment.enrollment_id,
            stage=f"education_program_completion:r{enrollment.revision}",
            revision=enrollment.revision + 1,
            report_ref=(f"education-enrollment:{enrollment.enrollment_id}@r{enrollment.revision}"),
        )
        self.notifier.send(notification_event)
        event_id = self._event_id()
        notification = ProgramNotificationRecord(enrollment_revision=enrollment.revision + 1)
        candidate = enrollment.model_copy(
            update={
                "status": EnrollmentStatus.COMPLETION_HITL_PENDING,
                "notifications": (*enrollment.notifications, notification),
                "audit_event_ids": (*enrollment.audit_event_ids, event_id),
            }
        )
        event = self._event(
            event_id,
            enrollment.enrollment_id,
            enrollment.revision + 1,
            "program_completion_requested",
            actor_id="system:education-runtime",
            actor_role="system",
            details={"required_milestones": ",".join(sorted(required_ids))},
        )
        if not isinstance(self.notifier, DurableNotificationOutbox):
            raise EducationProgramError(
                "education completion requires a durable notification outbox"
            )
        requirement = self.transactions.require_outbox(self.notifier.path_for(notification_event))
        saved = self.transactions.execute_update(
            candidate,
            expected_revision=enrollment.revision,
            event=event,
            command="program_completion_requested",
            idempotency_key=event_id,
            required_artifacts=(requirement,),
        )
        return saved

    @staticmethod
    def _evaluate_milestone(
        progress: MilestoneProgress,
        milestone: MilestoneSpec,
    ) -> MilestoneProgress:
        results = {item.requirement_id: item for item in progress.requirement_results}
        if milestone.completion_rule.mode == "all_required":
            complete = all(
                results.get(item.requirement_id) is not None
                and results[item.requirement_id].satisfied
                for item in milestone.requirements
            )
        else:
            points = sum(item.points_awarded for item in results.values() if item.satisfied)
            complete = points >= (milestone.completion_rule.minimum_points or 0.0)
        if complete:
            return progress.model_copy(
                update={
                    "status": MilestoneProgressStatus.COMPLETED,
                    "completed_at": datetime.now(UTC),
                }
            )
        project_result = next(
            (item for item in results.values() if item.source == "project_dossier"),
            None,
        )
        if project_result is not None and not project_result.satisfied:
            if project_result.observed_value in {
                ProjectStatus.REGISTRATION_HITL_PENDING.value,
                ProjectStatus.COMPLETION_HITL_PENDING.value,
            }:
                return progress.model_copy(
                    update={"status": MilestoneProgressStatus.WAITING_REVIEW}
                )
            if project_result.observed_value in {
                ProjectStatus.REGISTRATION_REJECTED.value,
                ProjectStatus.COMPLETION_NOT_ACCEPTED.value,
            }:
                return progress.model_copy(update={"status": MilestoneProgressStatus.NEEDS_ACTION})
            return progress.model_copy(update={"status": MilestoneProgressStatus.IN_PROGRESS})
        if any(not item.satisfied for item in results.values()):
            return progress.model_copy(update={"status": MilestoneProgressStatus.NEEDS_ACTION})
        return progress

    @staticmethod
    def _unlock_dependents(
        progress_items: tuple[MilestoneProgress, ...],
        program: EducationProgram,
    ) -> tuple[MilestoneProgress, ...]:
        completed = {
            item.milestone_id
            for item in progress_items
            if item.status is MilestoneProgressStatus.COMPLETED
        }
        specs = {milestone.milestone_id: milestone for _, milestone in program.milestones()}
        return tuple(
            item.model_copy(update={"status": MilestoneProgressStatus.AVAILABLE})
            if item.status is MilestoneProgressStatus.LOCKED
            and set(specs[item.milestone_id].prerequisites).issubset(completed)
            else item
            for item in progress_items
        )

    def _context(
        self,
        enrollment_id: str,
        milestone_id: str,
    ) -> tuple[EducationEnrollment, EducationProgram, MilestoneSpec]:
        enrollment = self.enrollments.load(enrollment_id)
        program, reference = self.programs.resolve(enrollment.program.selector)
        if reference.sha256 != enrollment.program.sha256:
            raise EducationProgramError("program content changed after enrollment")
        milestone = self._milestone(program, milestone_id)
        return enrollment, program, milestone

    @staticmethod
    def _require_revision(
        enrollment: EducationEnrollment,
        expected_revision: int | None,
    ) -> None:
        if expected_revision is not None and enrollment.revision != expected_revision:
            raise EducationProgramError(
                f"expected enrollment revision {expected_revision}; current revision is "
                f"{enrollment.revision}"
            )

    @staticmethod
    def _require_project_context(
        dossier: ProjectDossier,
        enrollment: EducationEnrollment,
        program: EducationProgram,
        milestone: MilestoneSpec,
        *,
        organization_id: str | None,
    ) -> None:
        expected_context: dict[str, str] = {
            "program_id": program.program_id,
            "program_version": program.version,
            "enrollment_id": enrollment.enrollment_id,
            "milestone_id": milestone.milestone_id,
            "learner_ref": enrollment.learner_ref,
        }
        if organization_id is not None:
            expected_context["proposer_org_id"] = organization_id
        actual_context = {key: getattr(dossier.review_context, key) for key in expected_context}
        if actual_context != expected_context:
            raise EducationProgramError(
                "project dossier education context does not match this enrollment milestone"
            )

    @staticmethod
    def _milestone(program: EducationProgram, milestone_id: str) -> MilestoneSpec:
        for _, milestone in program.milestones():
            if milestone.milestone_id == milestone_id:
                return milestone
        raise EducationProgramError(f"unknown milestone: {milestone_id}")

    @staticmethod
    def _progress(
        enrollment: EducationEnrollment,
        milestone_id: str,
    ) -> MilestoneProgress:
        for item in enrollment.milestones:
            if item.milestone_id == milestone_id:
                return item
        raise EducationProgramError(f"unknown milestone progress: {milestone_id}")

    @staticmethod
    def _requirement(
        milestone: MilestoneSpec,
        requirement_id: str,
    ) -> ManualConfirmationRequirement | ScoreRequirement | ProjectStatusRequirement:
        for item in milestone.requirements:
            if item.requirement_id == requirement_id:
                return item
        raise EducationProgramError(f"unknown requirement: {requirement_id}")

    @staticmethod
    def _require_role(required_role: str, actor_role: str) -> None:
        if actor_role != required_role and actor_role != "administrator":
            raise EducationProgramError(
                f"requirement needs role {required_role}; actor role is {actor_role}"
            )

    @staticmethod
    def _require_active(enrollment: EducationEnrollment) -> None:
        if enrollment.status not in {
            EnrollmentStatus.ACTIVE,
            EnrollmentStatus.RETURNED_FOR_REVISION,
        }:
            raise EducationProgramError(
                f"enrollment cannot progress from status {enrollment.status.value}"
            )

    @staticmethod
    def _project_status_satisfies(current: ProjectStatus, required: str) -> bool:
        if required == "completion_accepted":
            return current is ProjectStatus.COMPLETION_ACCEPTED
        accepted_registration_states = {
            ProjectStatus.REGISTRATION_APPROVED,
            ProjectStatus.IN_PROGRESS,
            ProjectStatus.COMPLETION_READY,
            ProjectStatus.COMPLETION_APPROVAL_PENDING,
            ProjectStatus.COMPLETION_REGISTERED,
            ProjectStatus.COMPLETION_UNDER_REVIEW,
            ProjectStatus.COMPLETION_HITL_PENDING,
            ProjectStatus.COMPLETION_ACCEPTED,
            ProjectStatus.COMPLETION_NOT_ACCEPTED,
        }
        return current in accepted_registration_states

    def _save_progress_event(
        self,
        enrollment: EducationEnrollment,
        progress: MilestoneProgress,
        event_type: str,
        *,
        actor_id: str,
        actor_role: str,
        details: dict[str, object],
    ) -> EducationEnrollment:
        event_id = self._event_id()
        candidate = enrollment.model_copy(
            update={
                "status": EnrollmentStatus.ACTIVE,
                "milestones": self._replace_progress(enrollment.milestones, progress),
                "audit_event_ids": (*enrollment.audit_event_ids, event_id),
            }
        )
        event = self._event(
            event_id,
            enrollment.enrollment_id,
            enrollment.revision + 1,
            event_type,
            actor_id=actor_id,
            actor_role=actor_role,
            details=details,
        )
        return self.transactions.execute_update(
            candidate,
            expected_revision=enrollment.revision,
            event=event,
            command=event_type,
            idempotency_key=event_id,
        )

    @staticmethod
    def _replace_progress(
        values: tuple[MilestoneProgress, ...],
        updated: MilestoneProgress,
    ) -> tuple[MilestoneProgress, ...]:
        return tuple(
            updated if item.milestone_id == updated.milestone_id else item for item in values
        )

    @staticmethod
    def _event(
        event_id: str,
        enrollment_id: str,
        enrollment_revision: int,
        event_type: str,
        *,
        actor_id: str,
        actor_role: str,
        details: dict[str, object],
    ) -> ProgramAuditEvent:
        return ProgramAuditEvent(
            event_id=event_id,
            enrollment_id=enrollment_id,
            event_type=event_type,
            actor_id=actor_id,
            actor_role=actor_role,
            enrollment_revision=enrollment_revision,
            details=details,
        )

    def _result(
        self,
        enrollment: EducationEnrollment,
        message: str,
    ) -> EducationPipelineResult:
        waiting = enrollment.status is EnrollmentStatus.COMPLETION_HITL_PENDING
        active = tuple(
            item.milestone_id
            for item in enrollment.milestones
            if item.status
            in {
                MilestoneProgressStatus.AVAILABLE,
                MilestoneProgressStatus.IN_PROGRESS,
                MilestoneProgressStatus.WAITING_REVIEW,
                MilestoneProgressStatus.NEEDS_ACTION,
            }
        )
        return EducationPipelineResult(
            pipeline_id=PIPELINE_ID,
            pipeline_version=PIPELINE_VERSION,
            status="waiting_human" if waiting else "succeeded",
            enrollment_id=enrollment.enrollment_id,
            enrollment_status=enrollment.status,
            enrollment_revision=enrollment.revision,
            enrollment_uri=str(self.enrollments.path_for(enrollment.enrollment_id)),
            active_milestone_ids=active,
            allowed_commands=("approve", "return_for_revision") if waiting else (),
            message=message,
        )

    @staticmethod
    def _event_id() -> str:
        return f"evt-edu-{uuid.uuid4()}"


__all__ = [
    "EducationProgramError",
    "EducationProgramService",
    "PIPELINE_ID",
    "PIPELINE_VERSION",
]
