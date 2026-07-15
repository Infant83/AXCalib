"""Evidence ingestion ports and offline PPTX adapter."""

from axcalib.ingest.pptx import (
    PARSER_ID,
    PPTX_MEDIA_TYPE,
    PptxEvidenceExtractor,
    PptxSourceError,
    infer_tags,
    sha256_file,
)

__all__ = [
    "PARSER_ID",
    "PPTX_MEDIA_TYPE",
    "PptxEvidenceExtractor",
    "PptxSourceError",
    "infer_tags",
    "sha256_file",
]
