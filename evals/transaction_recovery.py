"""Synthetic crash/restart evaluation for the local project transaction journal."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from axcalib.audit import AuditLog
from axcalib.dossier import DossierRepository
from axcalib.runtime import ProjectTransactionCoordinator
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


def run_boundary(root: Path, boundary: str, index: int) -> dict[str, object]:
    workspace = root / boundary
    repository = DossierRepository(workspace / "dossiers")
    audit = AuditLog(workspace / "audit" / "events.jsonl")
    project_id = f"transaction-eval-{index:03d}"
    base = ProjectDossier(
        project_id=project_id,
        display_id=f"AXC-TXN-{index:03d}",
        title="synthetic transaction recovery",
        revision=1,
        status=ProjectStatus.REGISTRATION_READY,
        audit_event_ids=("evt-created",),
    )
    repository.create(base)
    event_id = f"evt-{boundary}"
    candidate = base.model_copy(
        update={
            "status": ProjectStatus.REGISTRATION_APPROVED,
            "audit_event_ids": (*base.audit_event_ids, event_id),
        }
    )
    event = AuditEvent(
        event_id=event_id,
        project_id=project_id,
        event_type="registration_decided",
        actor_id="admin:synthetic",
        actor_role="administrator",
        dossier_revision=2,
        details={"command": "approve"},
    )
    coordinator = ProjectTransactionCoordinator(
        workspace,
        dossiers=repository,
        audit=audit,
        failure_injector=CrashOnce(boundary),
    )
    crashed = False
    try:
        coordinator.execute_update(
            candidate,
            expected_revision=1,
            audit_event=event,
            command="registration_decided",
            idempotency_key=f"transaction-eval-{index:03d}",
        )
    except SyntheticCrash:
        crashed = True
    first = coordinator.reconcile(f"txn-{event_id}")
    second = coordinator.reconcile(f"txn-{event_id}")
    saved = repository.load(project_id)
    audit_ids = [item["event_id"] for item in audit.entries()]
    passed = all(
        (
            crashed,
            first.status == "committed",
            second.status == "already_committed",
            saved.revision == 2,
            saved.status is ProjectStatus.REGISTRATION_APPROVED,
            audit_ids == [event_id],
        )
    )
    return {
        "boundary": boundary,
        "crash_injected": crashed,
        "first_reconcile": first.status,
        "second_reconcile": second.status,
        "dossier_revision": saved.revision,
        "audit_event_count": len(audit_ids),
        "passed": passed,
    }


def main() -> int:
    boundaries = ("after_prepare", "after_dossier", "after_audit")
    with tempfile.TemporaryDirectory(prefix="axcalib-transaction-eval-") as temporary:
        rows = [
            run_boundary(Path(temporary), boundary, index)
            for index, boundary in enumerate(boundaries, start=1)
        ]
    failures = [row["boundary"] for row in rows if not row["passed"]]
    report = {
        "schema_version": "axcalib.transaction-recovery-eval/v1alpha1",
        "synthetic": True,
        "boundary_count": len(boundaries),
        "rows": rows,
        "failures": failures,
        "passed": not failures,
        "quality_claim": (
            "local dossier/audit crash recovery and idempotency contract only; "
            "no database, distributed worker, or operational delivery claim"
        ),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
