from __future__ import annotations

import pytest

from axcalib import ActorRole, ProjectStatus, RecordingNotifier, TwoGateWorkflow, WorkflowRecord
from axcalib.workflows.two_gate import WorkflowError, approval_transition_errors


def _registration_hitl(workflow: TwoGateWorkflow) -> WorkflowRecord:
    record = WorkflowRecord("synthetic-test")
    record = workflow.transition(record, "submit_registration", actor_role=ActorRole.SUBMITTER)
    record = workflow.transition(
        record, "start_registration_evaluation", actor_role=ActorRole.SYSTEM
    )
    return workflow.transition(record, "publish_registration_draft", actor_role=ActorRole.SYSTEM)


def test_final_registration_decision_is_administrator_only() -> None:
    workflow = TwoGateWorkflow(RecordingNotifier())
    record = _registration_hitl(workflow)
    with pytest.raises(WorkflowError):
        workflow.transition(record, "approve_registration", actor_role=ActorRole.SYSTEM)
    approved = workflow.transition(
        record, "approve_registration", actor_role=ActorRole.ADMINISTRATOR
    )
    assert approved.status is ProjectStatus.REGISTRATION_APPROVED


def test_hitl_transition_fails_without_notification_adapter() -> None:
    workflow = TwoGateWorkflow()
    record = WorkflowRecord("synthetic-test")
    record = workflow.transition(record, "submit_registration", actor_role=ActorRole.SUBMITTER)
    record = workflow.transition(
        record, "start_registration_evaluation", actor_role=ActorRole.SYSTEM
    )
    with pytest.raises(WorkflowError, match="notification is required"):
        workflow.transition(record, "publish_registration_draft", actor_role=ActorRole.SYSTEM)


def test_assigned_mentor_must_approve_completion_submission() -> None:
    workflow = TwoGateWorkflow(RecordingNotifier())
    record = _registration_hitl(workflow)
    record = workflow.transition(
        record, "approve_registration", actor_role=ActorRole.ADMINISTRATOR
    )
    record = workflow.assign_mentor(
        record, "mentor:synthetic", actor_role=ActorRole.ADMINISTRATOR
    )
    record = workflow.transition(record, "start_execution", actor_role=ActorRole.PROJECT_OWNER)
    record = workflow.transition(record, "request_completion", actor_role=ActorRole.PROJECT_OWNER)
    record = workflow.transition(
        record, "request_completion_submission_approval", actor_role=ActorRole.PROJECT_OWNER
    )
    with pytest.raises(WorkflowError, match="assigned mentor"):
        workflow.transition(
            record, "approve_completion_submission", actor_role=ActorRole.PROJECT_OWNER
        )
    record = workflow.transition(
        record, "approve_completion_submission", actor_role=ActorRole.MENTOR
    )
    assert record.status is ProjectStatus.COMPLETION_REGISTERED


def test_static_transition_table_satisfies_human_approval_invariants() -> None:
    assert approval_transition_errors() == []

