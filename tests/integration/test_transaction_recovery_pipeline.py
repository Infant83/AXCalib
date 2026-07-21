import json
import subprocess
import sys
from pathlib import Path

import pytest

from axcalib import AXCalib
from axcalib.notifications.base import RecordingNotifier
from axcalib.runtime import TransactionStatus
from axcalib.schemas import PipelineStatus
from axcalib.workflows.two_gate import ProjectStatus

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tests" / "sources" / "oled_qc_project_outline.pptx"
SIDECAR = ROOT / "tests" / "sources" / "oled_qc_project_outline.axcalib.json"


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


def test_hitl_transaction_recovery_does_not_duplicate_notification(
    tmp_path: Path,
) -> None:
    recording = RecordingNotifier()
    client = AXCalib(tmp_path, notifier=recording)
    dossier = client.register_case(
        SOURCE,
        sidecar_path=SIDECAR,
        title="transaction recovery integration",
        project_id="transaction-integration-001",
    )
    client.submit_registration(dossier.project_id)
    client.service.transactions.failure_injector = CrashOnce("after_dossier")

    with pytest.raises(SyntheticCrash, match="after_dossier"):
        client.evaluate(dossier.project_id, "registration")

    interrupted = client.service.dossiers.load(dossier.project_id)
    records = client.service.transactions.journal.records()
    pending = next(
        item
        for item in records
        if item.latest_status is TransactionStatus.RECONCILE_REQUIRED
    )
    assert interrupted.status is ProjectStatus.REGISTRATION_HITL_PENDING
    assert {item.kind for item in pending.plan.required_artifacts} == {
        "report_json",
        "report_markdown",
        "notification_outbox",
    }
    assert len(recording.events) == 1

    result = client.reconcile_transactions(pending.plan.transaction_id)
    repeated = client.reconcile_transactions(pending.plan.transaction_id)

    assert result.status is PipelineStatus.SUCCEEDED
    assert result.results[0].status == "committed"
    assert repeated.results[0].status == "already_committed"
    assert len(recording.events) == 1
    assert len(client.service.audit.entries()) == 3
    assert client.service.transactions.journal.load(
        pending.plan.transaction_id
    ).latest_status is TransactionStatus.COMMITTED


def test_transaction_recovery_script_uses_the_same_pipeline(tmp_path: Path) -> None:
    script = ROOT / "scripts" / "pipelines" / "run_transaction_reconciliation.py"
    completed = subprocess.run(
        [sys.executable, str(script), str(tmp_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["pipeline_id"] == "project.transaction.reconcile"
    assert result["status"] == "succeeded"
    assert result["results"] == []
