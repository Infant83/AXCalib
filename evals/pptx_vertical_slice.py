"""Evaluate the supplied PPTX against the offline two-gate acceptance contract."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from axcalib import AXCalib  # noqa: E402
from axcalib.pipelines import TwoGatePptxRequest  # noqa: E402
from axcalib.schemas import EvaluationReport  # noqa: E402


def _load(markdown_path: str | None) -> EvaluationReport:
    if markdown_path is None:
        raise RuntimeError("expected report path is missing")
    path = Path(markdown_path).with_suffix(".json")
    return EvaluationReport.model_validate_json(path.read_text(encoding="utf-8"))


def main() -> int:
    """Run one repeatable local quality gate without live models or embeddings."""

    source = ROOT / "tests" / "sources" / "oled_qc_project_outline.pptx"
    sidecar = ROOT / "tests" / "sources" / "oled_qc_project_outline.axcalib.json"
    with tempfile.TemporaryDirectory(prefix="axcalib-pptx-eval-") as temporary:
        workspace = Path(temporary)
        client = AXCalib.from_toml(
            ROOT / "config" / "axcalib.toml",
            workspace=workspace,
            historical_cases_path=(
                ROOT / "fixtures" / "synthetic" / "historical_cases.json"
            ),
        )
        summary = client.run_pptx(
            TwoGatePptxRequest(
                proposal_path=source,
                proposal_sidecar_path=sidecar,
                final_path=source,
                final_sidecar_path=sidecar,
                title="PPTX vertical-slice evaluation",
                project_id="pptx-evaluation-001",
                administrator_id="admin:synthetic-eval",
                registration_decision="approve",
                registration_rationale=(
                    "등록 보완 제안을 확인하고 두 Gate 회귀평가의 실패 경로 실행만 승인한다."
                ),
                completion_decision="not_accept",
                completion_rationale=(
                    "동일 hash와 수행증거 부재를 확인하여 완료 미수용 fixture 결정을 기록한다."
                ),
            )
        )
        registration = _load(summary.registration_report_uri)
        completion = _load(summary.completion_report_uri)

        assessed_with_evidence = [
            criterion
            for criterion in registration.criteria
            if criterion.assessment.value in {"met", "partially_met"}
        ]
        traceable = sum(bool(item.evidence_refs) for item in assessed_with_evidence)
        checks = {
            "registration_recommendation_needs_changes": (
                registration.recommendation.value == "needs_changes"
            ),
            "completion_recommendation_not_accept": (
                completion.recommendation.value == "not_accept"
            ),
            "same_hash_guard": (
                completion.proposal_artifact_sha256
                == completion.evaluated_artifact_sha256
            ),
            "two_hitl_notifications": summary.notification_count == 2,
            "registration_stage_filter": all(
                case_id.startswith("synthetic-reg-")
                for case_id in registration.retrieval.case_ids
            ),
            "completion_stage_filter": all(
                case_id.startswith("synthetic-completion-")
                for case_id in completion.retrieval.case_ids
            ),
            "zero_similarity_portion": (
                registration.retrieval.similarity_portion == 0.0
                and completion.retrieval.similarity_portion == 0.0
            ),
            "criterion_traceability": traceable == len(assessed_with_evidence),
        }
        result = {
            "dataset": "tests/sources/oled_qc_project_outline.pptx",
            "mode": "offline_ooxml_plus_hash_bound_review_sidecar",
            "live_model_used": False,
            "embedding_or_vector_db_used": False,
            "registration_recommendation": registration.recommendation.value,
            "completion_recommendation": completion.recommendation.value,
            "traceable_assessed_criteria": f"{traceable}/{len(assessed_with_evidence)}",
            "checks": checks,
            "failures": [name for name, passed in checks.items() if not passed],
            "quality_claim": (
                "workflow and deterministic evidence-contract regression only; "
                "no semantic-model or retrieval-quality claim"
            ),
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
