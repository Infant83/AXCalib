from __future__ import annotations

import hashlib
import json
import shutil
from io import StringIO
from pathlib import Path

import pytest
from pydantic import ValidationError
from ruamel.yaml import YAML

from axcalib.calibration import (
    BenchmarkPrediction,
    BenchmarkStatus,
    BenchmarkThresholds,
    GoldBenchmarkError,
    GoldBenchmarkPackage,
    GoldLabelStatus,
    PredictedCriterion,
    evaluate_gold_benchmark,
    load_gold_benchmark_package,
)
from axcalib.policies import ReviewProfileRegistry, canonical_policy_sha256
from axcalib.schemas import ReviewPolicyStatus

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "docs" / "evaluation" / "templates" / "evaluation-owner-package"


def test_copyable_owner_template_validates_only_with_draft_opt_in() -> None:
    package = load_gold_benchmark_package(TEMPLATE, allow_draft=True)

    assert package.manifest.status is BenchmarkStatus.DRAFT
    assert len(package.labels) == 2
    assert {item.stage.value for item in package.labels} == {
        "registration",
        "completion",
    }
    with pytest.raises(GoldBenchmarkError, match="not executable"):
        load_gold_benchmark_package(TEMPLATE)


def test_owner_package_rejects_hash_drift(tmp_path: Path) -> None:
    package_root = tmp_path / "owner-package"
    package_root.mkdir()
    for source in TEMPLATE.iterdir():
        if source.is_file():
            (package_root / source.name).write_bytes(source.read_bytes())
    labels = package_root / "gold-labels.jsonl"
    labels.write_text(labels.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(GoldBenchmarkError, match="labels file hash drifted"):
        load_gold_benchmark_package(package_root, allow_draft=True)


def test_approved_manifest_requires_owner_thresholds() -> None:
    draft = load_gold_benchmark_package(TEMPLATE, allow_draft=True)

    with pytest.raises(ValidationError, match="owner-selected thresholds"):
        draft.manifest.model_copy(
            update={"status": BenchmarkStatus.APPROVED, "approval_ref": "approval:test"},
        ).model_validate(
            {
                **draft.manifest.model_dump(mode="json"),
                "status": "approved",
                "approval_ref": "approval:test",
                "thresholds": None,
            }
        )


def test_approved_manifest_requires_hidden_test_split() -> None:
    draft = load_gold_benchmark_package(TEMPLATE, allow_draft=True)
    thresholds = BenchmarkThresholds(
        criterion_assessment_accuracy_min=0.8,
        recommendation_accuracy_min=0.8,
        evidence_locator_precision_min=0.8,
        evidence_locator_recall_min=0.8,
        insufficient_evidence_recall_min=0.8,
        required_risk_flag_recall_min=0.8,
        human_pre_adjudication_agreement_min=0.8,
        dangerous_positive_rate_max=0.0,
        unsupported_claim_rate_max=0.0,
    )

    with pytest.raises(ValidationError, match="evaluation_split=test"):
        draft.manifest.__class__.model_validate(
            {
                **draft.manifest.model_dump(mode="json"),
                "status": "approved",
                "approval_ref": "approval:test",
                "thresholds": thresholds.model_dump(mode="json"),
            }
        )


def test_adjudicated_label_requires_two_reviewers() -> None:
    label = load_gold_benchmark_package(TEMPLATE, allow_draft=True).labels[0]

    with pytest.raises(ValidationError, match="two reviewers"):
        label.__class__.model_validate(
            {
                **label.model_dump(mode="json"),
                "label_status": GoldLabelStatus.ADJUDICATED.value,
                "adjudication_ref": "adjudication:test",
            }
        )


def test_offline_reference_metrics_have_no_official_pass_decision() -> None:
    package = _offline_package()
    predictions = tuple(_matching_prediction(package, label) for label in package.labels)

    report = evaluate_gold_benchmark(
        package,
        predictions,
        allow_offline_reference=True,
    )

    assert report.criterion_assessment_accuracy == 1.0
    assert report.recommendation_accuracy == 1.0
    assert report.insufficient_evidence_recall == 1.0
    assert report.dangerous_positive_rate == 0.0
    assert report.unsupported_claim_rate == 0.0
    assert report.expected_insufficient_evidence_count == 12
    assert report.required_risk_flag_count == 6
    assert report.negative_case_count == 2
    assert report.official_quality_decision is False
    assert report.passed is None
    assert report.benchmark_split.value == "development"


def test_dangerous_positive_recommendations_are_measured() -> None:
    package = _offline_package()
    predictions = []
    for label in package.labels:
        prediction = _matching_prediction(package, label)
        positive = "pass" if label.stage.value == "registration" else "accept"
        predictions.append(
            BenchmarkPrediction.model_validate(
                {
                    **prediction.model_dump(mode="json"),
                    "recommendation": positive,
                }
            )
        )

    report = evaluate_gold_benchmark(
        package,
        tuple(predictions),
        allow_offline_reference=True,
    )

    assert report.dangerous_positive_count == 2
    assert report.dangerous_positive_rate == 1.0
    assert report.recommendation_accuracy == 0.0


def test_approved_package_loads_and_produces_official_test_split_result(
    tmp_path: Path,
) -> None:
    package_root = _write_approved_package(tmp_path)
    package = load_gold_benchmark_package(package_root)
    predictions = tuple(_matching_prediction(package, label) for label in package.labels)

    report = evaluate_gold_benchmark(package, predictions)

    assert report.benchmark_status is BenchmarkStatus.APPROVED
    assert report.benchmark_split.value == "test"
    assert report.official_quality_decision is True
    assert report.passed is True
    assert report.registration_case_count == 1
    assert report.completion_case_count == 1
    assert report.human_vote_pair_count == report.criterion_count


def test_approved_result_fails_when_required_risk_metric_has_no_gold_cases(
    tmp_path: Path,
) -> None:
    package_root = _write_approved_package(tmp_path, include_risk_flags=False)
    package = load_gold_benchmark_package(package_root)
    predictions = tuple(_matching_prediction(package, label) for label in package.labels)

    report = evaluate_gold_benchmark(package, predictions)

    assert report.required_risk_flag_count == 0
    assert report.required_risk_flag_recall == 1.0
    assert report.threshold_checks["required_risk_flag_recall"] is False
    assert report.passed is False


def _offline_package() -> GoldBenchmarkPackage:
    draft = load_gold_benchmark_package(TEMPLATE, allow_draft=True)
    policy = draft.policy.model_copy(update={"status": ReviewPolicyStatus.OFFLINE_REFERENCE})
    policy_sha256 = canonical_policy_sha256(policy)
    manifest_policy = draft.manifest.policy.model_copy(update={"canonical_sha256": policy_sha256})
    thresholds = BenchmarkThresholds(
        criterion_assessment_accuracy_min=0.8,
        recommendation_accuracy_min=0.8,
        evidence_locator_precision_min=0.8,
        evidence_locator_recall_min=0.8,
        insufficient_evidence_recall_min=0.8,
        required_risk_flag_recall_min=0.8,
        human_pre_adjudication_agreement_min=0.8,
        dangerous_positive_rate_max=0.0,
        unsupported_claim_rate_max=0.0,
    )
    manifest = draft.manifest.model_copy(
        update={
            "status": BenchmarkStatus.OFFLINE_REFERENCE,
            "policy": manifest_policy,
            "thresholds": thresholds,
        }
    )
    approval = draft.approval.model_copy(
        update={
            "status": BenchmarkStatus.OFFLINE_REFERENCE,
            "policy_sha256": policy_sha256,
        }
    )
    return GoldBenchmarkPackage(
        package_root=draft.package_root,
        manifest_sha256="e" * 64,
        manifest=manifest,
        policy=policy,
        labels=draft.labels,
        approval=approval,
    )


def _write_approved_package(
    tmp_path: Path,
    *,
    include_risk_flags: bool = True,
) -> Path:
    package_root = tmp_path / "approved-owner-package"
    shutil.copytree(TEMPLATE, package_root)
    yaml = YAML()

    policy_path = package_root / "review-policy.yaml"
    policy_data = yaml.load(policy_path.read_text(encoding="utf-8"))
    policy_data["status"] = "published"
    policy_data["approval_ref"] = "approval:owner-001"
    policy_stream = StringIO()
    yaml.dump(policy_data, policy_stream)
    policy_path.write_text(policy_stream.getvalue(), encoding="utf-8")
    policy = ReviewProfileRegistry().load_file(policy_path).policy
    policy_sha256 = canonical_policy_sha256(policy)

    labels_path = package_root / "gold-labels.jsonl"
    approved_labels = []
    for line in labels_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        label = json.loads(line)
        label["split"] = "test"
        label["label_status"] = "adjudicated"
        label["reviewer_refs"] = ["reviewer:one", "reviewer:two"]
        label["adjudication_ref"] = "adjudication:owner-001"
        for index, criterion in enumerate(label["criteria"]):
            if not include_risk_flags:
                criterion["required_risk_flags"] = []
            if index == 0:
                criterion["expected_assessment"] = "not_met"
                criterion["acceptable_evidence_locators"] = ["pptx://slide/1"]
            criterion["reviewer_votes"] = [
                {
                    "reviewer_ref": "reviewer:one",
                    "assessment": criterion["expected_assessment"],
                },
                {
                    "reviewer_ref": "reviewer:two",
                    "assessment": criterion["expected_assessment"],
                },
            ]
        approved_labels.append(json.dumps(label, ensure_ascii=False, separators=(",", ":")))
    labels_path.write_text("\n".join(approved_labels) + "\n", encoding="utf-8")
    labels_sha256 = hashlib.sha256(labels_path.read_bytes()).hexdigest()

    approval_path = package_root / "OWNER_APPROVAL.md"
    approval_frontmatter = {
        "schema_version": "axcalib.evaluation-owner-approval/v1alpha1",
        "benchmark_id": "replace.ax-project.semantic-gold",
        "benchmark_version": "0.1.0",
        "status": "approved",
        "decision": "approve",
        "owner_ref": "replace:evaluation-owner",
        "approval_ref": "approval:owner-001",
        "approved_at": "2026-07-24T00:00:00Z",
        "policy_id": "replace.ax-project.review",
        "policy_version": "0.1.0",
        "policy_sha256": policy_sha256,
        "labels_sha256": labels_sha256,
        "data_classification": "synthetic",
        "external_model_allowed": False,
    }
    approval_stream = StringIO()
    yaml.dump(approval_frontmatter, approval_stream)
    approval_path.write_text(
        "---\n" + approval_stream.getvalue() + "---\n\n# Approved synthetic test fixture\n",
        encoding="utf-8",
    )
    approval_sha256 = hashlib.sha256(approval_path.read_bytes()).hexdigest()

    manifest_path = package_root / "benchmark-manifest.yaml"
    manifest_data = yaml.load(manifest_path.read_text(encoding="utf-8"))
    manifest_data["status"] = "approved"
    manifest_data["approval_ref"] = "approval:owner-001"
    manifest_data["evaluation_split"] = "test"
    manifest_data["policy"]["canonical_sha256"] = policy_sha256
    manifest_data["labels"]["sha256"] = labels_sha256
    manifest_data["approval"]["sha256"] = approval_sha256
    manifest_data["thresholds"] = BenchmarkThresholds(
        criterion_assessment_accuracy_min=0.8,
        recommendation_accuracy_min=0.8,
        evidence_locator_precision_min=0.8,
        evidence_locator_recall_min=0.8,
        insufficient_evidence_recall_min=0.8,
        required_risk_flag_recall_min=0.8,
        human_pre_adjudication_agreement_min=0.8,
        dangerous_positive_rate_max=0.0,
        unsupported_claim_rate_max=0.0,
    ).model_dump(mode="json")
    manifest_stream = StringIO()
    yaml.dump(manifest_data, manifest_stream)
    manifest_path.write_text(manifest_stream.getvalue(), encoding="utf-8")
    return package_root


def _matching_prediction(package: GoldBenchmarkPackage, label) -> BenchmarkPrediction:
    return BenchmarkPrediction(
        project_id=label.project_id,
        stage=label.stage,
        snapshot_sha256=label.snapshot_sha256,
        artifact_sha256=label.artifact_sha256,
        policy_id=package.policy.policy_id,
        policy_version=package.policy.version,
        policy_sha256=canonical_policy_sha256(package.policy),
        recommendation=label.expected_recommendation,
        criteria=tuple(
            PredictedCriterion(
                criterion_id=item.criterion_id,
                assessment=item.expected_assessment,
                evidence_locators=item.acceptable_evidence_locators,
                risk_flags=item.required_risk_flags,
            )
            for item in label.criteria
        ),
    )
