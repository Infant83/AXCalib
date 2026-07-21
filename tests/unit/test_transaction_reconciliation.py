import json
from pathlib import Path

import pytest

from axcalib.audit import AuditLog, AuditLogConflictError
from axcalib.dossier import DossierRepository
from axcalib.runtime import (
    ProjectTransactionCoordinator,
    TransactionBlockedError,
    TransactionIntegrityError,
    TransactionStatus,
)
from axcalib.schemas import AuditEvent, ProjectDossier
from axcalib.workflows.two_gate import ProjectStatus


class SyntheticCrash(RuntimeError):
    pass


class CrashOnce:
    def __init__(self, boundary: str) -> None:
        self.boundary = boundary
        self.triggered = False

    def __call__(self, boundary: str) -> None:
        if boundary == self.boundary and not self.triggered:
            self.triggered = True
            raise SyntheticCrash(boundary)


def _base_dossier(project_id: str = "transaction-test-001") -> ProjectDossier:
    return ProjectDossier(
        project_id=project_id,
        display_id="AXC-TXN-001",
        title="transaction recovery test",
        revision=1,
        status=ProjectStatus.REGISTRATION_READY,
        audit_event_ids=("evt-created",),
    )


def _update(
    base: ProjectDossier,
    *,
    event_id: str = "evt-registration-approved",
) -> tuple[ProjectDossier, AuditEvent]:
    candidate = base.model_copy(
        update={
            "status": ProjectStatus.REGISTRATION_APPROVED,
            "audit_event_ids": (*base.audit_event_ids, event_id),
        }
    )
    event = AuditEvent(
        event_id=event_id,
        project_id=base.project_id,
        event_type="registration_decided",
        actor_id="admin:test",
        actor_role="administrator",
        dossier_revision=2,
        details={"command": "approve"},
    )
    return candidate, event


@pytest.mark.parametrize("boundary", ["after_prepare", "after_dossier", "after_audit"])
def test_reconcile_recovers_every_dossier_audit_boundary_idempotently(
    tmp_path: Path,
    boundary: str,
) -> None:
    repository = DossierRepository(tmp_path / "dossiers")
    audit = AuditLog(tmp_path / "audit" / "events.jsonl")
    base = _base_dossier()
    repository.create(base)
    candidate, event = _update(base)
    coordinator = ProjectTransactionCoordinator(
        tmp_path,
        dossiers=repository,
        audit=audit,
        failure_injector=CrashOnce(boundary),
    )

    with pytest.raises(SyntheticCrash, match=boundary):
        coordinator.execute_update(
            candidate,
            expected_revision=1,
            audit_event=event,
            command="registration_decided",
            idempotency_key="registration-approved-001",
        )

    transaction_id = f"txn-{event.event_id}"
    before = coordinator.journal.load(transaction_id)
    assert before.latest_status is TransactionStatus.RECONCILE_REQUIRED

    recovered = coordinator.reconcile(transaction_id)
    repeated = coordinator.reconcile(transaction_id)
    dossier = repository.load(base.project_id)

    assert recovered.status == "committed"
    assert repeated.status == "already_committed"
    assert dossier.revision == 2
    assert dossier.status is ProjectStatus.REGISTRATION_APPROVED
    assert event.event_id in dossier.audit_event_ids
    assert [item["event_id"] for item in audit.entries()] == [event.event_id]
    assert coordinator.journal.load(transaction_id).latest_status is TransactionStatus.COMMITTED


def test_changed_required_outbox_blocks_state_then_recovers_after_restore(
    tmp_path: Path,
) -> None:
    repository = DossierRepository(tmp_path / "dossiers")
    audit = AuditLog(tmp_path / "audit" / "events.jsonl")
    base = _base_dossier("transaction-outbox-001")
    repository.create(base)
    candidate, event = _update(base, event_id="evt-outbox-bound")
    coordinator = ProjectTransactionCoordinator(
        tmp_path,
        dossiers=repository,
        audit=audit,
    )
    outbox_path = tmp_path / "outbox" / "notification.json"
    outbox_path.parent.mkdir(parents=True)
    recorded = json.dumps(
        {"delivery_status": "recorded", "event_type": "approval_requested"},
        sort_keys=True,
    ) + "\n"
    outbox_path.write_text(recorded, encoding="utf-8")
    requirement = coordinator.require_file(
        outbox_path,
        kind="notification_outbox",
        expected_delivery_status="recorded",
    )
    outbox_path.write_text(
        json.dumps({"delivery_status": "failed"}) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(TransactionBlockedError, match="changed_notification_outbox"):
        coordinator.execute_update(
            candidate,
            expected_revision=1,
            audit_event=event,
            command="registration_draft_published",
            idempotency_key="outbox-bound-001",
            required_artifacts=(requirement,),
        )

    transaction_id = f"txn-{event.event_id}"
    blocked = coordinator.reconcile(transaction_id)
    assert blocked.status == "blocked"
    assert blocked.reason_code == "changed_notification_outbox"
    assert repository.load(base.project_id).revision == 1
    assert audit.entries() == ()

    outbox_path.write_text(recorded, encoding="utf-8")
    recovered = coordinator.reconcile(transaction_id)
    assert recovered.status == "committed"
    assert repository.load(base.project_id).revision == 2
    assert len(audit.entries()) == 1


def test_reconcile_blocks_when_another_revision_won(tmp_path: Path) -> None:
    repository = DossierRepository(tmp_path / "dossiers")
    audit = AuditLog(tmp_path / "audit" / "events.jsonl")
    base = _base_dossier("transaction-stale-001")
    repository.create(base)
    candidate, event = _update(base, event_id="evt-stale-transaction")
    coordinator = ProjectTransactionCoordinator(
        tmp_path,
        dossiers=repository,
        audit=audit,
        failure_injector=CrashOnce("after_prepare"),
    )
    with pytest.raises(SyntheticCrash):
        coordinator.execute_update(
            candidate,
            expected_revision=1,
            audit_event=event,
            command="registration_decided",
            idempotency_key="stale-001",
        )

    other = base.model_copy(
        update={
            "title": "another command won",
            "audit_event_ids": (*base.audit_event_ids, "evt-other"),
        }
    )
    repository.save(other, expected_revision=1)
    result = coordinator.reconcile(f"txn-{event.event_id}")

    assert result.status == "blocked"
    assert result.reason_code == "target_revision_missing_event"
    assert repository.load(base.project_id).title == "another command won"
    assert audit.entries() == ()


def test_journal_hash_chain_detects_tampering(tmp_path: Path) -> None:
    repository = DossierRepository(tmp_path / "dossiers")
    audit = AuditLog(tmp_path / "audit" / "events.jsonl")
    base = _base_dossier("transaction-integrity-001")
    repository.create(base)
    candidate, event = _update(base, event_id="evt-integrity")
    coordinator = ProjectTransactionCoordinator(
        tmp_path,
        dossiers=repository,
        audit=audit,
        failure_injector=CrashOnce("after_prepare"),
    )
    with pytest.raises(SyntheticCrash):
        coordinator.execute_update(
            candidate,
            expected_revision=1,
            audit_event=event,
            command="registration_decided",
            idempotency_key="integrity-001",
        )
    path = coordinator.journal.path_for(f"txn-{event.event_id}")
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            '"status":"prepared"',
            '"status":"committed"',
            1,
        ),
        encoding="utf-8",
    )

    with pytest.raises(TransactionIntegrityError, match="hash mismatch"):
        coordinator.journal.load(f"txn-{event.event_id}")


def test_audit_append_once_rejects_same_id_with_different_content(
    tmp_path: Path,
) -> None:
    audit = AuditLog(tmp_path / "audit" / "events.jsonl")
    first = AuditEvent(
        event_id="evt-audit-conflict",
        project_id="audit-conflict-001",
        event_type="progress_recorded",
        actor_id="owner:first",
        actor_role="project_owner",
        dossier_revision=2,
    )
    conflicting = first.model_copy(update={"actor_id": "owner:other"})

    assert audit.append_once(first) is True
    assert audit.append_once(first) is False
    with pytest.raises(AuditLogConflictError, match="different content"):
        audit.append_once(conflicting)
    assert len(audit.entries()) == 1
