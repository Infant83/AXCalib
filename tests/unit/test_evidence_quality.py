import json
import shutil
from pathlib import Path

import pytest

from axcalib.evaluation import (
    EvidenceGoldError,
    evaluate_evidence_quality,
    load_evidence_gold,
)
from axcalib.ingest import EmbeddedImagePptxRenderer, PptxEvidenceExtractor
from axcalib.schemas import Assessment, CriterionResult, EvidenceLocator

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tests" / "sources" / "oled_qc_project_outline.pptx"
SIDECAR = ROOT / "tests" / "sources" / "oled_qc_project_outline.axcalib.json"
GOLD = ROOT / "evals" / "datasets" / "oled_qc_pptx_evidence_gold.json"


def _gold():
    return load_evidence_gold(GOLD, source_path=SOURCE, sidecar_path=SIDECAR)


def test_gold_dataset_is_bound_to_all_reviewed_visual_locators() -> None:
    gold = _gold()

    assert len(gold.items) == 13
    assert len(gold.reference_fields) == 12
    assert {item.slide_number for item in gold.items} == {
        1,
        2,
        3,
        4,
        5,
        7,
        8,
        9,
        10,
        11,
        12,
        13,
        14,
    }


def test_gold_loader_rejects_reviewed_sidecar_drift(tmp_path: Path) -> None:
    source = tmp_path / SOURCE.name
    sidecar = tmp_path / SIDECAR.name
    shutil.copy2(SOURCE, source)
    shutil.copy2(SIDECAR, sidecar)
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    data["slides"][0]["summary"] += " 변경"
    sidecar.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(EvidenceGoldError, match="sidecar_sha256"):
        load_evidence_gold(GOLD, source_path=source, sidecar_path=sidecar)


def test_quality_report_covers_render_sidecar_and_criterion_traceability(
    tmp_path: Path,
) -> None:
    evidence = PptxEvidenceExtractor().extract(
        SOURCE,
        role="registration_proposal",
        sidecar_path=SIDECAR,
    )
    artifact = evidence.artifact
    criteria = (
        CriterionResult(
            criterion_id="TEST-EVIDENCE",
            title="근거가 있는 판단",
            assessment=Assessment.MET,
            observation="검토된 슬라이드 근거가 있다.",
            evidence_refs=(
                EvidenceLocator(
                    artifact_id=artifact.artifact_id,
                    locator=f"{artifact.uri}#slide=1",
                    excerpt=evidence.slides[0].text,
                    source=evidence.slides[0].text_source,
                ),
            ),
        ),
        CriterionResult(
            criterion_id="TEST-INSUFFICIENT",
            title="판단불가 기록",
            assessment=Assessment.INSUFFICIENT_EVIDENCE,
            observation="제출자료에서 판단할 근거를 찾지 못했다.",
        ),
    )

    report = evaluate_evidence_quality(
        _gold(),
        render_manifest=EmbeddedImagePptxRenderer().render(SOURCE, tmp_path / "render"),
        evidence=evidence,
        criterion_results=criteria,
    )

    assert report.passed
    assert report.locator_recall == 1.0
    assert report.reference_field_coverage == 1.0
    assert report.traceable_criterion_count == 2
    assert report.unsupported_claim_count == 0
    assert report.unresolved_evidence_reference_count == 0
    assert report.ooxml_text_slide_count == 0
    assert report.verified_sidecar_slide_count == 13


def test_quality_report_rejects_assertion_without_evidence(tmp_path: Path) -> None:
    evidence = PptxEvidenceExtractor().extract(
        SOURCE,
        role="registration_proposal",
        sidecar_path=SIDECAR,
    )
    unsupported = CriterionResult(
        criterion_id="TEST-UNSUPPORTED",
        title="근거 없는 부정 판단",
        assessment=Assessment.NOT_MET,
        observation="근거 없이 충족하지 않았다고 주장했다.",
    )

    report = evaluate_evidence_quality(
        _gold(),
        render_manifest=EmbeddedImagePptxRenderer().render(SOURCE, tmp_path / "render"),
        evidence=evidence,
        criterion_results=(unsupported,),
    )

    assert not report.passed
    assert report.unsupported_claim_count == 1
    assert report.failures == ("criterion_traceability",)
