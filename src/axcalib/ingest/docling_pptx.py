"""Optional Docling PPTX adapter with slide-level provenance and coverage."""

from __future__ import annotations

from importlib import import_module
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from axcalib.ingest.pptx import infer_tags, sha256_file
from axcalib.schemas import FrozenModel, ParserRunManifest, SlideEvidence


class DoclingUnavailableError(RuntimeError):
    """Raised when the optional Docling dependency is not installed."""


class DoclingPptxResult(FrozenModel):
    """Normalized slide evidence plus a content-free parser manifest."""

    slides: tuple[SlideEvidence, ...]
    manifest: ParserRunManifest


class DoclingPptxParser:
    """Convert one local PPTX through Docling without remote fetches."""

    def parse(self, path: Path) -> DoclingPptxResult:
        """Parse a PPTX and report zero-text image-only outcomes explicitly."""

        try:
            docling_version = version("docling")
            input_format = import_module("docling.datamodel.base_models").InputFormat
            document_converter = import_module("docling.document_converter").DocumentConverter
        except (ImportError, PackageNotFoundError) as error:
            raise DoclingUnavailableError(
                "Docling is optional; install the axcalib docling extra before enabling it"
            ) from error

        resolved = path.resolve()
        converter = document_converter(allowed_formats=[input_format.PPTX])
        conversion = converter.convert(resolved, raises_on_error=False)
        parser_id = f"docling/{docling_version}:pptx"
        document = conversion.document
        page_count = len(document.pages) if document is not None else 0
        slides: list[SlideEvidence] = []
        if document is not None:
            for page_number in range(1, page_count + 1):
                text = document.export_to_text(page_no=page_number).strip()
                slides.append(
                    SlideEvidence(
                        slide_number=page_number,
                        text=text,
                        tags=infer_tags(text),
                        text_source=parser_id,
                        image_count=0,
                        is_blank=not text,
                    )
                )
        pages_with_text = sum(bool(slide.text) for slide in slides)
        text_chars = sum(len(slide.text) for slide in slides)
        warnings: list[str] = []
        if page_count and pages_with_text == 0:
            warnings.append(
                "Docling parsed the PPTX structure but extracted no text; image/VLM or "
                "hash-bound reviewed sidecar evidence is required."
            )
        if conversion.errors:
            warnings.append(f"Docling reported {len(conversion.errors)} conversion error(s).")
        return DoclingPptxResult(
            slides=tuple(slides),
            manifest=ParserRunManifest(
                parser_id=parser_id,
                status=str(conversion.status.value),
                source_sha256=sha256_file(resolved),
                page_count=page_count,
                pages_with_text=pages_with_text,
                text_chars=text_chars,
                warnings=tuple(warnings),
            ),
        )


__all__ = ["DoclingPptxParser", "DoclingPptxResult", "DoclingUnavailableError"]
