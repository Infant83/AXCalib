"""Safe, dependency-light PPTX evidence extraction for the offline MVP."""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from axcalib.schemas import ArtifactRef, EvidenceDocument, SlideEvidence

PPTX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
PARSER_ID = "axcalib.pptx-ooxml/v1"
SIDECAR_SCHEMA = "axcalib.pptx-sidecar/v1"
MAX_SLIDES = 64
MAX_PACKAGE_ENTRIES = 5000
MAX_UNCOMPRESSED_BYTES = 250 * 1024 * 1024

DRAWING_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
PRESENTATION_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
SLIDE_PATTERN = re.compile(r"^ppt/slides/slide(\d+)\.xml$")

TAG_KEYWORDS: dict[str, tuple[str, ...]] = {
    "problem": ("문제", "한계", "병목", "비용", "어려움"),
    "goal": ("목표", "목적", "최적화", "제안"),
    "scope": ("범위", "단계", "프레임워크", "워크플로"),
    "method": ("방법", "모델", "학습", "알고리즘", "qubo", "surrogate"),
    "roadmap": ("로드맵", "phase", "단계", "향후"),
    "risk": ("리스크", "위험", "한계", "주의"),
    "data": ("데이터", "dataset", "샘플"),
    "security": ("보안", "개인정보", "접근등급", "외부전송"),
    "role": ("담당", "역할", "책임", "mentor", "멘토"),
    "resource": ("자원", "예산", "gpu", "인력"),
    "kpi_plan": ("kpi", "지표", "baseline", "target", "측정"),
    "result": ("결과", "달성", "개선", "완료", "성과"),
    "deliverable": ("산출물", "배포", "코드", "리포트", "데모"),
    "validation_plan": ("검증", "평가", "실험", "비교"),
    "limitation": ("한계", "제약", "불확실"),
    "change": ("변경", "수정", "범위조정"),
    "reproducibility": ("재현", "버전", "hash", "로그", "테스트"),
}


class PptxSourceError(ValueError):
    """Raised when the source package or its sidecar is unsafe or inconsistent."""


def sha256_file(path: Path) -> str:
    """Hash a file without loading it entirely into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def infer_tags(text: str) -> tuple[str, ...]:
    """Infer broad evidence tags; this does not perform semantic scoring."""

    normalized = text.casefold()
    tags = {
        tag
        for tag, keywords in TAG_KEYWORDS.items()
        if any(keyword.casefold() in normalized for keyword in keywords)
    }
    if "kpi_plan" in tags and re.search(r"\d", normalized):
        tags.add("quantitative_target")
    return tuple(sorted(tags))


class PptxEvidenceExtractor:
    """Extract OOXML text and verified sidecar annotations with slide locators."""

    def artifact_ref(
        self,
        path: Path,
        *,
        role: str,
        sidecar_path: Path | None = None,
    ) -> ArtifactRef:
        """Create a content-addressed artifact reference."""

        resolved = path.resolve()
        if resolved.suffix.casefold() != ".pptx":
            raise PptxSourceError("only .pptx input is supported by the offline parser")
        if not resolved.is_file():
            raise PptxSourceError(f"PPTX source does not exist: {resolved}")
        digest = sha256_file(resolved)
        metadata: dict[str, str] = {"parser_id": PARSER_ID}
        if sidecar_path is not None:
            resolved_sidecar = sidecar_path.resolve()
            if not resolved_sidecar.is_file():
                raise PptxSourceError(f"PPTX sidecar does not exist: {resolved_sidecar}")
            metadata["sidecar_uri"] = str(resolved_sidecar)
            metadata["sidecar_sha256"] = sha256_file(resolved_sidecar)
            metadata["sidecar_byte_size"] = str(resolved_sidecar.stat().st_size)
            metadata["sidecar_media_type"] = "application/json"
        return ArtifactRef(
            artifact_id=f"artifact-{role}-{digest[:16]}",
            role=role,
            uri=str(resolved),
            media_type=PPTX_MEDIA_TYPE,
            sha256=digest,
            byte_size=resolved.stat().st_size,
            metadata=metadata,
        )

    def extract(
        self,
        path: Path,
        *,
        role: str,
        sidecar_path: Path | None = None,
    ) -> EvidenceDocument:
        """Parse one PPTX without executing content or following external links."""

        artifact = self.artifact_ref(path, role=role, sidecar_path=sidecar_path)
        sidecar = self._load_sidecar(sidecar_path, artifact.sha256)
        sidecar_slides = {int(item["slide"]): item for item in sidecar["slides"]}
        warnings: list[str] = []
        slides: list[SlideEvidence] = []

        try:
            package = zipfile.ZipFile(path)
        except (OSError, zipfile.BadZipFile) as error:
            raise PptxSourceError(f"invalid PPTX package: {error}") from error

        with package:
            infos = package.infolist()
            if len(infos) > MAX_PACKAGE_ENTRIES:
                raise PptxSourceError("PPTX package has too many entries")
            if sum(info.file_size for info in infos) > MAX_UNCOMPRESSED_BYTES:
                raise PptxSourceError("PPTX uncompressed package exceeds the offline safety limit")
            names = set(package.namelist())
            if any("vbaproject" in name.casefold() for name in names):
                raise PptxSourceError("macro-enabled PPTX content is not allowed")
            slide_names = sorted(
                (
                    (int(match.group(1)), name)
                    for name in names
                    if (match := SLIDE_PATTERN.match(name)) is not None
                ),
                key=lambda item: item[0],
            )
            if not slide_names:
                raise PptxSourceError("PPTX contains no slides")
            if len(slide_names) > MAX_SLIDES:
                raise PptxSourceError(f"PPTX contains more than {MAX_SLIDES} slides")

            for slide_number, slide_name in slide_names:
                try:
                    root = ET.fromstring(package.read(slide_name))
                except ET.ParseError as error:
                    raise PptxSourceError(
                        f"slide {slide_number} contains invalid XML: {error}"
                    ) from error
                chunks = [
                    " ".join((node.text or "").split())
                    for node in root.findall(f".//{{{DRAWING_NS}}}t")
                ]
                ooxml_text = " ".join(chunk for chunk in chunks if chunk)
                image_count = len(root.findall(f".//{{{PRESENTATION_NS}}}pic"))
                annotation = sidecar_slides.get(slide_number, {})
                summary = " ".join(str(annotation.get("summary", "")).split())
                annotated_tags = tuple(str(tag) for tag in annotation.get("tags", []))

                if ooxml_text and summary:
                    text = f"{ooxml_text}\n[검토 sidecar] {summary}"
                    text_source = "ooxml+verified_sidecar"
                elif ooxml_text:
                    text = ooxml_text
                    text_source = "ooxml"
                elif summary:
                    text = summary
                    text_source = "verified_sidecar"
                else:
                    text = ""
                    text_source = "none"
                # Sidecar tags are review annotations. Do not re-infer semantic tags from a
                # summary: words such as "결과" or "역할" can describe a method, not evidence
                # of an observed result or an assigned owner.
                tags = tuple(
                    sorted(set(infer_tags(ooxml_text)) | set(annotated_tags))
                )
                is_blank = not text and image_count == 0
                if image_count and not text:
                    warnings.append(
                        f"slide {slide_number}: image-only evidence has no verified text"
                    )
                slides.append(
                    SlideEvidence(
                        slide_number=slide_number,
                        text=text,
                        tags=tags,
                        text_source=text_source,
                        image_count=image_count,
                        is_blank=is_blank,
                    )
                )

            for name in names:
                if not name.endswith(".rels"):
                    continue
                try:
                    root = ET.fromstring(package.read(name))
                except ET.ParseError:
                    continue
                if any(
                    node.attrib.get("TargetMode") == "External"
                    for node in root.findall(f".//{{{REL_NS}}}Relationship")
                ):
                    warnings.append("external relationship present but not fetched")
                    break

        return EvidenceDocument(
            artifact=artifact,
            slides=tuple(slides),
            warnings=tuple(warnings),
            parser_id=PARSER_ID,
        )

    @staticmethod
    def _load_sidecar(path: Path | None, source_sha256: str) -> dict[str, Any]:
        if path is None:
            return {"slides": []}
        resolved = path.resolve()
        try:
            data = json.loads(resolved.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise PptxSourceError(f"invalid PPTX sidecar: {error}") from error
        if data.get("schema_version") != SIDECAR_SCHEMA:
            raise PptxSourceError(f"sidecar schema_version must be {SIDECAR_SCHEMA}")
        if str(data.get("source_sha256", "")).casefold() != source_sha256:
            raise PptxSourceError("sidecar source_sha256 does not match the PPTX")
        slides = data.get("slides")
        if not isinstance(slides, list):
            raise PptxSourceError("sidecar slides must be an array")
        seen_slides: set[int] = set()
        for item in slides:
            if not isinstance(item, dict) or not isinstance(item.get("slide"), int):
                raise PptxSourceError("each sidecar slide must have an integer slide number")
            slide_number = item["slide"]
            if slide_number < 1 or slide_number > MAX_SLIDES:
                raise PptxSourceError("sidecar slide number is outside the allowed range")
            if slide_number in seen_slides:
                raise PptxSourceError("sidecar contains a duplicate slide number")
            seen_slides.add(slide_number)
            if not isinstance(item.get("tags", []), list):
                raise PptxSourceError("sidecar slide tags must be an array")
        return {"slides": slides}
