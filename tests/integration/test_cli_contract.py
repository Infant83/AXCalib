from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from axcalib.cli import app


def test_cli_lists_and_runs_same_allowlisted_pipeline(tmp_path: Path) -> None:
    runner = CliRunner()
    workspace = tmp_path / "workspace"
    listed = runner.invoke(
        app,
        ["pipeline", "list", "--workspace", str(workspace), "--json-output"],
    )
    assert listed.exit_code == 0, listed.output
    assert "workspace.maintenance" in listed.output

    request = tmp_path / "maintenance.json"
    request.write_text("{}\n", encoding="utf-8")
    executed = runner.invoke(
        app,
        [
            "pipeline",
            "run",
            "workspace.maintenance",
            "v1alpha1",
            "--request",
            str(request),
            "--workspace",
            str(workspace),
            "--run-id",
            "cli-maintenance",
        ],
    )
    assert executed.exit_code == 0, executed.output
    assert '"status": "succeeded"' in executed.output

    status = runner.invoke(
        app,
        ["run", "status", "cli-maintenance", "--workspace", str(workspace)],
    )
    assert status.exit_code == 0, status.output
    assert '"run_id": "cli-maintenance"' in status.output


def test_cli_jsonl_batch_keeps_a_durable_result(tmp_path: Path) -> None:
    runner = CliRunner()
    workspace = tmp_path / "workspace"
    manifest = tmp_path / "alpha-batch.jsonl"
    manifest.write_text(
        json.dumps(
            {
                "item_id": "maintenance-report",
                "pipeline_id": "workspace.maintenance",
                "pipeline_version": "v1alpha1",
                "payload": {},
                "idempotency_key": "maintenance-report-1",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["batch", "run", str(manifest), "--workspace", str(workspace)],
    )

    assert result.exit_code == 0, result.output
    assert '"batch_id": "alpha-batch"' in result.output
    assert (workspace / "batches" / "batch-alpha-batch.result.json").is_file()
