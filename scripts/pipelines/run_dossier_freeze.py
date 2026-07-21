"""Freeze one exact dossier revision through the allowlisted local pipeline."""

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
from axcalib.pipelines import DossierFreezePipeline, DossierFreezeRequest  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--expected-revision", type=int, required=True)
    args = parser.parse_args()
    client = AXCalib(args.workspace)
    pipeline = client.registry.create(
        DossierFreezePipeline.pipeline_id,
        DossierFreezePipeline.pipeline_version,
    )
    result = pipeline.run(
        DossierFreezeRequest(
            project_id=args.project_id,
            expected_revision=args.expected_revision,
        )
    )
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0 if result.status.value == "succeeded" else 2


if __name__ == "__main__":
    raise SystemExit(main())
