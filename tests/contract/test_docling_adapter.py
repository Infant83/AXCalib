import importlib.util
from pathlib import Path

import pytest

from axcalib.ingest import DoclingPptxParser

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tests" / "sources" / "oled_qc_project_outline.pptx"


@pytest.mark.skipif(
    importlib.util.find_spec("docling") is None,
    reason="optional Docling extra is not installed in this test environment",
)
def test_docling_parses_supplied_image_only_pptx_with_explicit_zero_text() -> None:
    result = DoclingPptxParser().parse(SOURCE)

    assert result.manifest.status == "success"
    assert result.manifest.page_count == 16
    assert result.manifest.pages_with_text == 0
    assert result.manifest.text_chars == 0
    assert any("extracted no text" in warning for warning in result.manifest.warnings)
