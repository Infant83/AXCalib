import hashlib
from pathlib import Path

import pytest
from pydantic import ValidationError

from axcalib import AXCalib
from axcalib.policies import (
    CriterionDefinition,
    ReviewProfileCollisionError,
    ReviewProfileRegistry,
    ReviewProfileUnavailableError,
    builtin_default_policy,
    canonical_policy_sha256,
)
from axcalib.schemas import Assessment, EvaluationReport, ReviewerAdjustment

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tests" / "sources" / "oled_qc_project_outline.pptx"
SIDECAR = ROOT / "tests" / "sources" / "oled_qc_project_outline.axcalib.json"
PROFILE = ROOT / "config" / "review_profiles" / "axcalib-default-v1.yaml"


def test_yaml_policy_matches_code_owned_offline_fallback() -> None:
    registry = ReviewProfileRegistry.with_builtin_default()
    resolved = registry.load_file(PROFILE)

    assert resolved.ref.selector == "axcalib.default@1.0.0"
    assert resolved.ref.sha256 == canonical_policy_sha256(builtin_default_policy())
    for stage in (resolved.policy.registration, resolved.policy.completion):
        for reference in stage.references:
            assert reference.sha256 == hashlib.sha256(
                (ROOT / reference.uri).read_bytes()
            ).hexdigest()
    with pytest.raises(ReviewProfileUnavailableError, match="not selectable"):
        registry.resolve(resolved.ref.selector)


def test_registry_rejects_mutable_id_version_reuse() -> None:
    registry = ReviewProfileRegistry.with_builtin_default()
    changed = builtin_default_policy().model_copy(update={"description": "changed in place"})

    with pytest.raises(ReviewProfileCollisionError, match="collision"):
        registry.register(changed, source_uri="memory://changed")


def test_case_profile_changes_criteria_and_is_frozen_in_report(tmp_path: Path) -> None:
    base = builtin_default_policy()
    custom_registration = base.registration.model_copy(
        update={
            "criteria": (
                *base.registration.criteria,
                CriterionDefinition(
                    criterion_id="REG-CHANGE-READINESS",
                    title="변화관리 준비도",
                    required_tags=("role", "roadmap"),
                    follow_up="변화관리 책임자와 전환 일정을 명시해 주십시오.",
                ),
            )
        }
    )
    custom = base.model_copy(
        update={
            "policy_id": "axcalib.smart-factory-l2",
            "version": "0.1.0",
            "registration": custom_registration,
        }
    )
    registry = ReviewProfileRegistry.with_builtin_default()
    custom_profile = registry.register(custom, source_uri="memory://smart-factory-l2")
    client = AXCalib(tmp_path / "case", review_profiles=registry)

    dossier = client.register_case(
        SOURCE,
        title="정책 주입 회귀",
        sidecar_path=SIDECAR,
        project_id="profile-injection-001",
        review_profile=custom_profile.ref.selector,
    )
    client.submit_registration(dossier.project_id)
    result = client.evaluate(dossier.project_id, "registration")
    report = EvaluationReport.model_validate_json(
        Path(result.report_json_uri or "").read_text(encoding="utf-8")
    )

    assert report.review_profile == custom_profile.ref
    assert dossier.review_profile is not None
    assert report.review_profile.sha256 == dossier.review_profile.sha256
    assert "REG-CHANGE-READINESS" in {item.criterion_id for item in report.criteria}
    saved = client.service.dossiers.load(dossier.project_id)
    assert saved.registration.review_profile == custom_profile.ref


def test_human_adjustment_is_separate_and_stale_base_is_rejected(tmp_path: Path) -> None:
    client = AXCalib(tmp_path / "adjustment")
    dossier = client.register_case(
        SOURCE,
        title="관리자 보정 감사",
        sidecar_path=SIDECAR,
        project_id="review-adjustment-001",
    )
    client.submit_registration(dossier.project_id)
    result = client.evaluate(dossier.project_id, "registration")
    report_path = Path(result.report_json_uri or "")
    before = report_path.read_bytes()
    report = EvaluationReport.model_validate_json(before)
    criterion = report.criteria[0]
    adjustment = ReviewerAdjustment(
        criterion_id=criterion.criterion_id,
        from_assessment=criterion.assessment,
        to_assessment=Assessment.NOT_MET,
        reason="관리자 원문 재검토 결과 목표 범위가 불명확하다.",
    )

    client.decide_registration(
        dossier.project_id,
        command="approve",
        actor_id="admin:test",
        rationale="Agent finding과 관리자 보정을 분리해 기록한다.",
        adjustments=(adjustment,),
    )

    saved = client.service.dossiers.load(dossier.project_id)
    assert saved.registration.decision is not None
    assert saved.registration.decision.adjustments == (adjustment,)
    assert report_path.read_bytes() == before

    stale = adjustment.model_copy(update={"from_assessment": Assessment.NOT_APPLICABLE})
    with pytest.raises(ValueError, match="base assessment is stale"):
        client.service._validate_adjustments(report, (stale,))


def test_project_id_cannot_escape_workspace(tmp_path: Path) -> None:
    client = AXCalib(tmp_path / "safe-path")
    with pytest.raises(ValidationError, match="project_id"):
        client.register_case(
            SOURCE,
            title="금지된 경로",
            sidecar_path=SIDECAR,
            project_id="../outside",
        )
