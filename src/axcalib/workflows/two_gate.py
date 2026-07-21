"""Reference two-gate workflow used by the P1 offline harness."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from axcalib.notifications.base import NotificationEvent, NotificationPort


class WorkflowError(ValueError):
    """Raised when a transition would violate the workflow contract."""


class ActorRole(StrEnum):
    SYSTEM = "system"
    SUBMITTER = "submitter"
    PROJECT_OWNER = "project_owner"
    MENTOR = "mentor"
    ADMINISTRATOR = "administrator"


class ProjectStatus(StrEnum):
    DRAFT = "draft"
    REGISTRATION_READY = "registration_ready"
    REGISTRATION_UNDER_REVIEW = "registration_under_review"
    REGISTRATION_HITL_PENDING = "registration_hitl_pending"
    REGISTRATION_APPROVED = "registration_approved"
    REGISTRATION_REJECTED = "registration_rejected"
    IN_PROGRESS = "in_progress"
    COMPLETION_READY = "completion_ready"
    COMPLETION_APPROVAL_PENDING = "completion_approval_pending"
    COMPLETION_REGISTERED = "completion_registered"
    COMPLETION_UNDER_REVIEW = "completion_under_review"
    COMPLETION_HITL_PENDING = "completion_hitl_pending"
    COMPLETION_ACCEPTED = "completion_accepted"
    COMPLETION_NOT_ACCEPTED = "completion_not_accepted"


@dataclass(frozen=True, slots=True)
class WorkflowRecord:
    """Minimal state record; the versioned dossier is implemented in WP-01."""

    project_id: str
    status: ProjectStatus = ProjectStatus.DRAFT
    mentor_ref: str | None = None


@dataclass(frozen=True, slots=True)
class TransitionRule:
    source: ProjectStatus
    target: ProjectStatus
    roles: frozenset[ActorRole]
    notification_event: str | None = None


TRANSITIONS: dict[str, TransitionRule] = {
    "submit_registration": TransitionRule(
        ProjectStatus.DRAFT,
        ProjectStatus.REGISTRATION_READY,
        frozenset({ActorRole.SUBMITTER, ActorRole.PROJECT_OWNER}),
    ),
    "start_registration_evaluation": TransitionRule(
        ProjectStatus.REGISTRATION_READY,
        ProjectStatus.REGISTRATION_UNDER_REVIEW,
        frozenset({ActorRole.SYSTEM}),
    ),
    "publish_registration_draft": TransitionRule(
        ProjectStatus.REGISTRATION_UNDER_REVIEW,
        ProjectStatus.REGISTRATION_HITL_PENDING,
        frozenset({ActorRole.SYSTEM}),
        "registration_admin_approval_requested",
    ),
    "approve_registration": TransitionRule(
        ProjectStatus.REGISTRATION_HITL_PENDING,
        ProjectStatus.REGISTRATION_APPROVED,
        frozenset({ActorRole.ADMINISTRATOR}),
    ),
    "reject_registration": TransitionRule(
        ProjectStatus.REGISTRATION_HITL_PENDING,
        ProjectStatus.REGISTRATION_REJECTED,
        frozenset({ActorRole.ADMINISTRATOR}),
    ),
    "start_execution": TransitionRule(
        ProjectStatus.REGISTRATION_APPROVED,
        ProjectStatus.IN_PROGRESS,
        frozenset({ActorRole.PROJECT_OWNER, ActorRole.ADMINISTRATOR}),
    ),
    "request_completion": TransitionRule(
        ProjectStatus.IN_PROGRESS,
        ProjectStatus.COMPLETION_READY,
        frozenset({ActorRole.PROJECT_OWNER}),
    ),
    "request_completion_submission_approval": TransitionRule(
        ProjectStatus.COMPLETION_READY,
        ProjectStatus.COMPLETION_APPROVAL_PENDING,
        frozenset({ActorRole.PROJECT_OWNER}),
    ),
    "approve_completion_submission": TransitionRule(
        ProjectStatus.COMPLETION_APPROVAL_PENDING,
        ProjectStatus.COMPLETION_REGISTERED,
        frozenset({ActorRole.MENTOR, ActorRole.PROJECT_OWNER, ActorRole.ADMINISTRATOR}),
    ),
    "start_completion_evaluation": TransitionRule(
        ProjectStatus.COMPLETION_REGISTERED,
        ProjectStatus.COMPLETION_UNDER_REVIEW,
        frozenset({ActorRole.SYSTEM}),
    ),
    "publish_completion_draft": TransitionRule(
        ProjectStatus.COMPLETION_UNDER_REVIEW,
        ProjectStatus.COMPLETION_HITL_PENDING,
        frozenset({ActorRole.SYSTEM}),
        "completion_admin_approval_requested",
    ),
    "accept_completion": TransitionRule(
        ProjectStatus.COMPLETION_HITL_PENDING,
        ProjectStatus.COMPLETION_ACCEPTED,
        frozenset({ActorRole.ADMINISTRATOR}),
    ),
    "decline_completion": TransitionRule(
        ProjectStatus.COMPLETION_HITL_PENDING,
        ProjectStatus.COMPLETION_NOT_ACCEPTED,
        frozenset({ActorRole.ADMINISTRATOR}),
    ),
}


class TwoGateWorkflow:
    """Apply deterministic transitions and fail closed on missing HITL notifications."""

    def __init__(self, notifier: NotificationPort | None = None) -> None:
        self._notifier = notifier

    def assign_mentor(
        self, record: WorkflowRecord, mentor_ref: str, *, actor_role: ActorRole
    ) -> WorkflowRecord:
        if actor_role not in {ActorRole.PROJECT_OWNER, ActorRole.ADMINISTRATOR}:
            raise WorkflowError("only a project owner or administrator may assign a mentor")
        if record.status not in {ProjectStatus.REGISTRATION_APPROVED, ProjectStatus.IN_PROGRESS}:
            raise WorkflowError("mentor assignment is allowed only after registration approval")
        if not mentor_ref.strip():
            raise WorkflowError("mentor_ref must not be empty")
        return replace(record, mentor_ref=mentor_ref)

    def transition(
        self,
        record: WorkflowRecord,
        trigger: str,
        *,
        actor_role: ActorRole,
        notification_revision: int | None = None,
        notification_report_ref: str | None = None,
    ) -> WorkflowRecord:
        rule = TRANSITIONS.get(trigger)
        if rule is None:
            raise WorkflowError(f"unknown transition trigger: {trigger}")
        if record.status != rule.source:
            raise WorkflowError(
                f"{trigger} requires {rule.source.value}; current status is {record.status.value}"
            )
        if actor_role not in rule.roles:
            raise WorkflowError(f"{actor_role.value} is not allowed to execute {trigger}")
        if trigger == "approve_completion_submission":
            if record.mentor_ref and actor_role is not ActorRole.MENTOR:
                raise WorkflowError("an assigned mentor must approve the completion submission")
            if not record.mentor_ref and actor_role not in {
                ActorRole.PROJECT_OWNER,
                ActorRole.ADMINISTRATOR,
            }:
                raise WorkflowError("without a mentor, the owner or administrator must approve")
        if rule.notification_event:
            if self._notifier is None:
                raise WorkflowError("administrator approval notification is required")
            stage = "registration" if "registration" in rule.notification_event else "completion"
            self._notifier.send(
                NotificationEvent(
                    rule.notification_event,
                    record.project_id,
                    stage,
                    revision=notification_revision,
                    report_ref=notification_report_ref,
                )
            )
        return replace(record, status=rule.target)


def approval_transition_errors() -> list[str]:
    """Return invariant violations in the static transition table."""

    errors: list[str] = []
    human_only_targets = {
        ProjectStatus.REGISTRATION_APPROVED,
        ProjectStatus.REGISTRATION_REJECTED,
        ProjectStatus.COMPLETION_ACCEPTED,
        ProjectStatus.COMPLETION_NOT_ACCEPTED,
    }
    for trigger, rule in TRANSITIONS.items():
        if rule.target in human_only_targets and rule.roles != frozenset({ActorRole.ADMINISTRATOR}):
            errors.append(f"{trigger}: final gate transition must be administrator-only")
    for trigger in ("publish_registration_draft", "publish_completion_draft"):
        if not TRANSITIONS[trigger].notification_event:
            errors.append(f"{trigger}: HITL transition must emit a notification")
    return errors

