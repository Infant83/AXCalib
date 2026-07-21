"""Filesystem-backed two-gate PPTX workflow for the offline MVP."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from axcalib.audit import AuditLog
from axcalib.dossier import DossierRepository, RevisionConflictError, SnapshotRepository
from axcalib.evaluation import EvidenceEvaluator, OfflineEvidenceEvaluator
from axcalib.ingest import DoclingPptxParser, PptxEvidenceExtractor
from axcalib.notifications.base import NotificationEvent, NotificationPort, RecordingNotifier
from axcalib.notifications.outbox import DurableNotificationOutbox
from axcalib.policies import (
    DEFAULT_REVIEW_PROFILE,
    ResolvedReviewProfile,
    ReviewProfileRegistry,
)
from axcalib.reports import ReportRenderer
from axcalib.runtime import (
    ProjectTransactionCoordinator,
    TransactionArtifactRequirement,
)
from axcalib.schemas import (
    ArtifactRef,
    AuditEvent,
    EffectiveConfigRef,
    EvaluationReport,
    EvidenceDocument,
    HumanDecision,
    NotificationRecord,
    PipelineResult,
    PipelineStatus,
    ProjectDossier,
    ReviewContext,
    ReviewerAdjustment,
    ReviewStage,
    StageReview,
    WorkflowRunSummary,
)
from axcalib.workflows.two_gate import (
    ActorRole,
    ProjectStatus,
    TwoGateWorkflow,
    WorkflowRecord,
)

PIPELINE_ID = "two-gate-pptx"
PIPELINE_VERSION = "v1alpha1"


class TwoGatePptxRequest(BaseModel):
    """Input for an explicit, resumable local two-gate demonstration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    proposal_path: Path
    title: str = Field(min_length=1, max_length=300)
    proposal_sidecar_path: Path | None = None
    final_path: Path | None = None
    final_sidecar_path: Path | None = None
    project_id: str | None = None
    idempotency_key: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
    )
    administrator_id: str = "admin:local-reviewer"
    registration_decision: Literal["approve", "reject"] | None = None
    registration_rationale: str | None = None
    completion_decision: Literal["accept", "not_accept"] | None = None
    completion_rationale: str | None = None
    mentor_ref: str | None = None
    review_profile: str = DEFAULT_REVIEW_PROFILE
    review_context: ReviewContext = Field(default_factory=ReviewContext)

    @model_validator(mode="after")
    def decisions_require_rationales(self) -> TwoGatePptxRequest:
        """Prevent implicit or rationale-free human decisions."""

        if self.registration_decision and not (self.registration_rationale or "").strip():
            raise ValueError("registration_rationale is required with a decision")
        if self.completion_decision and not (self.completion_rationale or "").strip():
            raise ValueError("completion_rationale is required with a decision")
        if self.completion_decision and self.registration_decision != "approve":
            raise ValueError("completion decision requires explicit registration approval")
        return self


class LocalProjectService:
    """Application service used by scripts, future CLI/API, and tests."""

    def __init__(
        self,
        workspace: Path,
        *,
        notifier: NotificationPort | None = None,
        evaluator: EvidenceEvaluator | None = None,
        review_profiles: ReviewProfileRegistry | None = None,
        default_review_profile: str = DEFAULT_REVIEW_PROFILE,
        docling_parser: DoclingPptxParser | None = None,
        effective_config: EffectiveConfigRef | None = None,
    ) -> None:
        self.workspace = workspace.resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.dossiers = DossierRepository(self.workspace / "dossiers")
        self.snapshots = SnapshotRepository(self.workspace / "snapshots")
        self.reports = ReportRenderer(self.workspace / "reports")
        self.audit = AuditLog(self.workspace / "audit" / "events.jsonl")
        self.delivery_notifier = notifier or RecordingNotifier()
        self.notifier = DurableNotificationOutbox(
            self.workspace / "outbox",
            self.delivery_notifier,
        )
        self.transactions = ProjectTransactionCoordinator(
            self.workspace,
            dossiers=self.dossiers,
            audit=self.audit,
        )
        self.workflow = TwoGateWorkflow(self.notifier)
        self.extractor = PptxEvidenceExtractor()
        self.docling_parser = docling_parser
        self.effective_config = effective_config
        self.evaluator = evaluator or OfflineEvidenceEvaluator()
        self.review_profiles = review_profiles or ReviewProfileRegistry.with_builtin_default()
        self.default_review_profile = default_review_profile

    def create_project(
        self,
        proposal_path: Path,
        *,
        title: str,
        sidecar_path: Path | None = None,
        project_id: str | None = None,
        review_profile: str | None = None,
        review_context: ReviewContext | None = None,
    ) -> ProjectDossier:
        """Create one dossier whose source artifact remains external and hash-addressed."""

        identifier = project_id or str(uuid.uuid4())
        resolved_profile = self.review_profiles.resolve(
            review_profile or self.default_review_profile,
            allow_offline_reference=True,
        )
        artifact = self.extractor.artifact_ref(
            proposal_path,
            role="registration_proposal",
            sidecar_path=sidecar_path,
        )
        event_id = self._event_id()
        dossier = ProjectDossier(
            project_id=identifier,
            display_id=f"AXC-{identifier[:8].upper()}",
            title=title.strip(),
            revision=1,
            status=ProjectStatus.DRAFT,
            review_context=review_context or ReviewContext(),
            review_profile=resolved_profile.ref,
            effective_config=self.effective_config,
            artifacts=(artifact,),
            registration=StageReview(
                submission_artifact_id=artifact.artifact_id,
                review_profile=resolved_profile.ref,
            ),
            audit_event_ids=(event_id,),
        )
        event = AuditEvent(
            event_id=event_id,
            project_id=dossier.project_id,
            event_type="project_created",
            actor_id="submitter:local",
            actor_role=ActorRole.SUBMITTER.value,
            dossier_revision=1,
            details={
                "artifact_id": artifact.artifact_id,
                "artifact_sha256": artifact.sha256,
                "review_profile": resolved_profile.ref.selector,
                "review_profile_sha256": resolved_profile.ref.sha256,
            },
        )
        return self.transactions.execute_create(
            dossier,
            event,
            command="project_created",
            idempotency_key=event_id,
        )

    def submit_registration(self, project_id: str) -> PipelineResult:
        """Submit a draft to the registration-ready checkpoint."""

        dossier = self.dossiers.load(project_id)
        record = self._transition(dossier, "submit_registration", ActorRole.SUBMITTER)
        updated = dossier.model_copy(update={"status": record.status})
        saved = self._save_event(
            updated,
            dossier.revision,
            "registration_submitted",
            "submitter:local",
            ActorRole.SUBMITTER,
            {"trigger": "submit_registration"},
        )
        return self._result(saved, "등록심의 평가를 실행할 수 있습니다.")

    def evaluate_registration(self, project_id: str) -> PipelineResult:
        """Freeze, evaluate, report, notify, and wait for an administrator."""

        dossier = self.dossiers.load(project_id)
        profile = self._review_profile(dossier)
        snapshot = self.snapshots.freeze(dossier)
        artifact = self._artifact(dossier, dossier.registration.submission_artifact_id)
        evidence = self._extract(artifact)
        report = self.evaluator.evaluate_registration(dossier, snapshot, evidence, profile)
        rendered = self.reports.render(report)
        record = self._transition(
            dossier,
            "start_registration_evaluation",
            ActorRole.SYSTEM,
        )
        record = self.workflow.transition(
            record,
            "publish_registration_draft",
            actor_role=ActorRole.SYSTEM,
            notification_revision=dossier.revision + 1,
            notification_report_ref=report.report_id,
        )
        notification = NotificationRecord(
            event_type="registration_admin_approval_requested",
            stage=ReviewStage.REGISTRATION,
            required_role=ActorRole.ADMINISTRATOR.value,
            report_id=report.report_id,
            dossier_revision=dossier.revision + 1,
        )
        review = dossier.registration.model_copy(
            update={
                "snapshot": snapshot,
                "report_id": report.report_id,
                "report_json_uri": str(rendered.json_path),
                "report_markdown_uri": str(rendered.markdown_path),
                "review_profile": profile.ref,
            }
        )
        updated = dossier.model_copy(
            update={
                "status": record.status,
                "registration": review,
                "notifications": (*dossier.notifications, notification),
            }
        )
        saved = self._save_event(
            updated,
            dossier.revision,
            "registration_draft_published",
            "system:offline-evaluator",
            ActorRole.SYSTEM,
            {
                "report_id": report.report_id,
                "recommendation": report.recommendation.value,
                "notification_event": notification.event_type,
                "snapshot_id": snapshot.snapshot_id,
                "review_profile_sha256": profile.ref.sha256,
            },
        )
        return self._result(
            saved,
            "등록심의 Agent 초안이 생성됐습니다. 관리자 결정이 필요합니다.",
            report=report,
            allowed_commands=("approve", "reject"),
        )

    def decide_registration(
        self,
        project_id: str,
        *,
        command: Literal["approve", "reject"],
        actor_id: str,
        rationale: str,
        adjustments: tuple[ReviewerAdjustment, ...] = (),
    ) -> PipelineResult:
        """Apply an explicit administrator registration decision."""

        dossier = self.dossiers.load(project_id)
        if not rationale.strip():
            raise ValueError("administrator rationale must not be empty")
        trigger = "approve_registration" if command == "approve" else "reject_registration"
        record = self._transition(dossier, trigger, ActorRole.ADMINISTRATOR)
        report_id = self._required_report_id(dossier.registration)
        report = self._load_report(dossier.registration)
        self._validate_adjustments(report, adjustments)
        decision = HumanDecision(
            stage=ReviewStage.REGISTRATION,
            command=command,
            actor_id=actor_id,
            actor_role=ActorRole.ADMINISTRATOR.value,
            rationale=rationale.strip(),
            report_id=report_id,
            adjustments=adjustments,
        )
        updated = dossier.model_copy(
            update={
                "status": record.status,
                "registration": dossier.registration.model_copy(update={"decision": decision}),
            }
        )
        saved = self._save_event(
            updated,
            dossier.revision,
            "registration_decided",
            actor_id,
            ActorRole.ADMINISTRATOR,
            {
                "command": command,
                "report_id": report_id,
                "adjustment_count": str(len(adjustments)),
                "adjusted_criteria": ",".join(item.criterion_id for item in adjustments),
            },
        )
        message = "등록 승인으로 수행 단계 진입이 가능합니다."
        if command == "reject":
            message = "등록 반려가 확정되어 이 수행 프로세스는 종료됩니다."
        return self._result(saved, message)

    def assign_mentor(self, project_id: str, *, mentor_ref: str) -> PipelineResult:
        """Assign an optional mentor after registration approval."""

        dossier = self.dossiers.load(project_id)
        record = self.workflow.assign_mentor(
            self._record(dossier),
            mentor_ref,
            actor_role=ActorRole.PROJECT_OWNER,
        )
        execution = dossier.execution.model_copy(update={"mentor_ref": record.mentor_ref})
        updated = dossier.model_copy(update={"execution": execution})
        saved = self._save_event(
            updated,
            dossier.revision,
            "mentor_assigned",
            "project-owner:local",
            ActorRole.PROJECT_OWNER,
            {"mentor_ref": mentor_ref},
        )
        return self._result(saved, "멘토가 배정됐습니다.")

    def start_execution(self, project_id: str) -> PipelineResult:
        """Start execution only after administrator registration approval."""

        dossier = self.dossiers.load(project_id)
        record = self._transition(dossier, "start_execution", ActorRole.PROJECT_OWNER)
        execution = dossier.execution.model_copy(update={"started_at": datetime.now(UTC)})
        updated = dossier.model_copy(update={"status": record.status, "execution": execution})
        saved = self._save_event(
            updated,
            dossier.revision,
            "execution_started",
            "project-owner:local",
            ActorRole.PROJECT_OWNER,
            {"trigger": "start_execution"},
        )
        return self._result(saved, "과제 수행 단계가 시작됐습니다.")

    def record_progress(
        self,
        project_id: str,
        *,
        note: str,
        artifact_path: Path | None = None,
        sidecar_path: Path | None = None,
        expected_revision: int | None = None,
    ) -> PipelineResult:
        """Append a progress note and optional hash-addressed PPTX evidence."""

        dossier = self.dossiers.load(project_id)
        if expected_revision is not None and dossier.revision != expected_revision:
            raise RevisionConflictError(
                f"expected revision {expected_revision}; current revision is {dossier.revision}"
            )
        if dossier.status is not ProjectStatus.IN_PROGRESS:
            raise ValueError("progress can be recorded only while the project is in progress")
        if not note.strip():
            raise ValueError("progress note must not be empty")
        artifacts = dossier.artifacts
        artifact_id = "none"
        if artifact_path is not None:
            artifact = self.extractor.artifact_ref(
                artifact_path,
                role="progress_evidence",
                sidecar_path=sidecar_path,
            )
            artifact_id = artifact.artifact_id
            if all(existing.artifact_id != artifact.artifact_id for existing in artifacts):
                artifacts = (*artifacts, artifact)
        execution = dossier.execution.model_copy(
            update={"notes": (*dossier.execution.notes, note.strip())}
        )
        updated = dossier.model_copy(update={"execution": execution, "artifacts": artifacts})
        saved = self._save_event(
            updated,
            dossier.revision,
            "progress_recorded",
            "project-owner:local",
            ActorRole.PROJECT_OWNER,
            {"artifact_id": artifact_id, "note_length": str(len(note.strip()))},
        )
        return self._result(saved, "수행 진행기록이 dossier에 추가됐습니다.")

    def submit_completion(
        self,
        project_id: str,
        final_path: Path,
        *,
        sidecar_path: Path | None = None,
        approval_actor_id: str = "project-owner:local",
        approval_actor_role: ActorRole = ActorRole.PROJECT_OWNER,
    ) -> PipelineResult:
        """Register final evidence after the required owner or mentor approval."""

        dossier = self.dossiers.load(project_id)
        artifact = self.extractor.artifact_ref(
            final_path,
            role="completion_final",
            sidecar_path=sidecar_path,
        )
        record = self._transition(dossier, "request_completion", ActorRole.PROJECT_OWNER)
        record = self.workflow.transition(
            record,
            "request_completion_submission_approval",
            actor_role=ActorRole.PROJECT_OWNER,
        )
        record = self.workflow.transition(
            record,
            "approve_completion_submission",
            actor_role=approval_actor_role,
        )
        completion = StageReview(
            submission_artifact_id=artifact.artifact_id,
            review_profile=dossier.review_profile,
        )
        execution = dossier.execution.model_copy(
            update={"completion_submitted_at": datetime.now(UTC)}
        )
        updated = dossier.model_copy(
            update={
                "status": record.status,
                "artifacts": (*dossier.artifacts, artifact),
                "completion": completion,
                "execution": execution,
            }
        )
        saved = self._save_event(
            updated,
            dossier.revision,
            "completion_registered",
            approval_actor_id,
            approval_actor_role,
            {
                "artifact_id": artifact.artifact_id,
                "artifact_sha256": artifact.sha256,
                "approval_role": approval_actor_role.value,
            },
        )
        return self._result(saved, "완료평가 제출이 등록됐습니다.")

    def evaluate_completion(self, project_id: str) -> PipelineResult:
        """Compare completion evidence with the frozen registration baseline."""

        dossier = self.dossiers.load(project_id)
        profile = self._review_profile(dossier)
        snapshot = self.snapshots.freeze(dossier)
        artifact = self._artifact(dossier, dossier.completion.submission_artifact_id)
        evidence = self._extract(artifact)
        registration_report = self._load_report(dossier.registration)
        report = self.evaluator.evaluate_completion(
            dossier,
            snapshot,
            evidence,
            registration_report,
            profile,
        )
        rendered = self.reports.render(report)
        record = self._transition(dossier, "start_completion_evaluation", ActorRole.SYSTEM)
        record = self.workflow.transition(
            record,
            "publish_completion_draft",
            actor_role=ActorRole.SYSTEM,
            notification_revision=dossier.revision + 1,
            notification_report_ref=report.report_id,
        )
        notification = NotificationRecord(
            event_type="completion_admin_approval_requested",
            stage=ReviewStage.COMPLETION,
            required_role=ActorRole.ADMINISTRATOR.value,
            report_id=report.report_id,
            dossier_revision=dossier.revision + 1,
        )
        review = dossier.completion.model_copy(
            update={
                "snapshot": snapshot,
                "report_id": report.report_id,
                "report_json_uri": str(rendered.json_path),
                "report_markdown_uri": str(rendered.markdown_path),
                "review_profile": profile.ref,
            }
        )
        updated = dossier.model_copy(
            update={
                "status": record.status,
                "completion": review,
                "notifications": (*dossier.notifications, notification),
            }
        )
        saved = self._save_event(
            updated,
            dossier.revision,
            "completion_draft_published",
            "system:offline-evaluator",
            ActorRole.SYSTEM,
            {
                "report_id": report.report_id,
                "recommendation": report.recommendation.value,
                "notification_event": notification.event_type,
                "snapshot_id": snapshot.snapshot_id,
                "review_profile_sha256": profile.ref.sha256,
            },
        )
        return self._result(
            saved,
            "완료평가 Agent 초안이 생성됐습니다. 관리자 결정이 필요합니다.",
            report=report,
            allowed_commands=("accept", "not_accept"),
        )

    def decide_completion(
        self,
        project_id: str,
        *,
        command: Literal["accept", "not_accept"],
        actor_id: str,
        rationale: str,
        adjustments: tuple[ReviewerAdjustment, ...] = (),
    ) -> PipelineResult:
        """Apply an explicit administrator completion decision."""

        dossier = self.dossiers.load(project_id)
        if not rationale.strip():
            raise ValueError("administrator rationale must not be empty")
        trigger = "accept_completion" if command == "accept" else "decline_completion"
        record = self._transition(dossier, trigger, ActorRole.ADMINISTRATOR)
        report_id = self._required_report_id(dossier.completion)
        report = self._load_report(dossier.completion)
        self._validate_adjustments(report, adjustments)
        decision = HumanDecision(
            stage=ReviewStage.COMPLETION,
            command=command,
            actor_id=actor_id,
            actor_role=ActorRole.ADMINISTRATOR.value,
            rationale=rationale.strip(),
            report_id=report_id,
            adjustments=adjustments,
        )
        updated = dossier.model_copy(
            update={
                "status": record.status,
                "completion": dossier.completion.model_copy(update={"decision": decision}),
            }
        )
        saved = self._save_event(
            updated,
            dossier.revision,
            "completion_decided",
            actor_id,
            ActorRole.ADMINISTRATOR,
            {
                "command": command,
                "report_id": report_id,
                "adjustment_count": str(len(adjustments)),
                "adjusted_criteria": ",".join(item.criterion_id for item in adjustments),
            },
        )
        return self._result(saved, "완료평가 관리자 결정이 기록됐습니다.")

    def run_two_gate(self, request: TwoGatePptxRequest) -> WorkflowRunSummary:
        """Run until a human wait or through both explicitly supplied decisions."""

        dossier = self.create_project(
            request.proposal_path,
            title=request.title,
            sidecar_path=request.proposal_sidecar_path,
            project_id=request.project_id,
            review_profile=request.review_profile,
            review_context=request.review_context,
        )
        self.submit_registration(dossier.project_id)
        registration_result = self.evaluate_registration(dossier.project_id)
        if request.registration_decision is None:
            return self._summary(dossier.project_id, registration_result.report_markdown_uri)
        self.decide_registration(
            dossier.project_id,
            command=request.registration_decision,
            actor_id=request.administrator_id,
            rationale=request.registration_rationale or "",
        )
        if request.registration_decision == "reject":
            return self._summary(dossier.project_id, registration_result.report_markdown_uri)
        if request.mentor_ref:
            self.assign_mentor(dossier.project_id, mentor_ref=request.mentor_ref)
        self.start_execution(dossier.project_id)
        final_path = request.final_path or request.proposal_path
        final_sidecar = request.final_sidecar_path
        if final_sidecar is None and final_path.resolve() == request.proposal_path.resolve():
            final_sidecar = request.proposal_sidecar_path
        approval_role = ActorRole.MENTOR if request.mentor_ref else ActorRole.PROJECT_OWNER
        approval_actor = request.mentor_ref or "project-owner:local"
        self.submit_completion(
            dossier.project_id,
            final_path,
            sidecar_path=final_sidecar,
            approval_actor_id=approval_actor,
            approval_actor_role=approval_role,
        )
        completion_result = self.evaluate_completion(dossier.project_id)
        if request.completion_decision is not None:
            self.decide_completion(
                dossier.project_id,
                command=request.completion_decision,
                actor_id=request.administrator_id,
                rationale=request.completion_rationale or "",
            )
        return self._summary(
            dossier.project_id,
            registration_result.report_markdown_uri,
            completion_result.report_markdown_uri,
        )

    def _save_event(
        self,
        dossier: ProjectDossier,
        expected_revision: int,
        event_type: str,
        actor_id: str,
        actor_role: ActorRole,
        details: dict[str, str],
    ) -> ProjectDossier:
        event_id = self._event_id()
        candidate = dossier.model_copy(
            update={"audit_event_ids": (*dossier.audit_event_ids, event_id)}
        )
        event = AuditEvent(
            event_id=event_id,
            project_id=candidate.project_id,
            event_type=event_type,
            actor_id=actor_id,
            actor_role=actor_role.value,
            dossier_revision=expected_revision + 1,
            details=details,
        )
        return self.transactions.execute_update(
            candidate,
            expected_revision=expected_revision,
            audit_event=event,
            command=event_type,
            idempotency_key=event_id,
            required_artifacts=self._transaction_requirements(
                candidate,
                target_revision=expected_revision + 1,
            ),
        )

    def _transaction_requirements(
        self,
        dossier: ProjectDossier,
        *,
        target_revision: int,
    ) -> tuple[TransactionArtifactRequirement, ...]:
        """Bind report and recorded outbox files before entering a HITL state."""

        if dossier.status is ProjectStatus.REGISTRATION_HITL_PENDING:
            stage = ReviewStage.REGISTRATION
            review = dossier.registration
        elif dossier.status is ProjectStatus.COMPLETION_HITL_PENDING:
            stage = ReviewStage.COMPLETION
            review = dossier.completion
        else:
            return ()
        if not review.report_id or not review.report_json_uri or not review.report_markdown_uri:
            raise RuntimeError("HITL transaction requires both rendered report files")
        notification = next(
            (
                item
                for item in reversed(dossier.notifications)
                if item.stage is stage
                and item.report_id == review.report_id
                and item.dossier_revision == target_revision
            ),
            None,
        )
        if notification is None or notification.delivery_status != "recorded":
            raise RuntimeError("HITL transaction requires a recorded notification")
        outbox_event = NotificationEvent(
            event_type=notification.event_type,
            project_id=dossier.project_id,
            stage=stage.value,
            required_role=notification.required_role,
            revision=target_revision,
            report_ref=review.report_id,
        )
        return (
            self.transactions.require_file(
                Path(review.report_json_uri),
                kind="report_json",
                expected_report_id=review.report_id,
            ),
            self.transactions.require_file(
                Path(review.report_markdown_uri),
                kind="report_markdown",
            ),
            self.transactions.require_file(
                self.notifier.path_for(outbox_event),
                kind="notification_outbox",
                expected_delivery_status="recorded",
            ),
        )

    def _result(
        self,
        dossier: ProjectDossier,
        message: str,
        *,
        report: EvaluationReport | None = None,
        allowed_commands: tuple[str, ...] = (),
    ) -> PipelineResult:
        return PipelineResult(
            pipeline_id=PIPELINE_ID,
            pipeline_version=PIPELINE_VERSION,
            status=(PipelineStatus.WAITING_HUMAN if allowed_commands else PipelineStatus.SUCCEEDED),
            project_id=dossier.project_id,
            dossier_status=dossier.status,
            dossier_revision=dossier.revision,
            dossier_uri=str(self.dossiers.path_for(dossier.project_id)),
            report_id=report.report_id if report else None,
            report_json_uri=(
                dossier.registration.report_json_uri
                if report and report.stage is ReviewStage.REGISTRATION
                else dossier.completion.report_json_uri
                if report
                else None
            ),
            report_markdown_uri=(
                dossier.registration.report_markdown_uri
                if report and report.stage is ReviewStage.REGISTRATION
                else dossier.completion.report_markdown_uri
                if report
                else None
            ),
            allowed_commands=allowed_commands,
            message=message,
        )

    def _summary(
        self,
        project_id: str,
        registration_report_uri: str | None,
        completion_report_uri: str | None = None,
    ) -> WorkflowRunSummary:
        dossier = self.dossiers.load(project_id)
        if not registration_report_uri:
            raise RuntimeError("registration report URI is required for a workflow summary")
        return WorkflowRunSummary(
            project_id=project_id,
            final_status=dossier.status,
            dossier_uri=str(self.dossiers.path_for(project_id)),
            registration_report_uri=registration_report_uri,
            completion_report_uri=completion_report_uri,
            registration_decision=dossier.registration.decision,
            completion_decision=dossier.completion.decision,
            notification_count=len(dossier.notifications),
            audit_uri=str(self.audit.path),
        )

    def _extract(self, artifact: ArtifactRef) -> EvidenceDocument:
        sidecar = artifact.metadata.get("sidecar_uri")
        evidence = self.extractor.extract(
            Path(artifact.uri),
            role=artifact.role,
            sidecar_path=Path(sidecar) if sidecar else None,
        )
        frozen_sidecar_hash = artifact.metadata.get("sidecar_sha256")
        current_sidecar_hash = evidence.artifact.metadata.get("sidecar_sha256")
        if frozen_sidecar_hash != current_sidecar_hash:
            raise RuntimeError(
                "sidecar evidence changed after dossier registration; create a new revision"
            )
        if self.docling_parser is None:
            return evidence
        docling = self.docling_parser.parse(Path(artifact.uri))
        by_slide = {slide.slide_number: slide for slide in docling.slides}
        merged = []
        for slide in evidence.slides:
            parsed = by_slide.get(slide.slide_number)
            if parsed is not None and parsed.text and not slide.text:
                merged.append(
                    slide.model_copy(
                        update={
                            "text": parsed.text,
                            "tags": parsed.tags,
                            "text_source": parsed.text_source,
                            "is_blank": False,
                        }
                    )
                )
            else:
                merged.append(slide)
        warnings = list(evidence.warnings)
        warnings.extend(docling.manifest.warnings)
        if docling.manifest.page_count != len(evidence.slides):
            warnings.append(
                "Docling and OOXML slide counts differ; OOXML slide numbering was retained."
            )
        return evidence.model_copy(
            update={
                "slides": tuple(merged),
                "parser_id": f"{evidence.parser_id}+{docling.manifest.parser_id}",
                "parser_runs": (*evidence.parser_runs, docling.manifest),
                "warnings": tuple(dict.fromkeys(warnings)),
            }
        )

    @staticmethod
    def _artifact(dossier: ProjectDossier, artifact_id: str | None) -> ArtifactRef:
        if artifact_id is None:
            raise RuntimeError("submission artifact is missing")
        for artifact in dossier.artifacts:
            if artifact.artifact_id == artifact_id:
                return artifact
        raise RuntimeError(f"submission artifact not found: {artifact_id}")

    @staticmethod
    def _record(dossier: ProjectDossier) -> WorkflowRecord:
        return WorkflowRecord(
            project_id=dossier.project_id,
            status=dossier.status,
            mentor_ref=dossier.execution.mentor_ref,
        )

    def _transition(
        self,
        dossier: ProjectDossier,
        trigger: str,
        actor_role: ActorRole,
    ) -> WorkflowRecord:
        return self.workflow.transition(
            self._record(dossier),
            trigger,
            actor_role=actor_role,
        )

    @staticmethod
    def _required_report_id(review: StageReview) -> str:
        if not review.report_id:
            raise RuntimeError("review report is missing")
        return review.report_id

    @staticmethod
    def _load_report(review: StageReview) -> EvaluationReport:
        if not review.report_json_uri:
            raise RuntimeError("registration report JSON is missing")
        return EvaluationReport.model_validate_json(
            Path(review.report_json_uri).read_text(encoding="utf-8")
        )

    def _review_profile(self, dossier: ProjectDossier) -> ResolvedReviewProfile:
        if dossier.review_profile is None:
            raise RuntimeError("dossier has no frozen review profile")
        return self.review_profiles.resolve_ref(
            dossier.review_profile,
            allow_offline_reference=True,
        )

    @staticmethod
    def _validate_adjustments(
        report: EvaluationReport,
        adjustments: tuple[ReviewerAdjustment, ...],
    ) -> None:
        criteria = {item.criterion_id: item for item in report.criteria}
        seen: set[str] = set()
        for adjustment in adjustments:
            if adjustment.criterion_id in seen:
                raise ValueError(f"duplicate reviewer adjustment: {adjustment.criterion_id}")
            seen.add(adjustment.criterion_id)
            criterion = criteria.get(adjustment.criterion_id)
            if criterion is None:
                raise ValueError(
                    f"reviewer adjustment criterion is not in the Agent report: "
                    f"{adjustment.criterion_id}"
                )
            if criterion.assessment is not adjustment.from_assessment:
                raise ValueError(
                    f"reviewer adjustment base assessment is stale for {adjustment.criterion_id}"
                )

    @staticmethod
    def _event_id() -> str:
        return f"evt-{uuid.uuid4()}"


class TwoGatePptxPipeline:
    """Composable total workflow with matching sync and async entrypoints."""

    pipeline_id = PIPELINE_ID
    pipeline_version = PIPELINE_VERSION

    def __init__(self, service: LocalProjectService) -> None:
        self.service = service

    def run(self, request: TwoGatePptxRequest) -> WorkflowRunSummary:
        """Run the local workflow synchronously."""

        return self.service.run_two_gate(request)

    async def arun(self, request: TwoGatePptxRequest) -> WorkflowRunSummary:
        """Run with the same semantics without blocking the event loop."""

        return await asyncio.to_thread(self.run, request)


__all__ = [
    "LocalProjectService",
    "PIPELINE_ID",
    "PIPELINE_VERSION",
    "TwoGatePptxPipeline",
    "TwoGatePptxRequest",
]
