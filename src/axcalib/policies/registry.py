"""Versioned, hash-bound review policy packs for deterministic evaluation."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, model_validator
from ruamel.yaml import YAML

from axcalib.schemas import (
    AgentRecommendation,
    FrozenModel,
    ReviewPolicyStatus,
    ReviewProfileRef,
    ReviewStage,
)

DEFAULT_REVIEW_PROFILE = "axcalib.default@1.0.0"


class ReferenceAuthority(StrEnum):
    """How a reference may influence a review."""

    NORMATIVE = "normative"
    GUIDANCE = "guidance"
    HISTORICAL = "historical"


class ReviewReference(FrozenModel):
    """Allowlisted reference metadata; source bytes remain external."""

    reference_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{1,127}$")
    title: str = Field(min_length=1, max_length=300)
    authority: ReferenceAuthority
    uri: str
    version: str = Field(min_length=1, max_length=100)
    sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")


class CriterionDefinition(FrozenModel):
    """One deterministic criterion loaded from a trusted policy pack."""

    criterion_id: str = Field(pattern=r"^[A-Z][A-Z0-9_-]{2,127}$")
    title: str = Field(min_length=1, max_length=300)
    required_tags: tuple[str, ...] = Field(min_length=1)
    follow_up: str = Field(min_length=1, max_length=2000)
    critical: bool = False
    blocking_recommendation: AgentRecommendation | None = None


class StageReviewPolicy(FrozenModel):
    """Rubric, references, and recommendation semantics for one gate."""

    stage: ReviewStage
    rubric_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{2,127}$")
    rubric_version: str = Field(pattern=r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$")
    checklist_refs: tuple[str, ...] = Field(min_length=1)
    references: tuple[ReviewReference, ...] = ()
    criteria: tuple[CriterionDefinition, ...] = Field(min_length=1)
    all_met_recommendation: AgentRecommendation
    gap_recommendation: AgentRecommendation

    @model_validator(mode="after")
    def validate_stage_semantics(self) -> StageReviewPolicy:
        """Reject duplicate IDs and cross-stage recommendation vocabulary."""

        criterion_ids = [item.criterion_id for item in self.criteria]
        if len(criterion_ids) != len(set(criterion_ids)):
            raise ValueError("criterion_id values must be unique within a stage")
        reference_ids = [item.reference_id for item in self.references]
        if len(reference_ids) != len(set(reference_ids)):
            raise ValueError("reference_id values must be unique within a stage")
        allowed = (
            {
                AgentRecommendation.PASS,
                AgentRecommendation.NEEDS_CHANGES,
                AgentRecommendation.REJECT,
            }
            if self.stage is ReviewStage.REGISTRATION
            else {
                AgentRecommendation.ACCEPT,
                AgentRecommendation.NEEDS_CHANGES,
                AgentRecommendation.NOT_ACCEPT,
            }
        )
        recommendations = {
            self.all_met_recommendation,
            self.gap_recommendation,
            *(item.blocking_recommendation for item in self.criteria),
        }
        invalid = {item for item in recommendations if item is not None and item not in allowed}
        if invalid:
            raise ValueError(
                f"recommendations are invalid for {self.stage.value}: "
                + ", ".join(sorted(item.value for item in invalid))
            )
        return self


class ReviewPolicyPack(FrozenModel):
    """Canonical machine-readable policy for both AXCalib review gates."""

    schema_version: Literal["axcalib.review-policy-pack/v1alpha1"] = (
        "axcalib.review-policy-pack/v1alpha1"
    )
    policy_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{2,127}$")
    version: str = Field(pattern=r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$")
    status: ReviewPolicyStatus
    owner: str = Field(min_length=1, max_length=200)
    approval_ref: str | None = None
    description: str = Field(min_length=1, max_length=1000)
    registration: StageReviewPolicy
    completion: StageReviewPolicy

    @model_validator(mode="after")
    def validate_gate_binding(self) -> ReviewPolicyPack:
        """Keep registration and completion rubrics bound to their own gates."""

        if self.registration.stage is not ReviewStage.REGISTRATION:
            raise ValueError("registration policy must declare stage=registration")
        if self.completion.stage is not ReviewStage.COMPLETION:
            raise ValueError("completion policy must declare stage=completion")
        if self.status is ReviewPolicyStatus.PUBLISHED and not self.approval_ref:
            raise ValueError("published review policy requires approval_ref")
        return self

    def for_stage(self, stage: ReviewStage) -> StageReviewPolicy:
        """Return the immutable policy for one gate."""

        return self.registration if stage is ReviewStage.REGISTRATION else self.completion


class ResolvedReviewProfile(FrozenModel):
    """Validated pack plus its immutable source identity."""

    ref: ReviewProfileRef
    policy: ReviewPolicyPack


class ReviewProfileError(ValueError):
    """Base error for unsafe or unavailable review profiles."""


class ReviewProfileCollisionError(ReviewProfileError):
    """Raised when the same id/version is reused for different policy bytes."""


class ReviewProfileUnavailableError(ReviewProfileError):
    """Raised when a requested profile cannot be used exactly as frozen."""


def canonical_policy_sha256(policy: ReviewPolicyPack) -> str:
    """Hash canonical validated JSON, independent of YAML formatting."""

    payload = json.dumps(
        policy.model_dump(mode="json", exclude_none=True),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def builtin_default_policy() -> ReviewPolicyPack:
    """Return the code-owned offline reference policy used by the MVP."""

    registration = StageReviewPolicy(
        stage=ReviewStage.REGISTRATION,
        rubric_id="axcalib.registration-checklist",
        rubric_version="1.0.0",
        checklist_refs=("docs/rubrics/registration_checklist.md",),
        references=(
            ReviewReference(
                reference_id="registration-checklist-guide",
                title="AXCalib registration checklist guide",
                authority=ReferenceAuthority.GUIDANCE,
                uri="docs/rubrics/registration_checklist.md",
                version="0.1.0-draft",
                sha256="3661a7ce6140ac70f1efe51f9eaae1c5885fae238894771277b701340813ec5a",
            ),
        ),
        criteria=(
            CriterionDefinition(
                criterion_id="REG-PROBLEM-GOAL",
                title="문제와 AX 목표",
                required_tags=("problem", "goal"),
                follow_up="해결하려는 문제와 목표를 한 문장씩 명시해 주십시오.",
                critical=True,
                blocking_recommendation=AgentRecommendation.REJECT,
            ),
            CriterionDefinition(
                criterion_id="REG-SCOPE-METHOD",
                title="범위와 접근방법",
                required_tags=("scope", "method"),
                follow_up="포함·제외 범위와 핵심 방법을 구분해 주십시오.",
            ),
            CriterionDefinition(
                criterion_id="REG-PLAN-VALIDATION",
                title="로드맵과 검증계획",
                required_tags=("roadmap", "validation_plan"),
                follow_up="단계별 종료조건과 검증 책임자를 추가해 주십시오.",
            ),
            CriterionDefinition(
                criterion_id="REG-KPI",
                title="정량 KPI와 측정방법",
                required_tags=("kpi_plan", "quantitative_target"),
                follow_up="KPI별 baseline, target, unit, period와 측정방법을 제시해 주십시오.",
                critical=True,
            ),
            CriterionDefinition(
                criterion_id="REG-RISK",
                title="위험과 한계",
                required_tags=("risk", "limitation"),
                follow_up="위험별 대응책, owner와 중단조건을 연결해 주십시오.",
            ),
            CriterionDefinition(
                criterion_id="REG-DATA-GOVERNANCE",
                title="데이터·보안·윤리",
                required_tags=("data", "security"),
                follow_up="데이터 출처, 접근등급, 개인정보와 외부전송 정책을 명시해 주십시오.",
                critical=True,
            ),
            CriterionDefinition(
                criterion_id="REG-ROLE-RESOURCE",
                title="역할과 자원",
                required_tags=("role", "resource"),
                follow_up="과제 owner, 평가자, 필요한 인력·시스템·예산을 명시해 주십시오.",
            ),
        ),
        all_met_recommendation=AgentRecommendation.PASS,
        gap_recommendation=AgentRecommendation.NEEDS_CHANGES,
    )
    completion = StageReviewPolicy(
        stage=ReviewStage.COMPLETION,
        rubric_id="axcalib.completion-checklist",
        rubric_version="1.0.0",
        checklist_refs=("docs/rubrics/completion_checklist.md",),
        references=(
            ReviewReference(
                reference_id="completion-checklist-guide",
                title="AXCalib completion checklist guide",
                authority=ReferenceAuthority.GUIDANCE,
                uri="docs/rubrics/completion_checklist.md",
                version="0.1.0-draft",
                sha256="260f4fdfedddae2cd8cc22f98afd1d8ea9586384d1126d809e2966d298354649",
            ),
        ),
        criteria=(
            CriterionDefinition(
                criterion_id="COM-DELIVERABLE",
                title="완료 산출물과 작동 증거",
                required_tags=("deliverable", "result"),
                follow_up="실제 산출물 URI/hash, 실행 로그와 검증 결과를 제출해 주십시오.",
                critical=True,
                blocking_recommendation=AgentRecommendation.NOT_ACCEPT,
            ),
            CriterionDefinition(
                criterion_id="COM-KPI",
                title="KPI 관측값과 달성도",
                required_tags=("result", "quantitative_target"),
                follow_up="관측값, 단위, 기간, 측정방법과 원문 locator를 제출해 주십시오.",
                critical=True,
                blocking_recommendation=AgentRecommendation.NOT_ACCEPT,
            ),
            CriterionDefinition(
                criterion_id="COM-EXECUTION",
                title="수행·재현 증거",
                required_tags=("result", "reproducibility"),
                follow_up="버전, 환경, 테스트 및 재실행 절차를 제출해 주십시오.",
                critical=True,
                blocking_recommendation=AgentRecommendation.NOT_ACCEPT,
            ),
            CriterionDefinition(
                criterion_id="COM-CHANGE",
                title="등록안 대비 변경",
                required_tags=("change",),
                follow_up="등록 baseline 대비 변경과 승인 여부를 명시해 주십시오.",
            ),
            CriterionDefinition(
                criterion_id="COM-RISK-FOLLOWUP",
                title="완료 시점 위험과 후속계획",
                required_tags=("risk", "limitation"),
                follow_up="남은 위험, 운영 한계와 후속 책임자를 명시해 주십시오.",
            ),
        ),
        all_met_recommendation=AgentRecommendation.ACCEPT,
        gap_recommendation=AgentRecommendation.NEEDS_CHANGES,
    )
    return ReviewPolicyPack(
        policy_id="axcalib.default",
        version="1.0.0",
        status=ReviewPolicyStatus.OFFLINE_REFERENCE,
        owner="unassigned:evaluation-owner",
        description=(
            "Synthetic/offline two-gate reference policy; not an approved production rubric."
        ),
        registration=registration,
        completion=completion,
    )


class ReviewProfileRegistry:
    """Allowlisted in-memory registry keyed by immutable policy id and version."""

    def __init__(self) -> None:
        self._profiles: dict[tuple[str, str], ResolvedReviewProfile] = {}

    @classmethod
    def with_builtin_default(cls) -> ReviewProfileRegistry:
        """Create a registry containing the offline reference policy."""

        registry = cls()
        registry.register(builtin_default_policy(), source_uri="builtin://axcalib.default/1.0.0")
        return registry

    def register(
        self,
        policy: ReviewPolicyPack,
        *,
        source_uri: str,
    ) -> ResolvedReviewProfile:
        """Register a validated pack, rejecting mutable id/version reuse."""

        digest = canonical_policy_sha256(policy)
        ref = ReviewProfileRef(
            policy_id=policy.policy_id,
            version=policy.version,
            sha256=digest,
            status=policy.status,
            source_uri=source_uri,
        )
        resolved = ResolvedReviewProfile(ref=ref, policy=policy)
        key = (policy.policy_id, policy.version)
        existing = self._profiles.get(key)
        if existing and existing.ref.sha256 != digest:
            raise ReviewProfileCollisionError(
                f"policy id/version collision: {policy.policy_id}@{policy.version}"
            )
        self._profiles[key] = resolved
        return resolved

    def load_file(self, path: Path) -> ResolvedReviewProfile:
        """Load one strict YAML policy pack and bind its resolved source URI."""

        resolved_path = path.resolve()
        yaml = YAML(typ="safe")
        raw: Any = yaml.load(resolved_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ReviewProfileError(f"review policy must be a mapping: {resolved_path}")
        policy = ReviewPolicyPack.model_validate(raw)
        return self.register(policy, source_uri=str(resolved_path))

    def load_directory(self, root: Path) -> tuple[ResolvedReviewProfile, ...]:
        """Load sorted YAML files only; arbitrary imports and expressions are unsupported."""

        resolved_root = root.resolve()
        if not resolved_root.is_dir():
            return ()
        paths = sorted((*resolved_root.glob("*.yaml"), *resolved_root.glob("*.yml")))
        return tuple(self.load_file(path) for path in paths)

    def resolve(
        self,
        selector: str,
        *,
        expected_sha256: str | None = None,
        allow_offline_reference: bool = False,
    ) -> ResolvedReviewProfile:
        """Resolve an exact selector and fail closed on status or hash drift."""

        try:
            policy_id, version = selector.rsplit("@", 1)
        except ValueError as error:
            raise ReviewProfileUnavailableError(
                "review profile selector must use policy_id@version"
            ) from error
        profile = self._profiles.get((policy_id, version))
        if profile is None:
            raise ReviewProfileUnavailableError(f"review profile is not registered: {selector}")
        if expected_sha256 and profile.ref.sha256 != expected_sha256:
            raise ReviewProfileUnavailableError(
                f"review profile hash mismatch for {selector}; frozen case cannot be evaluated"
            )
        if profile.policy.status is ReviewPolicyStatus.PUBLISHED:
            return profile
        if (
            allow_offline_reference
            and profile.policy.status is ReviewPolicyStatus.OFFLINE_REFERENCE
        ):
            return profile
        raise ReviewProfileUnavailableError(
            "review profile status is not selectable in this runtime: "
            f"{profile.policy.status.value}"
        )

    def resolve_ref(
        self,
        ref: ReviewProfileRef,
        *,
        allow_offline_reference: bool = False,
    ) -> ResolvedReviewProfile:
        """Resolve a dossier reference with exact hash verification."""

        return self.resolve(
            ref.selector,
            expected_sha256=ref.sha256,
            allow_offline_reference=allow_offline_reference,
        )


__all__ = [
    "DEFAULT_REVIEW_PROFILE",
    "CriterionDefinition",
    "ReferenceAuthority",
    "ResolvedReviewProfile",
    "ReviewPolicyPack",
    "ReviewProfileCollisionError",
    "ReviewProfileError",
    "ReviewProfileRegistry",
    "ReviewProfileUnavailableError",
    "ReviewReference",
    "StageReviewPolicy",
    "builtin_default_policy",
    "canonical_policy_sha256",
]
