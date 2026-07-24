"""Owner-approved, hash-bound semantic gold benchmark contracts."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, model_validator
from ruamel.yaml import YAML

from axcalib.policies import (
    ReviewPolicyPack,
    ReviewProfileRegistry,
    canonical_policy_sha256,
)
from axcalib.schemas import (
    AgentRecommendation,
    Assessment,
    EvaluationReport,
    FrozenModel,
    ReviewPolicyStatus,
    ReviewStage,
)
from axcalib.schemas.domain import utc_now

BENCHMARK_MANIFEST_SCHEMA_VERSION = "axcalib.gold-benchmark-manifest/v1alpha1"
GOLD_CASE_SCHEMA_VERSION = "axcalib.gold-case-label/v1alpha1"
OWNER_APPROVAL_SCHEMA_VERSION = "axcalib.evaluation-owner-approval/v1alpha1"
BENCHMARK_REPORT_SCHEMA_VERSION = "axcalib.gold-benchmark-report/v1alpha1"

_ID_PATTERN = r"^[a-z0-9][a-z0-9._-]{2,127}$"
_SEMVER_PATTERN = r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$"
_SHA256_PATTERN = r"^[a-f0-9]{64}$"
_CRITERION_PATTERN = r"^[A-Z][A-Z0-9_-]{2,127}$"
_STABLE_SLIDE_LOCATOR = re.compile(r"^pptx://slide/([1-9][0-9]*)$")
_REPORT_LOCATOR = re.compile(r"^report:[A-Za-z0-9][A-Za-z0-9._:-]{1,255}$")
_ARTIFACT_LOCATOR = re.compile(r"^artifact:sha256=[a-f0-9]{64}$")
_REPORT_SLIDE_FRAGMENT = re.compile(r"#slide=([1-9][0-9]*)$")

_MAX_MANIFEST_BYTES = 1_000_000
_MAX_POLICY_BYTES = 2_000_000
_MAX_APPROVAL_BYTES = 1_000_000
_MAX_LABELS_BYTES = 20_000_000
_MAX_LABEL_LINE_BYTES = 200_000


class BenchmarkStatus(StrEnum):
    """Lifecycle of a semantic benchmark package."""

    DRAFT = "draft"
    OFFLINE_REFERENCE = "offline_reference"
    APPROVED = "approved"
    RETIRED = "retired"


class BenchmarkSplit(StrEnum):
    """Data split controlled by the Evaluation Owner."""

    DEVELOPMENT = "development"
    VALIDATION = "validation"
    TEST = "test"


class GoldLabelStatus(StrEnum):
    """Human review maturity of one gold label."""

    SINGLE_REVIEW = "single_review"
    DOUBLE_REVIEW = "double_review"
    ADJUDICATED = "adjudicated"


class OwnerDecision(StrEnum):
    """Explicit package decision retained in the approval Markdown."""

    PENDING = "pending"
    APPROVE = "approve"
    REJECT = "reject"


class BenchmarkPolicyFile(FrozenModel):
    """Review policy file and canonical policy identity."""

    path: str = Field(min_length=1, max_length=300)
    policy_id: str = Field(pattern=_ID_PATTERN)
    version: str = Field(pattern=_SEMVER_PATTERN)
    canonical_sha256: str = Field(pattern=_SHA256_PATTERN)


class BenchmarkLabelsFile(FrozenModel):
    """Hash-bound JSONL label file metadata."""

    path: str = Field(min_length=1, max_length=300)
    sha256: str = Field(pattern=_SHA256_PATTERN)
    record_count: int = Field(ge=1)


class BenchmarkApprovalFile(FrozenModel):
    """Hash-bound human-readable approval record."""

    path: str = Field(min_length=1, max_length=300)
    sha256: str = Field(pattern=_SHA256_PATTERN)


class BenchmarkThresholds(FrozenModel):
    """Owner-selected acceptance thresholds; code does not invent their values."""

    criterion_assessment_accuracy_min: float = Field(ge=0.0, le=1.0)
    recommendation_accuracy_min: float = Field(ge=0.0, le=1.0)
    evidence_locator_precision_min: float = Field(ge=0.0, le=1.0)
    evidence_locator_recall_min: float = Field(ge=0.0, le=1.0)
    insufficient_evidence_recall_min: float = Field(ge=0.0, le=1.0)
    required_risk_flag_recall_min: float = Field(ge=0.0, le=1.0)
    human_pre_adjudication_agreement_min: float = Field(ge=0.0, le=1.0)
    dangerous_positive_rate_max: float = Field(ge=0.0, le=1.0)
    unsupported_claim_rate_max: float = Field(ge=0.0, le=1.0)


class GoldBenchmarkManifest(FrozenModel):
    """Manifest binding policy, labels, approval record, and thresholds."""

    schema_version: Literal["axcalib.gold-benchmark-manifest/v1alpha1"] = (
        BENCHMARK_MANIFEST_SCHEMA_VERSION
    )
    benchmark_id: str = Field(pattern=_ID_PATTERN)
    version: str = Field(pattern=_SEMVER_PATTERN)
    status: BenchmarkStatus
    owner_ref: str = Field(min_length=1, max_length=200)
    approval_ref: str | None = Field(default=None, max_length=300)
    description: str = Field(min_length=1, max_length=2000)
    evaluation_split: BenchmarkSplit
    policy: BenchmarkPolicyFile
    labels: BenchmarkLabelsFile
    approval: BenchmarkApprovalFile
    thresholds: BenchmarkThresholds | None = None

    @model_validator(mode="after")
    def validate_approval_contract(self) -> GoldBenchmarkManifest:
        if self.status is BenchmarkStatus.APPROVED:
            if not self.approval_ref:
                raise ValueError("approved benchmark requires approval_ref")
            if self.thresholds is None:
                raise ValueError("approved benchmark requires owner-selected thresholds")
            if self.evaluation_split is not BenchmarkSplit.TEST:
                raise ValueError("approved benchmark requires evaluation_split=test")
        return self

    @property
    def selector(self) -> str:
        """Return the immutable benchmark selector."""

        return f"{self.benchmark_id}@{self.version}"


class GoldReviewerVote(FrozenModel):
    """One pseudonymous pre-adjudication assessment."""

    reviewer_ref: str = Field(min_length=1, max_length=200)
    assessment: Assessment


class GoldCriterionLabel(FrozenModel):
    """One adjudicated expected criterion finding."""

    criterion_id: str = Field(pattern=_CRITERION_PATTERN)
    expected_assessment: Assessment
    acceptable_evidence_locators: tuple[str, ...] = ()
    required_risk_flags: tuple[str, ...] = ()
    reviewer_votes: tuple[GoldReviewerVote, ...] = ()
    rationale: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def validate_evidence_contract(self) -> GoldCriterionLabel:
        locators = self.acceptable_evidence_locators
        if len(locators) != len(set(locators)):
            raise ValueError("acceptable_evidence_locators must be unique")
        for locator in locators:
            if not _is_stable_gold_locator(locator):
                raise ValueError(f"gold locator is not stable or allowlisted: {locator}")
        if tuple(sorted(set(self.required_risk_flags))) != self.required_risk_flags:
            raise ValueError("required_risk_flags must be unique and sorted")
        vote_refs = [vote.reviewer_ref for vote in self.reviewer_votes]
        if len(vote_refs) != len(set(vote_refs)):
            raise ValueError("reviewer_votes must contain unique reviewer_ref values")
        asserting = {
            Assessment.MET,
            Assessment.PARTIALLY_MET,
            Assessment.NOT_MET,
        }
        if self.expected_assessment in asserting and not locators:
            raise ValueError(
                "met/partially_met/not_met gold labels require at least one stable locator"
            )
        return self


class GoldCaseLabel(FrozenModel):
    """One project-stage gold label, independent from a final human certification."""

    schema_version: Literal["axcalib.gold-case-label/v1alpha1"] = GOLD_CASE_SCHEMA_VERSION
    label_id: str = Field(pattern=_ID_PATTERN)
    project_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
    stage: ReviewStage
    split: BenchmarkSplit
    snapshot_sha256: str = Field(pattern=_SHA256_PATTERN)
    artifact_sha256: str = Field(pattern=_SHA256_PATTERN)
    expected_recommendation: AgentRecommendation
    criteria: tuple[GoldCriterionLabel, ...] = Field(min_length=1)
    label_status: GoldLabelStatus
    reviewer_refs: tuple[str, ...] = Field(min_length=1)
    adjudication_ref: str | None = Field(default=None, max_length=300)
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_label(self) -> GoldCaseLabel:
        criterion_ids = [item.criterion_id for item in self.criteria]
        if len(criterion_ids) != len(set(criterion_ids)):
            raise ValueError("gold case criterion_id values must be unique")
        if tuple(sorted(set(self.reviewer_refs))) != self.reviewer_refs:
            raise ValueError("reviewer_refs must be unique and sorted")
        if self.label_status is GoldLabelStatus.SINGLE_REVIEW:
            if len(self.reviewer_refs) != 1 or self.adjudication_ref:
                raise ValueError("single_review requires one reviewer and no adjudication_ref")
        elif len(self.reviewer_refs) < 2:
            raise ValueError("double_review/adjudicated labels require two reviewers")
        if self.label_status is GoldLabelStatus.ADJUDICATED and not self.adjudication_ref:
            raise ValueError("adjudicated label requires adjudication_ref")
        allowed = _recommendations_for_stage(self.stage)
        if self.expected_recommendation not in allowed:
            raise ValueError(
                f"recommendation is invalid for {self.stage.value}: "
                f"{self.expected_recommendation.value}"
            )
        return self

    @property
    def key(self) -> tuple[str, ReviewStage]:
        """Return the report lookup key."""

        return self.project_id, self.stage


class EvaluationOwnerApproval(FrozenModel):
    """Structured frontmatter extracted from the owner approval Markdown."""

    schema_version: Literal["axcalib.evaluation-owner-approval/v1alpha1"] = (
        OWNER_APPROVAL_SCHEMA_VERSION
    )
    benchmark_id: str = Field(pattern=_ID_PATTERN)
    benchmark_version: str = Field(pattern=_SEMVER_PATTERN)
    status: BenchmarkStatus
    decision: OwnerDecision
    owner_ref: str = Field(min_length=1, max_length=200)
    approval_ref: str | None = Field(default=None, max_length=300)
    approved_at: datetime | None = None
    policy_id: str = Field(pattern=_ID_PATTERN)
    policy_version: str = Field(pattern=_SEMVER_PATTERN)
    policy_sha256: str = Field(pattern=_SHA256_PATTERN)
    labels_sha256: str = Field(pattern=_SHA256_PATTERN)
    data_classification: Literal["synthetic", "deidentified", "internal_restricted"]
    external_model_allowed: bool

    @model_validator(mode="after")
    def validate_decision(self) -> EvaluationOwnerApproval:
        if self.status is BenchmarkStatus.APPROVED:
            if self.decision is not OwnerDecision.APPROVE:
                raise ValueError("approved owner record requires decision=approve")
            if not self.approval_ref or self.approved_at is None:
                raise ValueError("approved owner record requires approval_ref and approved_at")
        if self.status is BenchmarkStatus.DRAFT and self.decision is not OwnerDecision.PENDING:
            raise ValueError("draft owner record requires decision=pending")
        return self


class GoldBenchmarkPackage(FrozenModel):
    """Fully verified owner package ready for validation or evaluation."""

    package_root: str
    manifest_sha256: str = Field(pattern=_SHA256_PATTERN)
    manifest: GoldBenchmarkManifest
    policy: ReviewPolicyPack
    labels: tuple[GoldCaseLabel, ...]
    approval: EvaluationOwnerApproval


class PredictedCriterion(FrozenModel):
    """Normalized report criterion used for benchmark comparison."""

    criterion_id: str = Field(pattern=_CRITERION_PATTERN)
    assessment: Assessment
    evidence_locators: tuple[str, ...] = ()
    risk_flags: tuple[str, ...] = ()


class BenchmarkPrediction(FrozenModel):
    """Secret-free prediction projection from one AXCalib evaluation report."""

    project_id: str
    stage: ReviewStage
    snapshot_sha256: str = Field(pattern=_SHA256_PATTERN)
    artifact_sha256: str = Field(pattern=_SHA256_PATTERN)
    policy_id: str
    policy_version: str
    policy_sha256: str = Field(pattern=_SHA256_PATTERN)
    recommendation: AgentRecommendation
    criteria: tuple[PredictedCriterion, ...]
    model: str | None = None
    live_model: bool = False

    @property
    def key(self) -> tuple[str, ReviewStage]:
        """Return the gold-label lookup key."""

        return self.project_id, self.stage


class GoldBenchmarkQualityReport(FrozenModel):
    """Deterministic comparison against approved human labels."""

    schema_version: Literal["axcalib.gold-benchmark-report/v1alpha1"] = (
        BENCHMARK_REPORT_SCHEMA_VERSION
    )
    benchmark_id: str
    benchmark_version: str
    benchmark_status: BenchmarkStatus
    benchmark_split: BenchmarkSplit
    manifest_sha256: str = Field(pattern=_SHA256_PATTERN)
    policy_id: str
    policy_version: str
    policy_sha256: str = Field(pattern=_SHA256_PATTERN)
    generated_at: datetime = Field(default_factory=utc_now)
    case_count: int = Field(ge=1)
    registration_case_count: int = Field(ge=0)
    completion_case_count: int = Field(ge=0)
    criterion_count: int = Field(ge=1)
    gold_evidence_locator_count: int = Field(ge=0)
    predicted_evidence_locator_count: int = Field(ge=0)
    expected_insufficient_evidence_count: int = Field(ge=0)
    required_risk_flag_count: int = Field(ge=0)
    human_vote_pair_count: int = Field(ge=0)
    negative_case_count: int = Field(ge=0)
    asserting_prediction_count: int = Field(ge=0)
    criterion_assessment_accuracy: float = Field(ge=0.0, le=1.0)
    recommendation_accuracy: float = Field(ge=0.0, le=1.0)
    evidence_locator_precision: float = Field(ge=0.0, le=1.0)
    evidence_locator_recall: float = Field(ge=0.0, le=1.0)
    insufficient_evidence_recall: float = Field(ge=0.0, le=1.0)
    required_risk_flag_recall: float = Field(ge=0.0, le=1.0)
    human_pre_adjudication_agreement: float = Field(ge=0.0, le=1.0)
    dangerous_positive_count: int = Field(ge=0)
    dangerous_positive_rate: float = Field(ge=0.0, le=1.0)
    unsupported_claim_count: int = Field(ge=0)
    unsupported_claim_rate: float = Field(ge=0.0, le=1.0)
    live_model_report_count: int = Field(ge=0)
    models: tuple[str, ...] = ()
    threshold_checks: dict[str, bool]
    official_quality_decision: bool
    passed: bool | None
    quality_claim: str

    @model_validator(mode="after")
    def validate_official_decision(self) -> GoldBenchmarkQualityReport:
        expected_official = self.benchmark_status is BenchmarkStatus.APPROVED
        if self.official_quality_decision != expected_official:
            raise ValueError("official_quality_decision must reflect approved benchmark status")
        if not expected_official and self.passed is not None:
            raise ValueError("non-approved benchmark cannot produce a pass/fail decision")
        if expected_official:
            if not self.threshold_checks or self.passed != all(self.threshold_checks.values()):
                raise ValueError("approved benchmark passed must equal all threshold checks")
        return self


class GoldBenchmarkError(ValueError):
    """Raised when an owner package or prediction set is unsafe or incomplete."""


def load_gold_benchmark_package(
    package_root: Path,
    *,
    allow_draft: bool = False,
    allow_offline_reference: bool = False,
) -> GoldBenchmarkPackage:
    """Load one package and fail closed on policy, label, approval, or hash drift."""

    root = package_root.resolve()
    manifest_path = _safe_package_file(
        root,
        "benchmark-manifest.yaml",
        maximum_bytes=_MAX_MANIFEST_BYTES,
    )
    manifest = _load_yaml_model(manifest_path, GoldBenchmarkManifest)

    allowed_statuses = {BenchmarkStatus.APPROVED}
    if allow_draft:
        allowed_statuses.add(BenchmarkStatus.DRAFT)
    if allow_offline_reference:
        allowed_statuses.add(BenchmarkStatus.OFFLINE_REFERENCE)
    if manifest.status not in allowed_statuses:
        raise GoldBenchmarkError(
            f"benchmark status is not executable in this mode: {manifest.status.value}"
        )

    policy_path = _safe_package_file(
        root,
        manifest.policy.path,
        maximum_bytes=_MAX_POLICY_BYTES,
    )
    registry = ReviewProfileRegistry()
    try:
        resolved_policy = registry.load_file(policy_path)
    except (OSError, ValueError) as error:
        raise GoldBenchmarkError("review policy failed strict validation") from error
    policy = resolved_policy.policy
    if (
        policy.policy_id != manifest.policy.policy_id
        or policy.version != manifest.policy.version
        or resolved_policy.ref.sha256 != manifest.policy.canonical_sha256
    ):
        raise GoldBenchmarkError("manifest review policy identity or hash drifted")
    _validate_status_pair(manifest.status, policy.status)

    labels_path = _safe_package_file(
        root,
        manifest.labels.path,
        maximum_bytes=_MAX_LABELS_BYTES,
    )
    if _sha256_file(labels_path) != manifest.labels.sha256:
        raise GoldBenchmarkError("gold labels file hash drifted")
    labels = _load_gold_labels(labels_path)
    if len(labels) != manifest.labels.record_count:
        raise GoldBenchmarkError("gold labels record_count does not match the file")
    _validate_labels_against_policy(
        labels,
        policy,
        evaluation_split=manifest.evaluation_split,
        approved=manifest.status is BenchmarkStatus.APPROVED,
    )

    approval_path = _safe_package_file(
        root,
        manifest.approval.path,
        maximum_bytes=_MAX_APPROVAL_BYTES,
    )
    if _sha256_file(approval_path) != manifest.approval.sha256:
        raise GoldBenchmarkError("owner approval Markdown hash drifted")
    approval = _load_owner_approval(approval_path)
    _validate_approval(manifest, policy, approval)

    return GoldBenchmarkPackage(
        package_root=str(root),
        manifest_sha256=_sha256_file(manifest_path),
        manifest=manifest,
        policy=policy,
        labels=labels,
        approval=approval,
    )


def prediction_from_report(report: EvaluationReport) -> BenchmarkPrediction:
    """Project an immutable report into stable, path-free benchmark fields."""

    criteria = tuple(
        PredictedCriterion(
            criterion_id=item.criterion_id,
            assessment=item.assessment,
            evidence_locators=tuple(
                dict.fromkeys(_stable_prediction_locator(ref.locator) for ref in item.evidence_refs)
            ),
            risk_flags=item.risk_flags,
        )
        for item in report.criteria
    )
    return BenchmarkPrediction(
        project_id=report.project_id,
        stage=report.stage,
        snapshot_sha256=report.snapshot.dossier_sha256,
        artifact_sha256=report.evaluated_artifact_sha256,
        policy_id=report.review_profile.policy_id,
        policy_version=report.review_profile.version,
        policy_sha256=report.review_profile.sha256,
        recommendation=report.recommendation,
        criteria=criteria,
        model=None if report.model_run is None else report.model_run.model,
        live_model=False if report.model_run is None else report.model_run.live,
    )


def evaluate_gold_benchmark(
    package: GoldBenchmarkPackage,
    predictions: tuple[BenchmarkPrediction, ...],
    *,
    allow_offline_reference: bool = False,
) -> GoldBenchmarkQualityReport:
    """Compare predictions with gold labels without making a human certification decision."""

    status = package.manifest.status
    if status is not BenchmarkStatus.APPROVED and not (
        allow_offline_reference and status is BenchmarkStatus.OFFLINE_REFERENCE
    ):
        raise GoldBenchmarkError(
            "quality evaluation requires an approved benchmark; "
            "offline_reference needs explicit opt-in"
        )

    evaluation_labels = tuple(
        label for label in package.labels if label.split is package.manifest.evaluation_split
    )
    if not evaluation_labels:
        raise GoldBenchmarkError("benchmark evaluation split contains no labels")

    by_key: dict[tuple[str, ReviewStage], BenchmarkPrediction] = {}
    for prediction in predictions:
        if prediction.key in by_key:
            raise GoldBenchmarkError("prediction set contains a duplicate project/stage")
        by_key[prediction.key] = prediction
    expected_keys = {label.key for label in evaluation_labels}
    if set(by_key) != expected_keys:
        raise GoldBenchmarkError("prediction set does not exactly cover gold project/stage keys")

    correct_criteria = 0
    criterion_count = 0
    correct_recommendations = 0
    gold_locator_count = 0
    predicted_locator_count = 0
    matched_locator_count = 0
    expected_insufficient_count = 0
    correct_insufficient_count = 0
    required_risk_flag_count = 0
    matched_risk_flag_count = 0
    human_vote_pair_count = 0
    human_agreeing_pair_count = 0
    negative_case_count = 0
    dangerous_positive_count = 0
    asserting_prediction_count = 0
    unsupported_claim_count = 0
    models: set[str] = set()
    live_model_report_count = 0

    for label in evaluation_labels:
        prediction = by_key[label.key]
        _validate_prediction_identity(package, label, prediction)
        if prediction.recommendation is label.expected_recommendation:
            correct_recommendations += 1

        positive = _positive_recommendation(label.stage)
        if label.expected_recommendation is not positive:
            negative_case_count += 1
            if prediction.recommendation is positive:
                dangerous_positive_count += 1

        gold_by_id = {item.criterion_id: item for item in label.criteria}
        predicted_by_id = {item.criterion_id: item for item in prediction.criteria}
        if len(predicted_by_id) != len(prediction.criteria) or set(predicted_by_id) != set(
            gold_by_id
        ):
            raise GoldBenchmarkError(f"prediction criteria do not match gold for {label.label_id}")
        for criterion_id, gold in gold_by_id.items():
            predicted = predicted_by_id[criterion_id]
            criterion_count += 1
            if predicted.assessment is gold.expected_assessment:
                correct_criteria += 1
            if gold.expected_assessment is Assessment.INSUFFICIENT_EVIDENCE:
                expected_insufficient_count += 1
                if predicted.assessment is Assessment.INSUFFICIENT_EVIDENCE:
                    correct_insufficient_count += 1

            required_flags = set(gold.required_risk_flags)
            predicted_flags = set(predicted.risk_flags)
            required_risk_flag_count += len(required_flags)
            matched_risk_flag_count += len(required_flags.intersection(predicted_flags))
            votes = gold.reviewer_votes
            for left in range(len(votes)):
                for right in range(left + 1, len(votes)):
                    human_vote_pair_count += 1
                    if votes[left].assessment is votes[right].assessment:
                        human_agreeing_pair_count += 1

            gold_locators = set(gold.acceptable_evidence_locators)
            predicted_locators = set(predicted.evidence_locators)
            gold_locator_count += len(gold_locators)
            predicted_locator_count += len(predicted_locators)
            matched = len(gold_locators.intersection(predicted_locators))
            matched_locator_count += matched
            if predicted.assessment in {
                Assessment.MET,
                Assessment.PARTIALLY_MET,
                Assessment.NOT_MET,
            }:
                asserting_prediction_count += 1
                if not predicted_locators or (gold_locators and matched == 0):
                    unsupported_claim_count += 1
        if prediction.model:
            models.add(prediction.model)
        if prediction.live_model:
            live_model_report_count += 1

    case_count = len(evaluation_labels)
    criterion_accuracy = correct_criteria / criterion_count
    recommendation_accuracy = correct_recommendations / case_count
    locator_precision = (
        matched_locator_count / predicted_locator_count
        if predicted_locator_count
        else (1.0 if gold_locator_count == 0 else 0.0)
    )
    locator_recall = matched_locator_count / gold_locator_count if gold_locator_count else 1.0
    insufficient_recall = (
        correct_insufficient_count / expected_insufficient_count
        if expected_insufficient_count
        else 1.0
    )
    risk_flag_recall = (
        matched_risk_flag_count / required_risk_flag_count if required_risk_flag_count else 1.0
    )
    human_agreement = (
        human_agreeing_pair_count / human_vote_pair_count if human_vote_pair_count else 1.0
    )
    dangerous_rate = dangerous_positive_count / negative_case_count if negative_case_count else 0.0
    unsupported_rate = (
        unsupported_claim_count / asserting_prediction_count if asserting_prediction_count else 0.0
    )

    thresholds = package.manifest.thresholds
    checks: dict[str, bool] = {}
    if thresholds is not None:
        checks = {
            "criterion_assessment_accuracy": (
                criterion_accuracy >= thresholds.criterion_assessment_accuracy_min
            ),
            "recommendation_accuracy": (
                recommendation_accuracy >= thresholds.recommendation_accuracy_min
            ),
            "evidence_locator_precision": (
                locator_precision >= thresholds.evidence_locator_precision_min
            ),
            "evidence_locator_recall": (locator_recall >= thresholds.evidence_locator_recall_min),
            "insufficient_evidence_recall": (
                expected_insufficient_count > 0
                and insufficient_recall >= thresholds.insufficient_evidence_recall_min
            ),
            "required_risk_flag_recall": (
                required_risk_flag_count > 0
                and risk_flag_recall >= thresholds.required_risk_flag_recall_min
            ),
            "human_pre_adjudication_agreement": (
                human_vote_pair_count > 0
                and human_agreement >= thresholds.human_pre_adjudication_agreement_min
            ),
            "dangerous_positive_rate": (
                negative_case_count > 0 and dangerous_rate <= thresholds.dangerous_positive_rate_max
            ),
            "unsupported_claim_rate": (unsupported_rate <= thresholds.unsupported_claim_rate_max),
        }
    official = status is BenchmarkStatus.APPROVED
    return GoldBenchmarkQualityReport(
        benchmark_id=package.manifest.benchmark_id,
        benchmark_version=package.manifest.version,
        benchmark_status=status,
        benchmark_split=package.manifest.evaluation_split,
        manifest_sha256=package.manifest_sha256,
        policy_id=package.policy.policy_id,
        policy_version=package.policy.version,
        policy_sha256=canonical_policy_sha256(package.policy),
        case_count=case_count,
        registration_case_count=sum(
            label.stage is ReviewStage.REGISTRATION for label in evaluation_labels
        ),
        completion_case_count=sum(
            label.stage is ReviewStage.COMPLETION for label in evaluation_labels
        ),
        criterion_count=criterion_count,
        gold_evidence_locator_count=gold_locator_count,
        predicted_evidence_locator_count=predicted_locator_count,
        expected_insufficient_evidence_count=expected_insufficient_count,
        required_risk_flag_count=required_risk_flag_count,
        human_vote_pair_count=human_vote_pair_count,
        negative_case_count=negative_case_count,
        asserting_prediction_count=asserting_prediction_count,
        criterion_assessment_accuracy=criterion_accuracy,
        recommendation_accuracy=recommendation_accuracy,
        evidence_locator_precision=locator_precision,
        evidence_locator_recall=locator_recall,
        insufficient_evidence_recall=insufficient_recall,
        required_risk_flag_recall=risk_flag_recall,
        human_pre_adjudication_agreement=human_agreement,
        dangerous_positive_count=dangerous_positive_count,
        dangerous_positive_rate=dangerous_rate,
        unsupported_claim_count=unsupported_claim_count,
        unsupported_claim_rate=unsupported_rate,
        live_model_report_count=live_model_report_count,
        models=tuple(sorted(models)),
        threshold_checks=checks,
        official_quality_decision=official,
        passed=all(checks.values()) if official else None,
        quality_claim=(
            "Owner-approved semantic benchmark comparison; this report evaluates Agent "
            "draft agreement and evidence traceability, never a final certification decision."
            if official
            else "Offline-reference benchmark smoke only; no official quality pass/fail claim."
        ),
    )


def _load_yaml_model(path: Path, model: type[GoldBenchmarkManifest]) -> GoldBenchmarkManifest:
    yaml = YAML(typ="safe")
    try:
        raw: Any = yaml.load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("YAML root must be a mapping")
        return model.model_validate(raw)
    except (OSError, ValueError) as error:
        raise GoldBenchmarkError(f"invalid benchmark manifest: {path.name}") from error


def _load_gold_labels(path: Path) -> tuple[GoldCaseLabel, ...]:
    labels: list[GoldCaseLabel] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                if len(line.encode("utf-8")) > _MAX_LABEL_LINE_BYTES:
                    raise GoldBenchmarkError(f"gold label line exceeds size limit: {line_number}")
                try:
                    labels.append(GoldCaseLabel.model_validate_json(line))
                except ValueError as error:
                    raise GoldBenchmarkError(f"invalid gold label at line {line_number}") from error
    except OSError as error:
        raise GoldBenchmarkError("gold labels file cannot be read") from error
    if not labels:
        raise GoldBenchmarkError("gold labels file is empty")
    keys = [label.key for label in labels]
    if len(keys) != len(set(keys)):
        raise GoldBenchmarkError("gold labels contain duplicate project/stage keys")
    label_ids = [label.label_id for label in labels]
    if len(label_ids) != len(set(label_ids)):
        raise GoldBenchmarkError("gold labels contain duplicate label_id values")
    return tuple(labels)


def _load_owner_approval(path: Path) -> EvaluationOwnerApproval:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise GoldBenchmarkError("owner approval Markdown cannot be read") from error
    if not lines or lines[0].strip() != "---":
        raise GoldBenchmarkError("owner approval Markdown requires YAML frontmatter")
    try:
        end = next(index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---")
    except StopIteration as error:
        raise GoldBenchmarkError("owner approval Markdown frontmatter is not closed") from error
    yaml = YAML(typ="safe")
    try:
        raw: Any = yaml.load("\n".join(lines[1:end]))
        if not isinstance(raw, dict):
            raise ValueError("frontmatter must be a mapping")
        return EvaluationOwnerApproval.model_validate(raw)
    except ValueError as error:
        raise GoldBenchmarkError("owner approval frontmatter is invalid") from error


def _validate_labels_against_policy(
    labels: tuple[GoldCaseLabel, ...],
    policy: ReviewPolicyPack,
    *,
    evaluation_split: BenchmarkSplit,
    approved: bool,
) -> None:
    evaluation_labels = tuple(label for label in labels if label.split is evaluation_split)
    stages = {label.stage for label in evaluation_labels}
    if approved and stages != {ReviewStage.REGISTRATION, ReviewStage.COMPLETION}:
        raise GoldBenchmarkError(
            "approved benchmark evaluation split must include registration and completion labels"
        )
    gold_locator_count = 0
    for label in labels:
        stage_policy = policy.for_stage(label.stage)
        expected_ids = {criterion.criterion_id for criterion in stage_policy.criteria}
        received_ids = {criterion.criterion_id for criterion in label.criteria}
        if received_ids != expected_ids:
            raise GoldBenchmarkError(
                f"gold label criteria do not match policy for {label.label_id}"
            )
        gold_locator_count += sum(len(item.acceptable_evidence_locators) for item in label.criteria)
        if approved and label.label_status is not GoldLabelStatus.ADJUDICATED:
            raise GoldBenchmarkError(
                "approved benchmark requires adjudicated labels with two reviewers"
            )
        if approved:
            expected_reviewers = set(label.reviewer_refs)
            for criterion in label.criteria:
                vote_reviewers = {vote.reviewer_ref for vote in criterion.reviewer_votes}
                if vote_reviewers != expected_reviewers:
                    raise GoldBenchmarkError(
                        "approved benchmark requires every reviewer vote for every criterion"
                    )
    if approved and gold_locator_count == 0:
        raise GoldBenchmarkError("approved benchmark requires at least one stable evidence locator")


def _validate_approval(
    manifest: GoldBenchmarkManifest,
    policy: ReviewPolicyPack,
    approval: EvaluationOwnerApproval,
) -> None:
    expected = (
        manifest.benchmark_id,
        manifest.version,
        manifest.status,
        manifest.owner_ref,
        manifest.approval_ref,
        policy.policy_id,
        policy.version,
        canonical_policy_sha256(policy),
        manifest.labels.sha256,
    )
    actual = (
        approval.benchmark_id,
        approval.benchmark_version,
        approval.status,
        approval.owner_ref,
        approval.approval_ref,
        approval.policy_id,
        approval.policy_version,
        approval.policy_sha256,
        approval.labels_sha256,
    )
    if actual != expected:
        raise GoldBenchmarkError("owner approval record does not match manifest, policy, or labels")


def _validate_status_pair(
    benchmark_status: BenchmarkStatus,
    policy_status: ReviewPolicyStatus,
) -> None:
    expected = {
        BenchmarkStatus.DRAFT: ReviewPolicyStatus.DRAFT,
        BenchmarkStatus.OFFLINE_REFERENCE: ReviewPolicyStatus.OFFLINE_REFERENCE,
        BenchmarkStatus.APPROVED: ReviewPolicyStatus.PUBLISHED,
        BenchmarkStatus.RETIRED: ReviewPolicyStatus.RETIRED,
    }[benchmark_status]
    if policy_status is not expected:
        raise GoldBenchmarkError("benchmark and review policy lifecycle statuses are inconsistent")


def _validate_prediction_identity(
    package: GoldBenchmarkPackage,
    label: GoldCaseLabel,
    prediction: BenchmarkPrediction,
) -> None:
    expected = (
        label.snapshot_sha256,
        label.artifact_sha256,
        package.policy.policy_id,
        package.policy.version,
        canonical_policy_sha256(package.policy),
    )
    actual = (
        prediction.snapshot_sha256,
        prediction.artifact_sha256,
        prediction.policy_id,
        prediction.policy_version,
        prediction.policy_sha256,
    )
    if actual != expected:
        raise GoldBenchmarkError(f"prediction identity drifted from gold label: {label.label_id}")
    if prediction.recommendation not in _recommendations_for_stage(label.stage):
        raise GoldBenchmarkError(f"prediction recommendation is invalid for {label.stage.value}")


def _safe_package_file(root: Path, relative: str, *, maximum_bytes: int) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute():
        raise GoldBenchmarkError("package file path must be relative")
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise GoldBenchmarkError("package file path escapes the package root") from error
    if not resolved.is_file():
        raise GoldBenchmarkError(f"package file is missing: {relative}")
    try:
        size = resolved.stat().st_size
    except OSError as error:
        raise GoldBenchmarkError(f"package file metadata is unavailable: {relative}") from error
    if size > maximum_bytes:
        raise GoldBenchmarkError(f"package file exceeds size limit: {relative}")
    return resolved


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_stable_gold_locator(locator: str) -> bool:
    return bool(
        _STABLE_SLIDE_LOCATOR.fullmatch(locator)
        or _REPORT_LOCATOR.fullmatch(locator)
        or _ARTIFACT_LOCATOR.fullmatch(locator)
    )


def _stable_prediction_locator(locator: str) -> str:
    slide = _REPORT_SLIDE_FRAGMENT.search(locator)
    if slide is not None:
        return f"pptx://slide/{slide.group(1)}"
    if _REPORT_LOCATOR.fullmatch(locator) or _ARTIFACT_LOCATOR.fullmatch(locator):
        return locator
    return "unresolved:sha256=" + hashlib.sha256(locator.encode("utf-8")).hexdigest()


def _recommendations_for_stage(stage: ReviewStage) -> set[AgentRecommendation]:
    if stage is ReviewStage.REGISTRATION:
        return {
            AgentRecommendation.PASS,
            AgentRecommendation.NEEDS_CHANGES,
            AgentRecommendation.REJECT,
        }
    return {
        AgentRecommendation.ACCEPT,
        AgentRecommendation.NEEDS_CHANGES,
        AgentRecommendation.NOT_ACCEPT,
    }


def _positive_recommendation(stage: ReviewStage) -> AgentRecommendation:
    return (
        AgentRecommendation.PASS
        if stage is ReviewStage.REGISTRATION
        else AgentRecommendation.ACCEPT
    )


__all__ = [
    "BENCHMARK_MANIFEST_SCHEMA_VERSION",
    "BENCHMARK_REPORT_SCHEMA_VERSION",
    "GOLD_CASE_SCHEMA_VERSION",
    "OWNER_APPROVAL_SCHEMA_VERSION",
    "BenchmarkPrediction",
    "BenchmarkSplit",
    "BenchmarkStatus",
    "BenchmarkThresholds",
    "EvaluationOwnerApproval",
    "GoldBenchmarkError",
    "GoldBenchmarkManifest",
    "GoldBenchmarkPackage",
    "GoldBenchmarkQualityReport",
    "GoldCaseLabel",
    "GoldCriterionLabel",
    "GoldLabelStatus",
    "GoldReviewerVote",
    "OwnerDecision",
    "PredictedCriterion",
    "evaluate_gold_benchmark",
    "load_gold_benchmark_package",
    "prediction_from_report",
]
