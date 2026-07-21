"""Deterministic slide-render contracts for restricted image-only PPTX fixtures."""

from __future__ import annotations

import binascii
import hashlib
import json
import os
import posixpath
import struct
import tempfile
import zipfile
import zlib
from pathlib import Path
from typing import Literal, Protocol
from xml.etree import ElementTree as ET

from pydantic import Field, model_validator

from axcalib.ingest.pptx import (
    MAX_PACKAGE_ENTRIES,
    MAX_SLIDES,
    MAX_UNCOMPRESSED_BYTES,
    PRESENTATION_NS,
    REL_NS,
    SLIDE_PATTERN,
    PptxSourceError,
    sha256_file,
)
from axcalib.schemas import FrozenModel

DRAWING_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
OFFICE_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
RENDERER_ID = "axcalib.pptx-embedded-image/v1"
MANIFEST_NAME = "render-manifest.json"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
FULL_SLIDE_TOLERANCE = 0.005


class SlideRenderError(PptxSourceError):
    """Raised when a PPTX cannot be rendered by the restricted local adapter."""


class SlideRenderArtifact(FrozenModel):
    """One content-addressed PNG derived from a specific PPTX slide."""

    slide_number: int = Field(ge=1)
    slide_part_uri: str
    source_kind: Literal["embedded_image", "blank"]
    source_part_uri: str | None = None
    artifact_uri: str
    image_format: Literal["png"] = "png"
    image_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    byte_size: int = Field(gt=0)
    width_px: int = Field(gt=0)
    height_px: int = Field(gt=0)
    visual_content_present: bool

    @model_validator(mode="after")
    def validate_source_kind(self) -> SlideRenderArtifact:
        if self.source_kind == "embedded_image":
            if self.source_part_uri is None or not self.visual_content_present:
                raise ValueError("embedded image artifacts require a visual source part")
        elif self.source_part_uri is not None or self.visual_content_present:
            raise ValueError("blank artifacts cannot claim a visual source part")
        return self


class SlideRenderManifest(FrozenModel):
    """Stable render provenance without timestamps or environment-specific paths."""

    schema_version: Literal["axcalib.slide-render-manifest/v1alpha1"] = (
        "axcalib.slide-render-manifest/v1alpha1"
    )
    renderer_id: Literal["axcalib.pptx-embedded-image/v1"] = RENDERER_ID
    source_name: str
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    slide_count: int = Field(ge=1)
    rendered_slide_count: int = Field(ge=1)
    visual_slide_count: int = Field(ge=0)
    blank_slide_count: int = Field(ge=0)
    artifacts: tuple[SlideRenderArtifact, ...] = Field(min_length=1)
    manifest_uri: str = MANIFEST_NAME
    limitations: tuple[str, ...] = (
        "Only a single uncropped near-full-slide embedded PNG or a truly blank slide is supported.",
        "This adapter extracts reviewed visual pixels; it does not understand slide semantics.",
    )

    @model_validator(mode="after")
    def validate_counts(self) -> SlideRenderManifest:
        slide_numbers = [item.slide_number for item in self.artifacts]
        if slide_numbers != list(range(1, self.slide_count + 1)):
            raise ValueError("render artifacts must cover every slide in order")
        if self.rendered_slide_count != len(self.artifacts):
            raise ValueError("rendered_slide_count must equal artifact count")
        visual_count = sum(item.visual_content_present for item in self.artifacts)
        blank_count = sum(not item.visual_content_present for item in self.artifacts)
        if self.visual_slide_count != visual_count:
            raise ValueError("visual_slide_count does not match artifacts")
        if self.blank_slide_count != blank_count:
            raise ValueError("blank_slide_count does not match artifacts")
        return self

    @property
    def canonical_sha256(self) -> str:
        """Hash the stable JSON representation of the render manifest."""

        payload = json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


class SlideRenderer(Protocol):
    """Port implemented by local or future approved slide-render adapters."""

    renderer_id: str

    def render(self, source: Path, output_dir: Path) -> SlideRenderManifest:
        """Render one presentation into content-addressed slide artifacts."""

        ...


class EmbeddedImagePptxRenderer:
    """Extract full-slide embedded PNGs and synthesize deterministic blank slides.

    This is intentionally not a general PowerPoint renderer. It fails closed when a slide
    contains text, multiple pictures, crop/rotation, charts, or other composed content.
    """

    renderer_id = RENDERER_ID

    def render(self, source: Path, output_dir: Path) -> SlideRenderManifest:
        """Render a restricted image-only PPTX without Office, network, or model calls."""

        resolved = source.resolve()
        if resolved.suffix.casefold() != ".pptx" or not resolved.is_file():
            raise SlideRenderError("embedded-image renderer requires an existing .pptx file")
        destination = output_dir.resolve()
        destination.mkdir(parents=True, exist_ok=True)

        try:
            package = zipfile.ZipFile(resolved)
        except (OSError, zipfile.BadZipFile) as error:
            raise SlideRenderError(f"invalid PPTX package: {error}") from error

        with package:
            self._validate_package(package)
            slide_width, slide_height = self._slide_size(package)
            slide_parts = self._slide_parts(package)
            prepared: list[tuple[int, str, str | None, bytes | None]] = []
            dimensions: set[tuple[int, int]] = set()
            for slide_number, slide_part in slide_parts:
                source_part, image = self._extract_slide(
                    package,
                    slide_number=slide_number,
                    slide_part=slide_part,
                    slide_width=slide_width,
                    slide_height=slide_height,
                )
                if image is not None:
                    dimensions.add(_png_dimensions(image))
                prepared.append((slide_number, slide_part, source_part, image))

        if not dimensions:
            raise SlideRenderError("an all-blank presentation has no deterministic pixel profile")
        if len(dimensions) != 1:
            raise SlideRenderError("embedded image dimensions must be consistent across slides")
        width_px, height_px = next(iter(dimensions))
        blank_png = _blank_png(width_px, height_px)

        artifacts: list[SlideRenderArtifact] = []
        for slide_number, slide_part, source_part, embedded in prepared:
            pixels = embedded if embedded is not None else blank_png
            source_kind: Literal["embedded_image", "blank"] = (
                "embedded_image" if embedded is not None else "blank"
            )
            relative_uri = f"slides/slide-{slide_number:04d}.png"
            target = destination / Path(relative_uri)
            _atomic_write_bytes(target, pixels)
            artifacts.append(
                SlideRenderArtifact(
                    slide_number=slide_number,
                    slide_part_uri=slide_part,
                    source_kind=source_kind,
                    source_part_uri=source_part,
                    artifact_uri=relative_uri,
                    image_sha256=hashlib.sha256(pixels).hexdigest(),
                    byte_size=len(pixels),
                    width_px=width_px,
                    height_px=height_px,
                    visual_content_present=embedded is not None,
                )
            )

        visual_count = sum(item.visual_content_present for item in artifacts)
        manifest = SlideRenderManifest(
            source_name=resolved.name,
            source_sha256=sha256_file(resolved),
            slide_count=len(artifacts),
            rendered_slide_count=len(artifacts),
            visual_slide_count=visual_count,
            blank_slide_count=len(artifacts) - visual_count,
            artifacts=tuple(artifacts),
        )
        manifest_bytes = (
            json.dumps(
                manifest.model_dump(mode="json"),
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        ).encode("utf-8")
        _atomic_write_bytes(destination / MANIFEST_NAME, manifest_bytes)
        return manifest

    @staticmethod
    def _validate_package(package: zipfile.ZipFile) -> None:
        infos = package.infolist()
        if len(infos) > MAX_PACKAGE_ENTRIES:
            raise SlideRenderError("PPTX package has too many entries")
        if sum(info.file_size for info in infos) > MAX_UNCOMPRESSED_BYTES:
            raise SlideRenderError("PPTX uncompressed package exceeds the safety limit")
        if any("vbaproject" in info.filename.casefold() for info in infos):
            raise SlideRenderError("macro-enabled PPTX content is not allowed")

    @staticmethod
    def _slide_size(package: zipfile.ZipFile) -> tuple[int, int]:
        try:
            root = ET.fromstring(package.read("ppt/presentation.xml"))
        except (KeyError, ET.ParseError) as error:
            raise SlideRenderError("PPTX presentation metadata is invalid") from error
        size = root.find(f".//{{{PRESENTATION_NS}}}sldSz")
        if size is None:
            raise SlideRenderError("PPTX slide size is missing")
        try:
            width = int(size.attrib["cx"])
            height = int(size.attrib["cy"])
        except (KeyError, ValueError) as error:
            raise SlideRenderError("PPTX slide size is invalid") from error
        if width <= 0 or height <= 0:
            raise SlideRenderError("PPTX slide size must be positive")
        return width, height

    @staticmethod
    def _slide_parts(package: zipfile.ZipFile) -> list[tuple[int, str]]:
        parts = sorted(
            (
                (int(match.group(1)), name)
                for name in package.namelist()
                if (match := SLIDE_PATTERN.match(name)) is not None
            ),
            key=lambda item: item[0],
        )
        if not parts or len(parts) > MAX_SLIDES:
            raise SlideRenderError("PPTX slide count is outside the supported range")
        numbers = [number for number, _ in parts]
        if numbers != list(range(1, len(parts) + 1)):
            raise SlideRenderError("PPTX slide parts must be contiguous for the reference renderer")
        return parts

    def _extract_slide(
        self,
        package: zipfile.ZipFile,
        *,
        slide_number: int,
        slide_part: str,
        slide_width: int,
        slide_height: int,
    ) -> tuple[str | None, bytes | None]:
        try:
            root = ET.fromstring(package.read(slide_part))
        except (KeyError, ET.ParseError) as error:
            raise SlideRenderError(f"slide {slide_number} XML is invalid") from error
        shape_tree = root.find(
            f".//{{{PRESENTATION_NS}}}cSld/{{{PRESENTATION_NS}}}spTree"
        )
        if shape_tree is None:
            raise SlideRenderError(f"slide {slide_number} shape tree is missing")
        structural_tags = {
            f"{{{PRESENTATION_NS}}}nvGrpSpPr",
            f"{{{PRESENTATION_NS}}}grpSpPr",
        }
        content = [child for child in shape_tree if child.tag not in structural_tags]
        pictures = [
            child for child in content if child.tag == f"{{{PRESENTATION_NS}}}pic"
        ]
        if not pictures:
            if content:
                raise SlideRenderError(
                    f"slide {slide_number} contains composed content, not a true blank slide"
                )
            return None, None
        if len(pictures) != 1 or len(content) != 1:
            raise SlideRenderError(
                f"slide {slide_number} is outside the single embedded-image contract"
            )
        picture = pictures[0]
        self._validate_picture_geometry(
            picture,
            slide_number=slide_number,
            slide_width=slide_width,
            slide_height=slide_height,
        )
        crop = picture.find(f".//{{{DRAWING_NS}}}srcRect")
        if crop is not None and any(int(value) != 0 for value in crop.attrib.values()):
            raise SlideRenderError(f"slide {slide_number} contains a cropped picture")
        blip = picture.find(f".//{{{DRAWING_NS}}}blip")
        relationship_id = None if blip is None else blip.attrib.get(f"{{{OFFICE_REL_NS}}}embed")
        if not relationship_id:
            raise SlideRenderError(f"slide {slide_number} picture relationship is missing")
        source_part = self._relationship_target(
            package,
            slide_part=slide_part,
            relationship_id=relationship_id,
        )
        try:
            image = package.read(source_part)
        except KeyError as error:
            raise SlideRenderError(f"slide {slide_number} image part is missing") from error
        _png_dimensions(image)
        return source_part, image

    @staticmethod
    def _validate_picture_geometry(
        picture: ET.Element,
        *,
        slide_number: int,
        slide_width: int,
        slide_height: int,
    ) -> None:
        transform = picture.find(
            f".//{{{PRESENTATION_NS}}}spPr/{{{DRAWING_NS}}}xfrm"
        )
        if transform is None:
            raise SlideRenderError(f"slide {slide_number} picture transform is missing")
        if any(transform.attrib.get(name) not in (None, "0") for name in ("rot", "flipH", "flipV")):
            raise SlideRenderError(f"slide {slide_number} picture rotation/flip is unsupported")
        offset = transform.find(f"{{{DRAWING_NS}}}off")
        extent = transform.find(f"{{{DRAWING_NS}}}ext")
        if offset is None or extent is None:
            raise SlideRenderError(f"slide {slide_number} picture geometry is incomplete")
        try:
            left = int(offset.attrib["x"])
            top = int(offset.attrib["y"])
            width = int(extent.attrib["cx"])
            height = int(extent.attrib["cy"])
        except (KeyError, ValueError) as error:
            raise SlideRenderError(f"slide {slide_number} picture geometry is invalid") from error
        ratios = (
            abs(left) / slide_width,
            abs(top) / slide_height,
            abs(width - slide_width) / slide_width,
            abs(height - slide_height) / slide_height,
        )
        if any(ratio > FULL_SLIDE_TOLERANCE for ratio in ratios):
            raise SlideRenderError(f"slide {slide_number} picture does not cover the slide")

    @staticmethod
    def _relationship_target(
        package: zipfile.ZipFile,
        *,
        slide_part: str,
        relationship_id: str,
    ) -> str:
        slide_name = posixpath.basename(slide_part)
        relationships_part = posixpath.join(
            posixpath.dirname(slide_part),
            "_rels",
            f"{slide_name}.rels",
        )
        try:
            root = ET.fromstring(package.read(relationships_part))
        except (KeyError, ET.ParseError) as error:
            raise SlideRenderError("slide relationship XML is invalid") from error
        for relationship in root.findall(f".//{{{REL_NS}}}Relationship"):
            if relationship.attrib.get("Id") != relationship_id:
                continue
            if relationship.attrib.get("TargetMode") == "External":
                raise SlideRenderError("external picture relationships are not allowed")
            if not relationship.attrib.get("Type", "").endswith("/image"):
                raise SlideRenderError("picture relationship must use the OOXML image type")
            target = relationship.attrib.get("Target", "")
            normalized = posixpath.normpath(
                posixpath.join(posixpath.dirname(slide_part), target)
            )
            if not normalized.startswith("ppt/media/") or normalized not in package.namelist():
                raise SlideRenderError("picture relationship leaves the PPTX media directory")
            return normalized
        raise SlideRenderError("picture relationship target is missing")


def _png_dimensions(payload: bytes) -> tuple[int, int]:
    if len(payload) < 24 or not payload.startswith(PNG_SIGNATURE):
        raise SlideRenderError("the embedded full-slide image must be PNG")
    if payload[12:16] != b"IHDR":
        raise SlideRenderError("PNG IHDR is missing")
    width, height = struct.unpack(">II", payload[16:24])
    if width <= 0 or height <= 0:
        raise SlideRenderError("PNG dimensions must be positive")
    return width, height


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    checksum = binascii.crc32(kind + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", checksum)


def _blank_png(width: int, height: int) -> bytes:
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    row = b"\x00" + (b"\xff" * width * 3)
    pixels = zlib.compress(row * height, level=9)
    return PNG_SIGNATURE + _png_chunk(b"IHDR", header) + _png_chunk(
        b"IDAT", pixels
    ) + _png_chunk(b"IEND", b"")


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


__all__ = [
    "EmbeddedImagePptxRenderer",
    "SlideRenderArtifact",
    "SlideRenderError",
    "SlideRenderManifest",
    "SlideRenderer",
]
