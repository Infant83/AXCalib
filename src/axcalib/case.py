"""Project-id-bound read facade over the latest AXCalib dossier revision."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Literal, TypeVar, overload

from pydantic import ValidationError

from axcalib.reports import CaseViewRenderer
from axcalib.schemas import (
    Assessment,
    AssessmentCount,
    CaseArtifactView,
    CaseEvidenceView,
    CaseLifecycleStage,
    CaseNextAction,
    CaseNotificationView,
    CaseStatus,
    CaseSummary,
    CriterionReviewView,
    EvaluationReport,
    EvidenceLocator,
    ExecutionSummary,
    GateReviewView,
    HumanDecisionView,
    ProjectDossier,
    ReviewProfileRef,
    ReviewStage,
    StageReview,
)
from axcalib.workflows.two_gate import ProjectStatus

CaseOutputFormat = Literal["object", "json", "md"]
MAX_REPORT_BYTES = 10 * 1024 * 1024
SAFE_LOCATOR_FRAGMENT = re.compile(r"^[A-Za-z0-9_.:=,-]{1,128}$")
ViewT = TypeVar("ViewT", CaseStatus, CaseSummary)


class CaseIntegrityError(RuntimeError):
    """Raised when dossier and immutable report references no longer agree."""


def _lifecycle_stage(status: ProjectStatus) -> CaseLifecycleStage:
    if status in {
        ProjectStatus.DRAFT,
        ProjectStatus.REGISTRATION_READY,
        ProjectStatus.REGISTRATION_UNDER_REVIEW,
        ProjectStatus.REGISTRATION_HITL_PENDING,
        ProjectStatus.REGISTRATION_APPROVED,
        ProjectStatus.REGISTRATION_REJECTED,
    }:
        return CaseLifecycleStage.REGISTRATION
    if status is ProjectStatus.IN_PROGRESS:
        return CaseLifecycleStage.EXECUTION
    return CaseLifecycleStage.COMPLETION


def _is_terminal(status: ProjectStatus) -> bool:
    return status in {
        ProjectStatus.REGISTRATION_REJECTED,
        ProjectStatus.COMPLETION_ACCEPTED,
        ProjectStatus.COMPLETION_NOT_ACCEPTED,
    }


def _status_guidance(dossier: ProjectDossier) -> tuple[str | None, tuple[CaseNextAction, ...]]:
    actions: dict[ProjectStatus, tuple[CaseNextAction, ...]] = {
        ProjectStatus.DRAFT: (
            CaseNextAction(
                action_id="submit_registration",
                required_role="submitter_or_project_owner",
                description="등록심의 제출 revision을 준비합니다.",
            ),
        ),
        ProjectStatus.REGISTRATION_READY: (
            CaseNextAction(
                action_id="evaluate.registration",
                required_role="system_or_operator",
                description="고정 snapshot으로 등록심의 Agent 초안을 생성합니다.",
            ),
        ),
        ProjectStatus.REGISTRATION_UNDER_REVIEW: (
            CaseNextAction(
                action_id="reconcile_transactions",
                required_role="operator",
                description="중단된 평가 transaction을 점검하고 복구합니다.",
            ),
        ),
        ProjectStatus.REGISTRATION_HITL_PENDING: (
            CaseNextAction(
                action_id="decide_registration.approve",
                required_role="administrator",
                description="근거와 편향을 검토한 뒤 등록을 승인합니다.",
            ),
            CaseNextAction(
                action_id="decide_registration.reject",
                required_role="administrator",
                description="사유를 기록하고 등록을 반려합니다.",
            ),
        ),
        ProjectStatus.REGISTRATION_APPROVED: (
            CaseNextAction(
                action_id="start_execution",
                required_role="project_owner_or_administrator",
                description="승인된 등록 기준을 유지한 채 수행을 시작합니다.",
            ),
            CaseNextAction(
                action_id="assign_mentor",
                required_role="project_owner_or_administrator",
                description="필요한 경우 완료 제출 승인자를 mentor로 배정합니다.",
            ),
        ),
        ProjectStatus.IN_PROGRESS: (
            CaseNextAction(
                action_id="record_progress",
                required_role="project_owner",
                description="진행 내용과 선택적 증거를 dossier에 추가합니다.",
            ),
            CaseNextAction(
                action_id="submit_completion",
                required_role=(
                    "assigned_mentor"
                    if dossier.execution.mentor_ref
                    else "project_owner_or_administrator"
                ),
                description="완료 증거와 필요한 사람 승인을 함께 등록합니다.",
            ),
        ),
        ProjectStatus.COMPLETION_READY: (
            CaseNextAction(
                action_id="approve_completion_submission",
                required_role=(
                    "assigned_mentor"
                    if dossier.execution.mentor_ref
                    else "project_owner_or_administrator"
                ),
                description="완료평가 제출 등록을 승인합니다.",
            ),
        ),
        ProjectStatus.COMPLETION_APPROVAL_PENDING: (
            CaseNextAction(
                action_id="approve_completion_submission",
                required_role=(
                    "assigned_mentor"
                    if dossier.execution.mentor_ref
                    else "project_owner_or_administrator"
                ),
                description="완료평가 제출 등록을 승인합니다.",
            ),
        ),
        ProjectStatus.COMPLETION_REGISTERED: (
            CaseNextAction(
                action_id="evaluate.completion",
                required_role="system_or_operator",
                description="등록 baseline과 완료 증거를 비교해 Agent 초안을 생성합니다.",
            ),
        ),
        ProjectStatus.COMPLETION_UNDER_REVIEW: (
            CaseNextAction(
                action_id="reconcile_transactions",
                required_role="operator",
                description="중단된 평가 transaction을 점검하고 복구합니다.",
            ),
        ),
        ProjectStatus.COMPLETION_HITL_PENDING: (
            CaseNextAction(
                action_id="decide_completion.accept",
                required_role="administrator",
                description="근거와 편향을 검토한 뒤 완료평가를 수용합니다.",
            ),
            CaseNextAction(
                action_id="decide_completion.not_accept",
                required_role="administrator",
                description="사유를 기록하고 완료평가를 미수용 처리합니다.",
            ),
        ),
    }
    waiting: dict[ProjectStatus, str] = {
        ProjectStatus.REGISTRATION_READY: "registration_evaluation",
        ProjectStatus.REGISTRATION_UNDER_REVIEW: "system_or_recovery",
        ProjectStatus.REGISTRATION_HITL_PENDING: "administrator",
        ProjectStatus.REGISTRATION_APPROVED: "project_owner",
        ProjectStatus.IN_PROGRESS: "project_execution",
        ProjectStatus.COMPLETION_READY: (
            "assigned_mentor" if dossier.execution.mentor_ref else "project_owner_or_administrator"
        ),
        ProjectStatus.COMPLETION_APPROVAL_PENDING: (
            "assigned_mentor" if dossier.execution.mentor_ref else "project_owner_or_administrator"
        ),
        ProjectStatus.COMPLETION_REGISTERED: "completion_evaluation",
        ProjectStatus.COMPLETION_UNDER_REVIEW: "system_or_recovery",
        ProjectStatus.COMPLETION_HITL_PENDING: "administrator",
    }
    return waiting.get(dossier.status), actions.get(dossier.status, ())


class Case:
    """Live read handle for one project; every call reloads its latest dossier."""

    __slots__ = ("_expected_report_sha256", "_load", "_project_id", "_reports_root")

    def __init__(
        self,
        project_id: str,
        *,
        load_dossier: Callable[[str], ProjectDossier],
        reports_root: Path,
        expected_report_sha256: Callable[[str, str, Path], str | None],
    ) -> None:
        self._project_id = project_id
        self._load = load_dossier
        self._reports_root = reports_root.resolve()
        self._expected_report_sha256 = expected_report_sha256
        dossier = self._load(project_id)
        if dossier.project_id != project_id:
            raise CaseIntegrityError("loaded dossier project identity does not match the case")

    @property
    def project_id(self) -> str:
        """Return the immutable project identifier."""

        return self._project_id

    @property
    def dossier(self) -> ProjectDossier:
        """Return a validated snapshot of the latest editable dossier revision."""

        return self._current_dossier()

    @property
    def display_id(self) -> str:
        """Return the latest human-readable display identifier."""

        return self.dossier.display_id

    @property
    def title(self) -> str:
        """Return the latest project title."""

        return self.dossier.title

    @property
    def revision(self) -> int:
        """Return the latest dossier revision."""

        return self.dossier.revision

    @property
    def status(self) -> ProjectStatus:
        """Return the latest dossier lifecycle status."""

        return self.dossier.status

    @property
    def review_profile(self) -> ReviewProfileRef | None:
        """Return the latest frozen review profile reference, if present."""

        return self.dossier.review_profile

    @overload
    def get_current_status(
        self,
        *,
        format: Literal["object"] = "object",
        verbose: bool = False,
    ) -> CaseStatus: ...

    @overload
    def get_current_status(
        self,
        *,
        format: Literal["json", "md"],
        verbose: bool = False,
    ) -> str: ...

    @overload
    def get_current_status(
        self,
        *,
        format: CaseOutputFormat,
        verbose: bool = False,
    ) -> CaseStatus | str: ...

    def get_current_status(
        self,
        *,
        format: CaseOutputFormat = "object",
        verbose: bool = False,
    ) -> CaseStatus | str:
        """Return the current state, blocker, next actions, and latest review result."""

        dossier = self._current_dossier()
        waiting_for, next_actions = _status_guidance(dossier)
        latest = None
        if dossier.completion.report_id is not None:
            latest = self._review_view(dossier, ReviewStage.COMPLETION, verbose=verbose)
        elif dossier.registration.report_id is not None:
            latest = self._review_view(dossier, ReviewStage.REGISTRATION, verbose=verbose)
        value = CaseStatus(
            project_id=dossier.project_id,
            display_id=dossier.display_id,
            title=dossier.title,
            revision=dossier.revision,
            dossier_status=dossier.status,
            lifecycle_stage=_lifecycle_stage(dossier.status),
            terminal=_is_terminal(dossier.status),
            waiting_for=waiting_for,
            next_actions=next_actions,
            latest_review=latest,
            updated_at=dossier.updated_at,
        )
        return self._format(value, format=format, markdown=CaseViewRenderer.status_markdown)

    @overload
    async def aget_current_status(
        self,
        *,
        format: Literal["object"] = "object",
        verbose: bool = False,
    ) -> CaseStatus: ...

    @overload
    async def aget_current_status(
        self,
        *,
        format: Literal["json", "md"],
        verbose: bool = False,
    ) -> str: ...

    @overload
    async def aget_current_status(
        self,
        *,
        format: CaseOutputFormat,
        verbose: bool = False,
    ) -> CaseStatus | str: ...

    async def aget_current_status(
        self,
        *,
        format: CaseOutputFormat = "object",
        verbose: bool = False,
    ) -> CaseStatus | str:
        """Async equivalent of :meth:`get_current_status` with the same result meaning."""

        return await asyncio.to_thread(
            self.get_current_status,
            format=format,
            verbose=verbose,
        )

    @overload
    def get_summary(
        self,
        *,
        format: Literal["object"] = "object",
        verbose: bool = False,
    ) -> CaseSummary: ...

    @overload
    def get_summary(
        self,
        *,
        format: Literal["json", "md"],
        verbose: bool = False,
    ) -> str: ...

    @overload
    def get_summary(
        self,
        *,
        format: CaseOutputFormat,
        verbose: bool = False,
    ) -> CaseSummary | str: ...

    def get_summary(
        self,
        *,
        format: CaseOutputFormat = "object",
        verbose: bool = False,
    ) -> CaseSummary | str:
        """Return one lifecycle digest with Agent and human decisions kept separate."""

        dossier = self._current_dossier()
        profile = dossier.review_profile
        value = CaseSummary(
            project_id=dossier.project_id,
            display_id=dossier.display_id,
            title=dossier.title,
            revision=dossier.revision,
            dossier_status=dossier.status,
            lifecycle_stage=_lifecycle_stage(dossier.status),
            terminal=_is_terminal(dossier.status),
            review_profile=profile.selector if profile else None,
            review_profile_sha256=profile.sha256 if profile else None,
            review_context=dossier.review_context,
            registration=self._review_view(
                dossier,
                ReviewStage.REGISTRATION,
                verbose=verbose,
            ),
            execution=ExecutionSummary(
                started_at=dossier.execution.started_at,
                completion_submitted_at=dossier.execution.completion_submitted_at,
                mentor_assigned=dossier.execution.mentor_ref is not None,
                progress_note_count=len(dossier.execution.notes),
                progress_notes=dossier.execution.notes if verbose else (),
            ),
            completion=self._review_view(
                dossier,
                ReviewStage.COMPLETION,
                verbose=verbose,
            ),
            artifact_count=len(dossier.artifacts),
            artifacts=(
                tuple(
                    CaseArtifactView(
                        artifact_id=item.artifact_id,
                        role=item.role,
                        media_type=item.media_type,
                        sha256=item.sha256,
                        byte_size=item.byte_size,
                    )
                    for item in dossier.artifacts
                )
                if verbose
                else ()
            ),
            notification_count=len(dossier.notifications),
            notifications=(
                tuple(
                    CaseNotificationView(
                        stage=item.stage,
                        event_type=item.event_type,
                        required_role=item.required_role,
                        report_id=item.report_id,
                        dossier_revision=item.dossier_revision,
                        delivery_status=item.delivery_status,
                        recorded_at=item.recorded_at,
                    )
                    for item in dossier.notifications
                )
                if verbose
                else ()
            ),
            audit_event_count=len(dossier.audit_event_ids),
            audit_event_ids=dossier.audit_event_ids if verbose else (),
            updated_at=dossier.updated_at,
        )
        return self._format(value, format=format, markdown=CaseViewRenderer.summary_markdown)

    @overload
    async def aget_summary(
        self,
        *,
        format: Literal["object"] = "object",
        verbose: bool = False,
    ) -> CaseSummary: ...

    @overload
    async def aget_summary(
        self,
        *,
        format: Literal["json", "md"],
        verbose: bool = False,
    ) -> str: ...

    @overload
    async def aget_summary(
        self,
        *,
        format: CaseOutputFormat,
        verbose: bool = False,
    ) -> CaseSummary | str: ...

    async def aget_summary(
        self,
        *,
        format: CaseOutputFormat = "object",
        verbose: bool = False,
    ) -> CaseSummary | str:
        """Async equivalent of :meth:`get_summary` with the same result meaning."""

        return await asyncio.to_thread(
            self.get_summary,
            format=format,
            verbose=verbose,
        )

    def _current_dossier(self) -> ProjectDossier:
        dossier = self._load(self._project_id)
        if dossier.project_id != self._project_id:
            raise CaseIntegrityError("loaded dossier project identity does not match the case")
        return dossier

    def _review_view(
        self,
        dossier: ProjectDossier,
        stage: ReviewStage,
        *,
        verbose: bool,
    ) -> GateReviewView:
        review = dossier.registration if stage is ReviewStage.REGISTRATION else dossier.completion
        report = self._load_report(dossier, review, stage)
        if report is None:
            if review.decision is not None:
                raise CaseIntegrityError(
                    "a human decision exists without its immutable Agent report"
                )
            return GateReviewView(stage=stage)
        decision = review.decision
        if decision is not None:
            if decision.stage is not stage or decision.report_id != report.report_id:
                raise CaseIntegrityError("human decision identity does not match the Agent report")
            valid_commands = (
                {"approve", "reject"}
                if stage is ReviewStage.REGISTRATION
                else {"accept", "not_accept"}
            )
            if decision.command not in valid_commands:
                raise CaseIntegrityError("human decision command is invalid for the review stage")
        criteria_by_id = {item.criterion_id: item for item in report.criteria}
        adjustments = {item.criterion_id: item for item in decision.adjustments} if decision else {}
        if decision is not None and len(adjustments) != len(decision.adjustments):
            raise CaseIntegrityError("duplicate human criterion adjustments were recorded")
        criterion_views: list[CriterionReviewView] = []
        agent_counts: Counter[Assessment] = Counter()
        effective_counts: Counter[Assessment] = Counter()
        for criterion in report.criteria:
            adjustment = adjustments.get(criterion.criterion_id)
            if adjustment is not None and adjustment.from_assessment is not criterion.assessment:
                raise CaseIntegrityError("human adjustment no longer matches the Agent assessment")
            effective = adjustment.to_assessment if adjustment is not None else criterion.assessment
            agent_counts[criterion.assessment] += 1
            effective_counts[effective] += 1
            if verbose:
                criterion_views.append(
                    CriterionReviewView(
                        criterion_id=criterion.criterion_id,
                        title=criterion.title,
                        agent_assessment=criterion.assessment,
                        effective_assessment=effective,
                        human_adjusted=adjustment is not None,
                        observation=criterion.observation,
                        evidence_refs=tuple(
                            self._evidence_view(reference) for reference in criterion.evidence_refs
                        ),
                        adjustment_reason=adjustment.reason if adjustment else None,
                    )
                )
        unknown_adjustments = set(adjustments).difference(criteria_by_id)
        if unknown_adjustments:
            raise CaseIntegrityError("human adjustment references an unknown Agent criterion")
        return GateReviewView(
            stage=stage,
            report_id=report.report_id,
            report_base_revision=report.base_revision,
            snapshot_id=report.snapshot.snapshot_id,
            agent_recommendation=report.recommendation,
            agent_summary=report.recommendation_summary,
            human_decision=(
                HumanDecisionView(
                    command=decision.command,
                    decided_at=decision.decided_at,
                    adjustment_count=len(decision.adjustments),
                    actor_id=decision.actor_id if verbose else None,
                    rationale=decision.rationale if verbose else None,
                    authority_context=decision.authority_context if verbose else None,
                )
                if decision is not None
                else None
            ),
            agent_assessments=self._counts(agent_counts),
            effective_assessments=self._counts(effective_counts),
            adjusted_criterion_count=len(adjustments),
            criteria=tuple(criterion_views),
        )

    def _load_report(
        self,
        dossier: ProjectDossier,
        review: StageReview,
        stage: ReviewStage,
    ) -> EvaluationReport | None:
        if review.report_id is None and review.report_json_uri is None:
            return None
        if review.report_id is None or review.report_json_uri is None:
            raise CaseIntegrityError("dossier contains an incomplete Agent report reference")
        report_path = Path(review.report_json_uri).resolve()
        if not report_path.is_relative_to(self._reports_root):
            raise CaseIntegrityError("Agent report reference is outside the case report store")
        if report_path.suffix.lower() != ".json" or report_path.stem != review.report_id:
            raise CaseIntegrityError("Agent report filename does not match its dossier identity")
        try:
            payload = report_path.read_bytes()
            if len(payload) > MAX_REPORT_BYTES:
                raise CaseIntegrityError("Agent report exceeds the local read limit")
            expected_sha256 = self._expected_report_sha256(
                dossier.project_id,
                review.report_id,
                report_path,
            )
            if expected_sha256 is None:
                raise CaseIntegrityError("Agent report has no committed transaction hash anchor")
            if hashlib.sha256(payload).hexdigest() != expected_sha256:
                raise CaseIntegrityError("Agent report does not match its committed hash anchor")
            report = EvaluationReport.model_validate_json(payload)
        except (OSError, UnicodeError, ValidationError) as error:
            raise CaseIntegrityError("Agent report is missing or invalid") from error
        except RuntimeError as error:
            if isinstance(error, CaseIntegrityError):
                raise
            raise CaseIntegrityError("Agent report hash anchor is invalid") from error
        if (
            report.project_id != dossier.project_id
            or report.stage is not stage
            or report.report_id != review.report_id
            or report.base_revision != report.snapshot.dossier_revision
        ):
            raise CaseIntegrityError("Agent report identity does not match the dossier")
        if review.snapshot is not None and review.snapshot != report.snapshot:
            raise CaseIntegrityError("Agent report snapshot does not match the dossier")
        if review.review_profile is not None and review.review_profile != report.review_profile:
            raise CaseIntegrityError("Agent report policy does not match the dossier")
        artifact = next(
            (
                item
                for item in dossier.artifacts
                if item.artifact_id == review.submission_artifact_id
            ),
            None,
        )
        if artifact is None or artifact.sha256 != report.evaluated_artifact_sha256:
            raise CaseIntegrityError("Agent report evidence hash does not match the dossier")
        return report

    @staticmethod
    def _counts(values: Counter[Assessment]) -> tuple[AssessmentCount, ...]:
        return tuple(
            AssessmentCount(assessment=assessment, count=values[assessment])
            for assessment in Assessment
            if values[assessment]
        )

    @staticmethod
    def _evidence_view(reference: EvidenceLocator) -> CaseEvidenceView:
        locator = reference.locator
        if "#" in locator:
            fragment = locator.rsplit("#", 1)[1]
            locator = (
                f"artifact:{reference.artifact_id}#{fragment}"
                if SAFE_LOCATOR_FRAGMENT.fullmatch(fragment)
                else f"artifact:{reference.artifact_id}"
            )
        elif not locator.startswith(("artifact:", "report:")):
            locator = f"artifact:{reference.artifact_id}"
        return CaseEvidenceView(
            artifact_id=reference.artifact_id,
            locator=locator,
            excerpt=reference.excerpt,
            source=reference.source,
        )

    @staticmethod
    def _format(
        value: ViewT,
        *,
        format: CaseOutputFormat,
        markdown: Callable[[ViewT], str],
    ) -> ViewT | str:
        if format == "object":
            return value
        if format == "json":
            return (
                json.dumps(
                    value.model_dump(mode="json"),
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            )
        if format == "md":
            return markdown(value)
        raise ValueError("format must be one of: object, json, md")


__all__ = ["Case", "CaseIntegrityError", "CaseOutputFormat"]
