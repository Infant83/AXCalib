"""Run the smallest actual-PPTX AXCalib flow up to the first human gate."""

from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path

from axcalib import AXCalib

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PPTX = ROOT / "tests" / "sources" / "oled_qc_project_outline.pptx"
DEFAULT_SIDECAR = (
    ROOT / "tests" / "sources" / "oled_qc_project_outline.axcalib.json"
)


def run(
    *,
    workspace: Path,
    proposal: Path,
    sidecar: Path,
    project_id: str,
) -> dict[str, object]:
    """Register, submit, and evaluate one proposal without making a human decision."""

    ax = AXCalib(workspace)
    dossier = ax.register_case(
        proposal,
        title="OLED QC 프로젝트 등록심의 Alpha 예제",
        sidecar_path=sidecar,
        project_id=project_id,
    )
    submitted = ax.submit_registration(dossier.project_id)
    draft = ax.evaluate(dossier.project_id, "registration")
    return {
        "schema_version": "axcalib.quickstart-result/v1alpha1",
        "project_id": dossier.project_id,
        "dossier_uri": draft.dossier_uri,
        "dossier_revision": draft.dossier_revision,
        "status": draft.dossier_status.value,
        "pipeline_status": draft.status.value,
        "report_json_uri": draft.report_json_uri,
        "report_markdown_uri": draft.report_markdown_uri,
        "allowed_commands": list(draft.allowed_commands),
        "human_boundary": (
            "Agent 초안만 생성됐습니다. 관리자가 approve 또는 reject를 결정해야 합니다."
        ),
        "submitted_revision": submitted.dossier_revision,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--proposal", type=Path, default=DEFAULT_PPTX)
    parser.add_argument("--sidecar", type=Path, default=DEFAULT_SIDECAR)
    parser.add_argument("--project-id", default=f"alpha-{uuid.uuid4()}")
    args = parser.parse_args()
    result = run(
        workspace=args.workspace.resolve(),
        proposal=args.proposal.resolve(),
        sidecar=args.sidecar.resolve(),
        project_id=args.project_id,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
