from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from axcalib import AXCalib
from axcalib.pipelines import PipelineContext
from axcalib.runtime import PipelineRunStatus


def test_local_worker_script_processes_one_library_job_without_paths(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    runtime = AXCalib(workspace)
    runtime.enqueue_pipeline(
        "workspace.maintenance",
        "v1alpha1",
        {},
        context=PipelineContext(run_id="script-worker-run"),
    )
    command = [
        sys.executable,
        "scripts/pipelines/run_local_worker_once.py",
        "--workspace",
        str(workspace),
        "--worker-id",
        "worker:script-test",
    ]

    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    body = json.loads(completed.stdout)
    assert body == {
        "attempt": 1,
        "error_code": None,
        "pipeline_id": "workspace.maintenance",
        "pipeline_version": "v1alpha1",
        "processed": True,
        "replayed": False,
        "run_id": "script-worker-run",
        "status": "succeeded",
    }
    assert "checkpoint" not in completed.stdout
    assert runtime.executor.inspect("script-worker-run").status is PipelineRunStatus.SUCCEEDED

    empty = subprocess.run(command, check=False, capture_output=True, text=True)
    assert empty.returncode == 0, empty.stderr
    assert json.loads(empty.stdout) == {"processed": False}
