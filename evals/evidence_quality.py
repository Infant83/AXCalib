"""Evaluate the actual PPTX render, reviewed locators, and criterion traceability."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from axcalib import AXCalib  # noqa: E402
from axcalib.evaluation import evaluate_evidence_quality, load_evidence_gold  # noqa: E402
from axcalib.ingest import (  # noqa: E402
    DoclingPptxParser,
    EmbeddedImagePptxRenderer,
    PptxEvidenceExtractor,
)
from axcalib.pipelines import TwoGatePptxRequest  # noqa: E402
from axcalib.schemas import EvaluationReport, ParserRunManifest  # noqa: E402


def _load_report(markdown_path: str | None) -> EvaluationReport:
    if markdown_path is None:
        raise RuntimeError("expected evaluation report path is missing")
    path = Path(markdown_path).with_suffix(".json")
    return EvaluationReport.model_validate_json(path.read_text(encoding="utf-8"))


def _run(*, with_docling: bool, workspace: Path) -> tuple[dict[str, object], bool]:
    source = ROOT / "tests" / "sources" / "oled_qc_project_outline.pptx"
    sidecar = ROOT / "tests" / "sources" / "oled_qc_project_outline.axcalib.json"
    gold = load_evidence_gold(
        ROOT / "evals" / "datasets" / "oled_qc_pptx_evidence_gold.json",
        source_path=source,
        sidecar_path=sidecar,
    )
    render_manifest = EmbeddedImagePptxRenderer().render(source, workspace / "render")
    evidence = PptxEvidenceExtractor().extract(
        source,
        role="registration_proposal",
        sidecar_path=sidecar,
    )
    client = AXCalib.from_toml(
        ROOT / "config" / "axcalib.toml",
        workspace=workspace / "workflow",
        historical_cases_path=ROOT / "fixtures" / "synthetic" / "historical_cases.json",
    )
    summary = client.run_pptx(
        TwoGatePptxRequest(
            proposal_path=source,
            proposal_sidecar_path=sidecar,
            final_path=source,
            final_sidecar_path=sidecar,
            title="Actual PPTX evidence-quality evaluation",
            project_id="pptx-evidence-quality-001",
            administrator_id="admin:synthetic-eval",
            registration_decision="approve",
            registration_rationale=(
                "근거 품질 회귀평가에서 완료 미수용 경로를 실행하기 위해 등록만 승인한다."
            ),
            completion_decision="not_accept",
            completion_rationale=(
                "동일 hash와 수행증거 부재를 확인하여 완료 미수용 fixture 결정을 기록한다."
            ),
        )
    )
    registration = _load_report(summary.registration_report_uri)
    completion = _load_report(summary.completion_report_uri)
    docling_manifest: ParserRunManifest | None = None
    if with_docling:
        docling_manifest = DoclingPptxParser().parse(source).manifest
    report = evaluate_evidence_quality(
        gold,
        render_manifest=render_manifest,
        evidence=evidence,
        criterion_results=registration.criteria + completion.criteria,
        docling_manifest=docling_manifest,
    )
    payload = report.model_dump(mode="json")
    payload["failures"] = list(report.failures)
    payload["live_model_used"] = False
    payload["embedding_or_vector_db_used"] = False
    payload["docling_requested"] = with_docling
    return payload, report.passed


def main(argv: list[str] | None = None) -> int:
    """Run the offline evidence-quality gate; Docling remains explicit and optional."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--with-docling",
        action="store_true",
        help="also run the installed Docling PPTX contract against the image-only fixture",
    )
    args = parser.parse_args(argv)
    with tempfile.TemporaryDirectory(prefix="axcalib-evidence-quality-") as temporary:
        payload, passed = _run(
            with_docling=args.with_docling,
            workspace=Path(temporary),
        )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
