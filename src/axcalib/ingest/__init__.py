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
from axcalib.ingest.slide_render import (
    EmbeddedImagePptxRenderer,
    SlideRenderArtifact,
    SlideRenderer,
    SlideRenderError,
    SlideRenderManifest,
)

__all__ = [
    "DoclingPptxParser",
    "DoclingPptxResult",
    "DoclingUnavailableError",
    "EmbeddedImagePptxRenderer",
    "PARSER_ID",
    "PPTX_MEDIA_TYPE",
    "PptxEvidenceExtractor",
    "PptxSourceError",
    "SlideRenderArtifact",
    "SlideRenderError",
    "SlideRenderManifest",
    "SlideRenderer",
    "infer_tags",
    "sha256_file",
]
