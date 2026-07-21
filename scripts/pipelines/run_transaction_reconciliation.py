"""Run the allowlisted local transaction reconciliation pipeline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from axcalib import AXCalib
from axcalib.schemas import PipelineStatus


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reconcile AXCalib project transaction journals without external calls."
    )
    parser.add_argument("workspace", type=Path, help="AXCalib runtime workspace")
    parser.add_argument(
        "--transaction-id",
        help="One transaction ID; omit to reconcile every local journal",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = AXCalib(args.workspace).reconcile_transactions(args.transaction_id)
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 2 if result.status is PipelineStatus.BLOCKED else 0


if __name__ == "__main__":
    raise SystemExit(main())
