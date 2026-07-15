import json
from pathlib import Path

import pytest

from axcalib.ingest import PptxEvidenceExtractor, PptxSourceError, sha256_file

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tests" / "sources" / "oled_qc_project_outline.pptx"
SIDECAR = ROOT / "tests" / "sources" / "oled_qc_project_outline.axcalib.json"
EXPECTED_SHA256 = "cb0a21ca59330921855f8e7ce4eb6496c47383750332682160ad48188018bd76"


def test_supplied_image_only_pptx_uses_hash_bound_sidecar() -> None:
    extractor = PptxEvidenceExtractor()
    evidence = extractor.extract(
        SOURCE,
        role="registration_proposal",
        sidecar_path=SIDECAR,
    )

    assert sha256_file(SOURCE) == EXPECTED_SHA256
    assert evidence.artifact.sha256 == EXPECTED_SHA256
    assert len(evidence.slides) == 16
    assert evidence.slides[0].text_source == "verified_sidecar"
    assert "problem" in evidence.slides[0].tags
    all_tags = set().union(*(set(slide.tags) for slide in evidence.slides))
    assert "quantitative_target" not in all_tags
    assert "role" not in all_tags
    assert "resource" not in all_tags
    assert "result" not in all_tags


def test_image_only_pptx_without_sidecar_does_not_invent_text() -> None:
    evidence = PptxEvidenceExtractor().extract(
        SOURCE,
        role="registration_proposal",
    )

    assert evidence.text == ""
    assert any("image-only evidence" in warning for warning in evidence.warnings)


def test_sidecar_hash_mismatch_is_rejected(tmp_path: Path) -> None:
    data = json.loads(SIDECAR.read_text(encoding="utf-8"))
    data["source_sha256"] = "0" * 64
    invalid = tmp_path / "invalid.axcalib.json"
    invalid.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(PptxSourceError, match="does not match"):
        PptxEvidenceExtractor().extract(
            SOURCE,
            role="registration_proposal",
            sidecar_path=invalid,
        )
