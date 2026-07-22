from __future__ import annotations

import json
from pathlib import Path

import pytest

from axcalib import AXCalib
from axcalib.notifications.base import NotificationEvent, RecordingNotifier
from axcalib.pipelines import EnrollCommand, PipelineContext, StartMilestoneCommand
from axcalib.programs import load_program
from axcalib.runtime import PipelineRunStatus
from axcalib.schemas import (
    EnrollmentStatus,
    ProgramAuditEvent,
    ProgramNotificationRecord,
)

ROOT = Path(__file__).resolve().parents[2]
PROGRAM_PATH = (
    ROOT / "fixtures" / "synthetic" / "education_project_lifecycle" / "program.yaml"
)


class InjectedCrash(RuntimeError):
    pass


class CrashAt:
    def __init__(self, boundary: str) -> None:
        self.boundary = boundary

    def __call__(self, boundary: str) -> None:
        if boundary == self.boundary:
            raise InjectedCrash(boundary)


def _enrolled(client: AXCalib, enrollment_id: str = "enrollment-recovery") -> str:
    reference = client.publish_program(load_program(PROGRAM_PATH))
    result = client.run_education(
        EnrollCommand(
            program_selector=reference.selector,
            learner_ref="learner:recovery",
            enrollment_id=enrollment_id,
        )
    )
    return result.enrollment_id


def test_enrollment_and_audit_reconcile_after_crash(tmp_path: Path) -> None:
    client = AXCalib(tmp_path)
    enrollment_id = _enrolled(client)
    enrollment = client.education.enrollments.load(enrollment_id)
    program, _ = client.education.programs.resolve(
        enrollment.program.selector
    )
    first_milestone = program.milestones()[0][1].milestone_id
    client.education.transactions.failure_injector = CrashAt("after_enrollment")

    with pytest.raises(InjectedCrash):
        client.run_education(
            StartMilestoneCommand(
                enrollment_id=enrollment_id,
                milestone_id=first_milestone,
                actor_id="learner:recovery",
            )
        )

    record = next(
        item
        for item in client.education.transactions.journal.records()
        if item.plan.command == "milestone_started"
    )
    assert client.education.enrollments.load(enrollment_id).revision == 2
    assert len(client.education.audit.entries()) == 1

    client.education.transactions.failure_injector = None
    executed = client.execute_pipeline(
        "education.transaction.reconcile",
        "v1alpha1",
        {"transaction_id": record.plan.transaction_id},
        context=PipelineContext(run_id="education-reconcile"),
    )
    second = client.education.transactions.reconcile(record.plan.transaction_id)

    assert executed.status is PipelineRunStatus.SUCCEEDED
    assert executed.output is not None
    assert executed.output["results"][0]["recovered_artifacts"] == ["audit"]
    assert second.status == "already_committed"
    assert len(client.education.audit.entries()) == 2


def test_changed_education_outbox_blocks_without_duplicate_send(tmp_path: Path) -> None:
    recorder = RecordingNotifier()
    client = AXCalib(tmp_path, notifier=recorder)
    enrollment_id = _enrolled(client, "enrollment-outbox")
    enrollment = client.education.enrollments.load(enrollment_id)
    notification_event = NotificationEvent(
        event_type="education_program_completion_approval_requested",
        project_id=enrollment_id,
        stage=f"education_program_completion:r{enrollment.revision}",
        revision=enrollment.revision + 1,
        report_ref=f"education-enrollment:{enrollment_id}@r{enrollment.revision}",
    )
    client.service.notifier.send(notification_event)
    outbox_path = client.service.notifier.path_for(notification_event)
    original_bytes = outbox_path.read_bytes()
    original = original_bytes.decode("utf-8")
    event_id = "evt-edu-outbox-recovery"
    candidate = enrollment.model_copy(
        update={
            "status": EnrollmentStatus.COMPLETION_HITL_PENDING,
            "notifications": (
                *enrollment.notifications,
                ProgramNotificationRecord(
                    enrollment_revision=enrollment.revision + 1
                ),
            ),
            "audit_event_ids": (*enrollment.audit_event_ids, event_id),
        }
    )
    audit_event = ProgramAuditEvent(
        event_id=event_id,
        enrollment_id=enrollment_id,
        event_type="program_completion_requested",
        actor_id="system:education-runtime",
        actor_role="system",
        enrollment_revision=enrollment.revision + 1,
        details={},
    )
    requirement = client.education.transactions.require_outbox(outbox_path)
    client.education.transactions.failure_injector = CrashAt("after_prepare")
    with pytest.raises(InjectedCrash):
        client.education.transactions.execute_update(
            candidate,
            expected_revision=enrollment.revision,
            event=audit_event,
            command="program_completion_requested",
            idempotency_key=event_id,
            required_artifacts=(requirement,),
        )

    value = json.loads(original)
    value["attempts"] = 99
    outbox_path.write_text(json.dumps(value), encoding="utf-8")
    transaction_id = f"txn-edu-{event_id}"
    client.education.transactions.failure_injector = None
    blocked = client.education.transactions.reconcile(transaction_id)
    assert blocked.status == "blocked"
    assert blocked.reason_code == "changed_notification_outbox"
    assert len(recorder.events) == 1

    outbox_path.write_bytes(original_bytes)
    recovered = client.education.transactions.reconcile(transaction_id)
    assert recovered.status == "committed", recovered.reason_code
    assert len(recorder.events) == 1
