"""Deterministic Library MVP/Alpha execution and recovery quality gate."""

from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from axcalib import AXCalib
from axcalib.pipelines import EnrollCommand, PipelineContext, StartMilestoneCommand
from axcalib.programs import load_program
from axcalib.runtime import (
    BatchItem,
    BatchManifest,
    PipelineJobStatus,
    PipelineRunStatus,
)

ROOT = Path(__file__).resolve().parents[1]
PROGRAM = ROOT / "fixtures" / "synthetic" / "education_project_lifecycle" / "program.yaml"


class InjectedCrash(RuntimeError):
    """Synthetic process interruption at an explicit transaction boundary."""


def _crash_after_enrollment(boundary: str) -> None:
    if boundary == "after_enrollment":
        raise InjectedCrash(boundary)


def main() -> int:
    checks: dict[str, bool] = {}
    with TemporaryDirectory(prefix="axcalib-alpha-eval-") as directory:
        workspace = Path(directory)
        client = AXCalib(workspace)

        report_context = PipelineContext(run_id="eval-maintenance-report")
        first = client.execute_pipeline(
            "workspace.maintenance",
            "v1alpha1",
            {},
            context=report_context,
        )
        replay = client.execute_pipeline(
            "workspace.maintenance",
            "v1alpha1",
            {},
            context=report_context,
        )
        checks["pipeline_checkpoint_succeeded"] = (
            first.status is PipelineRunStatus.SUCCEEDED and first.attempt == 1
        )
        checks["pipeline_replay_is_idempotent"] = replay.replayed and replay.attempt == 1

        queued_context = PipelineContext(run_id="eval-durable-worker")
        prepared = client.enqueue_pipeline(
            "workspace.maintenance",
            "v1alpha1",
            {},
            context=queued_context,
        )
        checks["worker_enqueue_does_not_execute_inline"] = (
            prepared.status is PipelineRunStatus.PREPARED
            and prepared.attempt == 0
            and client.jobs.load(queued_context.run_id).status is PipelineJobStatus.QUEUED
        )
        worker_result = client.create_worker(worker_id="worker:alpha-eval").run_once()
        worker_replay = client.enqueue_pipeline(
            "workspace.maintenance",
            "v1alpha1",
            {},
            context=queued_context,
        )
        checks["worker_executes_and_replays_exact_run"] = (
            worker_result is not None
            and worker_result.status is PipelineRunStatus.SUCCEEDED
            and worker_result.attempt == 1
            and worker_replay.replayed
            and worker_replay.attempt == 1
            and client.jobs.load(queued_context.run_id).status is PipelineJobStatus.COMPLETED
        )

        batch = BatchManifest(
            batch_id="eval-alpha-batch",
            items=(
                BatchItem(
                    item_id="report-one",
                    pipeline_id="workspace.maintenance",
                    pipeline_version="v1alpha1",
                    payload={},
                    idempotency_key="eval-report-one",
                ),
                BatchItem(
                    item_id="report-two",
                    pipeline_id="workspace.maintenance",
                    pipeline_version="v1alpha1",
                    payload={},
                    idempotency_key="eval-report-two",
                ),
            ),
        )
        batch_first = client.run_batch(batch, max_concurrency=1)
        batch_replay = client.run_batch(batch, max_concurrency=1)
        checks["batch_items_succeeded"] = batch_first.status == "succeeded"
        checks["batch_resume_replayed_all_items"] = all(
            item.replayed for item in batch_replay.items
        )

        reference = client.publish_program(load_program(PROGRAM))
        enrollment_id = "alpha-eval-enrollment"
        client.run_education(
            EnrollCommand(
                program_selector=reference.selector,
                learner_ref="learner:alpha-eval",
                enrollment_id=enrollment_id,
            )
        )
        enrollment = client.education.enrollments.load(enrollment_id)
        program, _ = client.education.programs.resolve(enrollment.program.selector)
        milestone_id = program.milestones()[0][1].milestone_id
        client.education.transactions.failure_injector = _crash_after_enrollment
        try:
            client.run_education(
                StartMilestoneCommand(
                    enrollment_id=enrollment_id,
                    milestone_id=milestone_id,
                    actor_id="learner:alpha-eval",
                )
            )
        except InjectedCrash:
            pass
        else:
            checks["education_crash_injected"] = False
        record = next(
            item
            for item in client.education.transactions.journal.records()
            if item.plan.command == "milestone_started"
        )
        client.education.transactions.failure_injector = None
        recovered = client.execute_pipeline(
            "education.transaction.reconcile",
            "v1alpha1",
            {"transaction_id": record.plan.transaction_id},
            context=PipelineContext(run_id="eval-education-reconcile"),
        )
        checks["education_crash_injected"] = True
        checks["education_reconcile_succeeded"] = recovered.status is PipelineRunStatus.SUCCEEDED
        checks["education_audit_exactly_once"] = len(client.education.audit.entries()) == 2

        stale_lock = workspace / "dossiers" / ".stale-eval.lock"
        stale_lock.write_text("pid=99999999\n", encoding="utf-8")
        old = stale_lock.stat().st_mtime - 7200
        os.utime(stale_lock, (old, old))
        maintenance = client.execute_pipeline(
            "workspace.maintenance",
            "v1alpha1",
            {
                "apply": True,
                "stale_after_seconds": 60,
                "retention_seconds": 60,
            },
            context=PipelineContext(run_id="eval-maintenance-apply"),
        )
        actions = (maintenance.output or {}).get("actions", [])
        checks["stale_lock_quarantined_not_deleted"] = any(
            item.get("relative_path") == "dossiers/.stale-eval.lock"
            and item.get("decision") == "quarantined"
            and item.get("destination")
            for item in actions
        )

    failures = sorted(name for name, passed in checks.items() if not passed)
    result = {
        "schema_version": "axcalib.library-mvp-alpha-eval/v1alpha1",
        "synthetic": True,
        "checks": checks,
        "failures": failures,
        "passed": not failures,
        "quality_claim": (
            "local library execution, replay, durable single-host worker queue, batch, "
            "education reconciliation, and non-destructive maintenance contract only; "
            "no distributed operation, model, or retrieval quality claim"
        ),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
