"""Evidence ingestion ports and local PPTX adapters."""

from axcalib.ingest.docling_pptx import (
    DoclingPptxParser,
    DoclingPptxResult,
    DoclingUnavailableError,
)
from axcalib.ingest.pptx import (
    PARSER_ID,
    PPTX_MEDIA_TYPE,
    PptxEvidenceExtractor,
    PptxSourceError,
    infer_tags,
    sha256_file,
)

__all__ = [
    "DoclingPptxParser",
    "DoclingPptxResult",
    "DoclingUnavailableError",
    "PARSER_ID",
    "PPTX_MEDIA_TYPE",
    "PptxEvidenceExtractor",
    "PptxSourceError",
    "infer_tags",
    "sha256_file",
]
