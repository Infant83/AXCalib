"""Run the AXCalib local PPTX workflow without embedding domain rules here."""

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
from axcalib.pipelines import TwoGatePptxRequest  # noqa: E402
from axcalib.schemas import ReviewContext  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    """Create the thin file/argument boundary."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("proposal", type=Path)
    parser.add_argument("--proposal-sidecar", type=Path)
    parser.add_argument("--final", dest="final_path", type=Path)
    parser.add_argument("--final-sidecar", type=Path)
    parser.add_argument("--title", required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--project-id")
    parser.add_argument("--config", type=Path, default=ROOT / "config" / "axcalib.toml")
    parser.add_argument(
        "--historical-cases",
        type=Path,
        default=ROOT / "fixtures" / "synthetic" / "historical_cases.json",
    )
    parser.add_argument("--administrator-id", default="admin:local-reviewer")
    parser.add_argument("--registration-decision", choices=("approve", "reject"))
    parser.add_argument("--registration-rationale")
    parser.add_argument("--completion-decision", choices=("accept", "not_accept"))
    parser.add_argument("--completion-rationale")
    parser.add_argument("--mentor-ref")
    parser.add_argument("--review-profile", default="axcalib.default@1.0.0")
    parser.add_argument("--program-id")
    parser.add_argument("--business-unit-id")
    parser.add_argument("--proposer-org-id")
    parser.add_argument("--certification-level")
    parser.add_argument(
        "--docling",
        action="store_true",
        help="Enable the optional local Docling parser and provenance manifest.",
    )
    parser.add_argument(
        "--live-model",
        action="store_true",
        help="Opt in to the configured OpenAI-compatible endpoint; sends evidence text.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Parse I/O, call the library, and print structured output."""

    args = build_parser().parse_args(argv)
    client = AXCalib.from_toml(
        args.config,
        workspace=args.workspace,
        historical_cases_path=args.historical_cases,
        enable_docling=args.docling,
        live_model=args.live_model,
    )
    request = TwoGatePptxRequest(
        proposal_path=args.proposal,
        proposal_sidecar_path=args.proposal_sidecar,
        final_path=args.final_path,
        final_sidecar_path=args.final_sidecar,
        title=args.title,
        project_id=args.project_id,
        administrator_id=args.administrator_id,
        registration_decision=args.registration_decision,
        registration_rationale=args.registration_rationale,
        completion_decision=args.completion_decision,
        completion_rationale=args.completion_rationale,
        mentor_ref=args.mentor_ref,
        review_profile=args.review_profile,
        review_context=ReviewContext(
            program_id=args.program_id,
            business_unit_id=args.business_unit_id,
            proposer_org_id=args.proposer_org_id,
            certification_level=args.certification_level,
        ),
    )
    summary = client.run_pptx(request)
    print(json.dumps(summary.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
