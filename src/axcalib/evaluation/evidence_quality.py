"""Hash-bound evidence-quality contracts for the reviewed PPTX baseline."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from axcalib.ingest import SlideRenderManifest, sha256_file
from axcalib.schemas import (
    Assessment,
    CriterionResult,
    EvidenceDocument,
    FrozenModel,
    ParserRunManifest,
)

GOLD_SCHEMA_VERSION = "axcalib.evidence-gold/v1alpha1"
QUALITY_REPORT_SCHEMA_VERSION = "axcalib.evidence-quality-report/v1alpha1"
SLIDE_LOCATOR_PATTERN = re.compile(r"#slide=(\d+)$")


class EvidenceGoldError(ValueError):
    """Raised when a reviewed fixture drifts from its hash-bound gold contract."""


class EvidenceGoldItem(FrozenModel):
    """One reviewed slide locator without copying its source summary into the dataset."""

    evidence_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{2,127}$")
    slide_number: int = Field(ge=1)
    locator: str
    summary_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    tags: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_stable_locator(self) -> EvidenceGoldItem:
        if self.locator != f"pptx://slide/{self.slide_number}":
            raise ValueError("gold locator must use the stable pptx://slide/{number} form")
        if tuple(sorted(set(self.tags))) != self.tags:
            raise ValueError("gold item tags must be unique and sorted")
        return self


class EvidenceGoldDataset(FrozenModel):
    """Reviewed evidence anchors bound to exact source and sidecar bytes."""

    schema_version: Literal["axcalib.evidence-gold/v1alpha1"] = GOLD_SCHEMA_VERSION
    dataset_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{2,127}$")
    source_name: str
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    sidecar_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    annotation_status: Literal["manual_visual_transcription_for_offline_fixture"]
    reference_fields: tuple[str, ...] = Field(min_length=1)
    items: tuple[EvidenceGoldItem, ...] = Field(min_length=1)
    quality_claim: str

    @model_validator(mode="after")
    def validate_dataset(self) -> EvidenceGoldDataset:
        slide_numbers = [item.slide_number for item in self.items]
        if slide_numbers != sorted(set(slide_numbers)):
            raise ValueError("gold slide numbers must be unique and sorted")
        evidence_ids = [item.evidence_id for item in self.items]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("gold evidence IDs must be unique")
        expected_fields = tuple(sorted({tag for item in self.items for tag in item.tags}))
        if self.reference_fields != expected_fields:
            raise ValueError("reference_fields must equal the sorted union of item tags")
        return self


class EvidenceQualityReport(FrozenModel):
    """Deterministic evidence coverage and traceability metrics."""

    schema_version: Literal["axcalib.evidence-quality-report/v1alpha1"] = (
        QUALITY_REPORT_SCHEMA_VERSION
    )
    dataset_id: str
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    sidecar_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    render_manifest_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    slide_count: int = Field(ge=1)
    rendered_slide_count: int = Field(ge=0)
    visual_slide_count: int = Field(ge=0)
    blank_slide_count: int = Field(ge=0)
    gold_locator_count: int = Field(ge=1)
    located_gold_count: int = Field(ge=0)
    locator_recall: float = Field(ge=0.0, le=1.0)
    reference_field_count: int = Field(ge=1)
    observed_reference_field_count: int = Field(ge=0)
    reference_field_coverage: float = Field(ge=0.0, le=1.0)
    criterion_count: int = Field(ge=0)
    traceable_criterion_count: int = Field(ge=0)
    unsupported_claim_count: int = Field(ge=0)
    unresolved_evidence_reference_count: int = Field(ge=0)
    ooxml_text_slide_count: int = Field(ge=0)
    verified_sidecar_slide_count: int = Field(ge=0)
    docling_parser_id: str | None = None
    docling_page_count: int | None = Field(default=None, ge=0)
    docling_pages_with_text: int | None = Field(default=None, ge=0)
    checks: dict[str, bool]
    passed: bool
    quality_claim: str

    @model_validator(mode="after")
    def validate_pass_flag(self) -> EvidenceQualityReport:
        if not self.checks:
            raise ValueError("evidence quality report requires at least one check")
        if self.passed != all(self.checks.values()):
            raise ValueError("passed must equal the conjunction of all checks")
        return self

    @property
    def failures(self) -> tuple[str, ...]:
        """Return failed check names in stable insertion order."""

        return tuple(name for name, passed in self.checks.items() if not passed)


def load_evidence_gold(
    path: Path,
    *,
    source_path: Path,
    sidecar_path: Path,
) -> EvidenceGoldDataset:
    """Load a gold dataset and fail closed on source, sidecar, or annotation drift."""

    try:
        dataset = EvidenceGoldDataset.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise EvidenceGoldError(f"invalid evidence gold dataset: {error}") from error

    if dataset.source_name != source_path.name:
        raise EvidenceGoldError("gold source_name does not match the supplied PPTX")
    if dataset.source_sha256 != sha256_file(source_path):
        raise EvidenceGoldError("gold source_sha256 does not match the supplied PPTX")
    if dataset.sidecar_sha256 != sha256_file(sidecar_path):
        raise EvidenceGoldError("gold sidecar_sha256 does not match the supplied sidecar")

    try:
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise EvidenceGoldError(f"invalid evidence sidecar: {error}") from error
    if sidecar.get("schema_version") != "axcalib.pptx-sidecar/v1":
        raise EvidenceGoldError("gold sidecar schema_version is unsupported")
    if str(sidecar.get("source_sha256", "")).casefold() != dataset.source_sha256:
        raise EvidenceGoldError("sidecar source_sha256 does not match the gold source")
    if sidecar.get("annotation_status") != dataset.annotation_status:
        raise EvidenceGoldError("sidecar annotation_status does not match the gold dataset")

    raw_slides = sidecar.get("slides")
    if not isinstance(raw_slides, list):
        raise EvidenceGoldError("sidecar slides must be an array")
    reviewed: dict[int, tuple[str, tuple[str, ...]]] = {}
    for item in raw_slides:
        if not isinstance(item, dict) or not isinstance(item.get("slide"), int):
            raise EvidenceGoldError("sidecar reviewed slide is malformed")
        slide_number = int(item["slide"])
        if slide_number in reviewed:
            raise EvidenceGoldError("sidecar contains a duplicate reviewed slide")
        summary = " ".join(str(item.get("summary", "")).split())
        if not summary:
            raise EvidenceGoldError("sidecar reviewed summary cannot be empty")
        tags = item.get("tags", [])
        if not isinstance(tags, list):
            raise EvidenceGoldError("sidecar reviewed tags must be an array")
        reviewed[slide_number] = (
            hashlib.sha256(summary.encode("utf-8")).hexdigest(),
            tuple(sorted(str(tag) for tag in tags)),
        )

    expected = {
        item.slide_number: (item.summary_sha256, item.tags) for item in dataset.items
    }
    if reviewed != expected:
        raise EvidenceGoldError("reviewed sidecar locators, summaries, or tags drifted")
    return dataset


def evaluate_evidence_quality(
    gold: EvidenceGoldDataset,
    *,
    render_manifest: SlideRenderManifest,
    evidence: EvidenceDocument,
    criterion_results: tuple[CriterionResult, ...] = (),
    docling_manifest: ParserRunManifest | None = None,
) -> EvidenceQualityReport:
    """Measure deterministic locator coverage without claiming semantic correctness."""

    rendered = {item.slide_number: item for item in render_manifest.artifacts}
    extracted = {item.slide_number: item for item in evidence.slides}
    located = 0
    for item in gold.items:
        artifact = rendered.get(item.slide_number)
        slide = extracted.get(item.slide_number)
        if artifact is None or not artifact.visual_content_present or slide is None:
            continue
        normalized_text_hash = hashlib.sha256(
            " ".join(slide.text.split()).encode("utf-8")
        ).hexdigest()
        if (
            "sidecar" in slide.text_source
            and normalized_text_hash == item.summary_sha256
            and set(item.tags).issubset(slide.tags)
        ):
            located += 1

    observed_fields = set().union(*(set(slide.tags) for slide in evidence.slides))
    observed_reference_fields = set(gold.reference_fields).intersection(observed_fields)
    traceable = 0
    unsupported = 0
    unresolved_references = 0
    gold_slides = {item.slide_number for item in gold.items}
    non_asserting = {Assessment.INSUFFICIENT_EVIDENCE, Assessment.NOT_APPLICABLE}
    for criterion in criterion_results:
        valid_references = sum(
            _reference_is_resolved(
                reference.locator,
                reference.source,
                gold_slides,
                gold.source_sha256,
            )
            for reference in criterion.evidence_refs
        )
        unresolved_references += len(criterion.evidence_refs) - valid_references
        if valid_references or criterion.assessment in non_asserting:
            traceable += 1
        else:
            unsupported += 1

    ooxml_text_slides = sum(
        slide.text_source in {"ooxml", "ooxml+verified_sidecar"}
        for slide in evidence.slides
    )
    sidecar_slides = sum("sidecar" in slide.text_source for slide in evidence.slides)
    locator_recall = located / len(gold.items)
    field_coverage = len(observed_reference_fields) / len(gold.reference_fields)
    checks = {
        "source_hash_binding": (
            gold.source_sha256
            == render_manifest.source_sha256
            == evidence.artifact.sha256
        ),
        "full_slide_render_coverage": (
            render_manifest.rendered_slide_count
            == render_manifest.slide_count
            == len(evidence.slides)
        ),
        "reviewed_visual_locator_recall": locator_recall == 1.0,
        "reference_field_coverage": field_coverage == 1.0,
        "sidecar_slide_coverage": sidecar_slides == len(gold.items),
        "no_unreviewed_ooxml_text_claim": ooxml_text_slides == 0,
        "criterion_results_present": bool(criterion_results),
        "criterion_traceability": traceable == len(criterion_results),
        "criterion_locator_resolution": unresolved_references == 0,
    }
    if docling_manifest is not None:
        checks["docling_source_binding"] = (
            docling_manifest.source_sha256 == gold.source_sha256
        )
        checks["docling_full_page_coverage"] = (
            docling_manifest.page_count == render_manifest.slide_count
        )
        checks["docling_image_only_zero_text"] = docling_manifest.pages_with_text == 0

    return EvidenceQualityReport(
        dataset_id=gold.dataset_id,
        source_sha256=gold.source_sha256,
        sidecar_sha256=gold.sidecar_sha256,
        render_manifest_sha256=render_manifest.canonical_sha256,
        slide_count=render_manifest.slide_count,
        rendered_slide_count=render_manifest.rendered_slide_count,
        visual_slide_count=render_manifest.visual_slide_count,
        blank_slide_count=render_manifest.blank_slide_count,
        gold_locator_count=len(gold.items),
        located_gold_count=located,
        locator_recall=locator_recall,
        reference_field_count=len(gold.reference_fields),
        observed_reference_field_count=len(observed_reference_fields),
        reference_field_coverage=field_coverage,
        criterion_count=len(criterion_results),
        traceable_criterion_count=traceable,
        unsupported_claim_count=unsupported,
        unresolved_evidence_reference_count=unresolved_references,
        ooxml_text_slide_count=ooxml_text_slides,
        verified_sidecar_slide_count=sidecar_slides,
        docling_parser_id=(None if docling_manifest is None else docling_manifest.parser_id),
        docling_page_count=(None if docling_manifest is None else docling_manifest.page_count),
        docling_pages_with_text=(
            None if docling_manifest is None else docling_manifest.pages_with_text
        ),
        checks=checks,
        passed=all(checks.values()),
        quality_claim=(
            "Hash-bound locator coverage and criterion traceability only; no official "
            "rubric, semantic correctness, VLM, or retrieval-quality claim."
        ),
    )


def _reference_is_resolved(
    locator: str,
    source: str,
    gold_slides: set[int],
    source_sha256: str,
) -> bool:
    slide_match = SLIDE_LOCATOR_PATTERN.search(locator)
    if slide_match is not None:
        return int(slide_match.group(1)) in gold_slides
    if locator.startswith("report:"):
        return source == "registration_report" and len(locator) > len("report:")
    if locator.startswith("artifact:sha256="):
        digest = locator.removeprefix("artifact:sha256=")
        return source == "deterministic_hash_comparison" and digest == source_sha256
    return False


__all__ = [
    "EvidenceGoldDataset",
    "EvidenceGoldError",
    "EvidenceGoldItem",
    "EvidenceQualityReport",
    "evaluate_evidence_quality",
    "load_evidence_gold",
]
