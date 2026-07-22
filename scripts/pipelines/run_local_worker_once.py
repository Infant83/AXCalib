"""Claim and execute at most one AXCalib local durable pipeline job."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from axcalib import AXCalib  # noqa: E402
from axcalib.runtime import PipelineRunStatus  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--worker-id", default="worker:local-once")
    parser.add_argument("--lease-seconds", type=float, default=300.0)
    args = parser.parse_args()

    worker = AXCalib(args.workspace).create_worker(
        worker_id=args.worker_id,
        lease_seconds=args.lease_seconds,
    )
    result = worker.run_once()
    if result is None:
        print(json.dumps({"processed": False}, sort_keys=True))
        return 0
    safe_result = {
        "processed": True,
        "run_id": result.run_id,
        "pipeline_id": result.pipeline_id,
        "pipeline_version": result.pipeline_version,
        "status": result.status.value,
        "attempt": result.attempt,
        "error_code": result.error_code,
        "replayed": result.replayed,
    }
    print(json.dumps(safe_result, ensure_ascii=False, indent=2, sort_keys=True))
    failed = {
        PipelineRunStatus.BLOCKED,
        PipelineRunStatus.STALE,
        PipelineRunStatus.RETRYABLE_FAILURE,
        PipelineRunStatus.TERMINAL_FAILURE,
    }
    return 2 if result.status in failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
