"""Evaluate the actual-PPT education project lifecycle reference contract."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
for candidate in (ROOT / "src", ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from examples.education_project_lifecycle.run_full_lifecycle import run  # noqa: E402


def main() -> int:
    proposal = ROOT / "tests" / "sources" / "oled_qc_project_outline.pptx"
    completion = (
        ROOT
        / "fixtures"
        / "synthetic"
        / "education_project_lifecycle"
        / "completion_report.synthetic.pptx"
    )
    sidecar = json.loads(
        (ROOT / "tests" / "sources" / "oled_qc_project_outline.axcalib.json").read_text(
            encoding="utf-8"
        )
    )
    with tempfile.TemporaryDirectory(prefix="axcalib-education-eval-") as temporary:
        result = run(Path(temporary))
    milestone_values = cast(dict[str, str], result["milestones"])
    checks = {
        "actual_proposal_hash_bound": (
            hashlib.sha256(proposal.read_bytes()).hexdigest()
            == sidecar["source_sha256"]
        ),
        "proposal_has_13_reviewed_visual_locators": len(sidecar["slides"]) == 13,
        "completion_has_distinct_hash": (
            hashlib.sha256(proposal.read_bytes()).hexdigest()
            != hashlib.sha256(completion.read_bytes()).hexdigest()
        ),
        "project_completed_after_two_hitl": (
            result["project_status"] == "completion_accepted"
            and result["project_notification_count"] == 2
        ),
        "completion_agent_proposal_accept": result["completion_recommendation"] == "accept",
        "all_program_milestones_completed": set(milestone_values.values())
        == {"completed"},
        "program_completion_human_gate_recorded": (
            result["enrollment_status"] == "completed"
            and result["program_notification_count"] == 1
        ),
    }
    output = {
        "dataset": "education_project_lifecycle",
        "mode": "offline_actual_proposal_plus_synthetic_completion",
        "live_model_used": False,
        "embedding_or_vector_db_used": False,
        "checks": checks,
        "failures": [name for name, passed in checks.items() if not passed],
        "quality_claim": (
            "program/project workflow, locator, and human-authority regression only; "
            "no official education, model, or retrieval quality claim"
        ),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 1 if output["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
