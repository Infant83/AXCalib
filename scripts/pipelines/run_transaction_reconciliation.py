"""Run the allowlisted local transaction reconciliation pipeline."""

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
from axcalib.schemas import PipelineStatus  # noqa: E402


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
