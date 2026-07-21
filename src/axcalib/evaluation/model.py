"""Structured model evaluator layered over deterministic workflow invariants."""

from __future__ import annotations

import hashlib
import json

from pydantic import Field

from axcalib.evaluation.offline import OfflineEvidenceEvaluator
from axcalib.models import OpenAICompatibleClient
from axcalib.policies import ResolvedReviewProfile, StageReviewPolicy
from axcalib.schemas import (
    AgentRecommendation,
    Assessment,
    CriterionResult,
    EvaluationReport,
    EvidenceDocument,
    EvidenceLocator,
    FrozenModel,
    ModelRunManifest,
    ProjectDossier,
    SnapshotRef,
)

MODEL_EVALUATOR_ID = "axcalib.structured-evidence-model/v1"


class ModelCriterionFinding(FrozenModel):
    """Model finding before source-controlled locator materialization."""

    criterion_id: str
    assessment: Assessment
    observation: str = Field(min_length=1, max_length=1000)
    evidence_slide_numbers: tuple[int, ...] = ()
    follow_up_questions: tuple[str, ...] = ()


class ModelReviewOutput(FrozenModel):
    """Strict model output; it intentionally excludes a final approval decision."""

    criteria: tuple[ModelCriterionFinding, ...]
    recommendation_summary: str = Field(min_length=1, max_length=2000)
    limitations: tuple[str, ...] = ()


class StructuredModelOutputError(ValueError):
    """Raised when a model response violates evidence or rubric boundaries."""


class StructuredModelEvaluator:
    """Use a model for semantic findings while keeping workflow rules deterministic."""

    def __init__(
        self,
        gateway: OpenAICompatibleClient,
        *,
        baseline: OfflineEvidenceEvaluator | None = None,
    ) -> None:
        self.gateway = gateway
        self.baseline = baseline or OfflineEvidenceEvaluator()

    def evaluate_registration(
        self,
        dossier: ProjectDossier,
        snapshot: SnapshotRef,
        evidence: EvidenceDocument,
        profile: ResolvedReviewProfile | None = None,
    ) -> EvaluationReport:
        """Produce evidence-bound semantic registration findings."""

        baseline = self.baseline.evaluate_registration(dossier, snapshot, evidence, profile)
        resolved = profile or self.baseline.default_profile
        return self._augment(
            baseline,
            evidence=evidence,
            policy=resolved.policy.registration,
        )

    def evaluate_completion(
        self,
        dossier: ProjectDossier,
        snapshot: SnapshotRef,
        evidence: EvidenceDocument,
        registration_report: EvaluationReport,
        profile: ResolvedReviewProfile | None = None,
    ) -> EvaluationReport:
        """Produce semantic completion findings while preserving baseline guards."""

        baseline = self.baseline.evaluate_completion(
            dossier,
            snapshot,
            evidence,
            registration_report,
            profile,
        )
        resolved = profile or self.baseline.default_profile
        return self._augment(
            baseline,
            evidence=evidence,
            policy=resolved.policy.completion,
            registration_report=registration_report,
        )

    def _augment(
        self,
        baseline: EvaluationReport,
        *,
        evidence: EvidenceDocument,
        policy: StageReviewPolicy,
        registration_report: EvaluationReport | None = None,
    ) -> EvaluationReport:
        prompt = self._prompt(policy, evidence, registration_report)
        gateway_result = self.gateway.generate_structured(
            instructions=(
                "You are an AX evidence reviewer. Use only the supplied evidence. "
                "Do not infer missing facts, do not provide hidden chain-of-thought, and mark "
                "insufficient_evidence when a claim lacks a cited slide. Return every criterion "
                "exactly once. Write all narrative fields in Korean. Your output is a "
                "non-binding Agent draft for administrator HITL."
            ),
            input_text=prompt,
            schema_name=f"axcalib_{policy.stage.value}_review",
            json_schema=self._json_schema(policy),
        )
        try:
            output = ModelReviewOutput.model_validate_json(gateway_result.output_text)
        except ValueError as error:
            raise StructuredModelOutputError(
                "model output failed AXCalib structured validation"
            ) from error
        criteria = self._materialize(output, policy, evidence, baseline)
        recommendation = self._recommend(policy, criteria)
        if any("proposal_reused_as_final" in item.risk_flags for item in criteria):
            recommendation = AgentRecommendation.NOT_ACCEPT
        seed = "|".join(
            (
                baseline.report_id,
                gateway_result.request_sha256,
                gateway_result.response_sha256,
                self.gateway.config.model,
            )
        )
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
        limitations = [
            item
            for item in baseline.limitations
            if "LLM 또는 VLM 의미평가를 수행하지 않았습니다" not in item
        ]
        limitations.extend(output.limitations)
        if any(
            "model_assessment_downgraded_no_evidence" in item.risk_flags
            for item in criteria
        ):
            limitations.append(
                "locator 없는 모델 판정은 insufficient_evidence로 하향 정규화했습니다."
            )
        limitations.append(
            "모델 finding은 관리자 HITL을 대체하지 않으며 최종 승인·인증을 확정하지 않습니다."
        )
        return baseline.model_copy(
            update={
                "report_id": f"report-{policy.stage.value}-model-{digest[:16]}",
                "run_id": f"run-{policy.stage.value}-model-{digest[16:32]}",
                "evaluator_id": f"{MODEL_EVALUATOR_ID}:{gateway_result.model}",
                "model_run": ModelRunManifest(
                    profile_id=self.gateway.config.profile_id,
                    model=gateway_result.model,
                    api_mode=self.gateway.config.api_mode.value,
                    structured_output_mode=(
                        self.gateway.config.structured_output_mode.value
                    ),
                    max_output_tokens=self.gateway.config.max_output_tokens,
                    capabilities=self.gateway.config.capabilities,
                    request_sha256=gateway_result.request_sha256,
                    response_sha256=gateway_result.response_sha256,
                    response_id=gateway_result.response_id,
                    latency_ms=gateway_result.latency_ms,
                    live=self.gateway.config.live,
                ),
                "criteria": criteria,
                "recommendation": recommendation,
                "recommendation_summary": output.recommendation_summary,
                "limitations": tuple(dict.fromkeys(limitations)),
            }
        )

    @staticmethod
    def _prompt(
        policy: StageReviewPolicy,
        evidence: EvidenceDocument,
        registration_report: EvaluationReport | None = None,
    ) -> str:
        criteria = [
            {
                "criterion_id": item.criterion_id,
                "title": item.title,
                "required_evidence_concepts": list(item.required_tags),
                "critical": item.critical,
            }
            for item in policy.criteria
        ]
        slides = [
            {
                "slide_number": slide.slide_number,
                "text": slide.text[:3000],
                "source": slide.text_source,
            }
            for slide in evidence.slides
            if slide.text
        ]
        payload: dict[str, object] = {
            "stage": policy.stage.value,
            "rubric": f"{policy.rubric_id}@{policy.rubric_version}",
            "criteria": criteria,
            "evidence_slides": slides,
        }
        if registration_report is not None:
            payload["registration_baseline"] = {
                "report_id": registration_report.report_id,
                "snapshot_id": registration_report.snapshot.snapshot_id,
                "snapshot_sha256": registration_report.snapshot.dossier_sha256,
                "criteria": [
                    {
                        "criterion_id": item.criterion_id,
                        "title": item.title,
                        "assessment": item.assessment.value,
                        "observation": item.observation,
                        "evidence_locators": [
                            reference.locator for reference in item.evidence_refs
                        ],
                    }
                    for item in registration_report.criteria
                ],
            }
        return json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
        )

    @staticmethod
    def _json_schema(policy: StageReviewPolicy) -> dict[str, object]:
        return {
            "type": "object",
            "additionalProperties": False,
            "required": ["criteria", "recommendation_summary", "limitations"],
            "properties": {
                "criteria": {
                    "type": "array",
                    "minItems": len(policy.criteria),
                    "maxItems": len(policy.criteria),
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": [
                            "criterion_id",
                            "assessment",
                            "observation",
                            "evidence_slide_numbers",
                            "follow_up_questions",
                        ],
                        "properties": {
                            "criterion_id": {
                                "type": "string",
                                "enum": [item.criterion_id for item in policy.criteria],
                            },
                            "assessment": {
                                "type": "string",
                                "enum": [item.value for item in Assessment],
                            },
                            "observation": {"type": "string", "minLength": 1},
                            "evidence_slide_numbers": {
                                "type": "array",
                                "items": {"type": "integer", "minimum": 1},
                            },
                            "follow_up_questions": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                    },
                },
                "recommendation_summary": {"type": "string", "minLength": 1},
                "limitations": {"type": "array", "items": {"type": "string"}},
            },
        }

    @staticmethod
    def _materialize(
        output: ModelReviewOutput,
        policy: StageReviewPolicy,
        evidence: EvidenceDocument,
        baseline: EvaluationReport,
    ) -> tuple[CriterionResult, ...]:
        expected = {item.criterion_id: item for item in policy.criteria}
        received = [item.criterion_id for item in output.criteria]
        if len(received) != len(set(received)) or set(received) != set(expected):
            raise StructuredModelOutputError(
                "model output must contain every policy criterion exactly once"
            )
        slides = {item.slide_number: item for item in evidence.slides if item.text}
        baseline_by_id = {item.criterion_id: item for item in baseline.criteria}
        materialized: list[CriterionResult] = []
        baseline_link = baseline_by_id.get("COM-REGISTRATION-BASELINE")
        if baseline_link is not None:
            materialized.append(baseline_link)
        for finding in output.criteria:
            definition = expected[finding.criterion_id]
            unknown = set(finding.evidence_slide_numbers) - set(slides)
            if unknown:
                raise StructuredModelOutputError(
                    f"model cited unavailable evidence slides for {finding.criterion_id}"
                )
            evidence_required = {
                Assessment.MET,
                Assessment.PARTIALLY_MET,
                Assessment.NOT_MET,
            }
            assessment = finding.assessment
            downgraded = assessment in evidence_required and not (
                finding.evidence_slide_numbers
            )
            if downgraded:
                assessment = Assessment.INSUFFICIENT_EVIDENCE
            deterministic = baseline_by_id.get(finding.criterion_id)
            if deterministic and "proposal_reused_as_final" in deterministic.risk_flags:
                materialized.append(deterministic)
                continue
            refs = tuple(
                EvidenceLocator(
                    artifact_id=evidence.artifact.artifact_id,
                    locator=f"{evidence.artifact.uri}#slide={slide_number}",
                    excerpt=slides[slide_number].text[:500],
                    source=slides[slide_number].text_source,
                )
                for slide_number in finding.evidence_slide_numbers
            )
            risk_flags: list[str] = []
            if definition.critical and assessment is not Assessment.MET:
                risk_flags.append("critical_evidence_gap")
            if downgraded:
                risk_flags.append("model_assessment_downgraded_no_evidence")
            questions = finding.follow_up_questions
            if assessment is not Assessment.MET and not questions:
                questions = (definition.follow_up,)
            observation = finding.observation
            if downgraded:
                observation = (
                    f"모델의 {finding.assessment.value} 판정에 source locator가 없어 "
                    "insufficient_evidence로 하향했습니다. "
                    + observation
                )
            materialized.append(
                CriterionResult(
                    criterion_id=finding.criterion_id,
                    title=definition.title,
                    assessment=assessment,
                    observation=observation,
                    evidence_refs=refs,
                    risk_flags=tuple(risk_flags),
                    follow_up_questions=questions,
                )
            )
        return tuple(materialized)

    @staticmethod
    def _recommend(
        policy: StageReviewPolicy,
        criteria: tuple[CriterionResult, ...],
    ) -> AgentRecommendation:
        by_id = {item.criterion_id: item for item in criteria}
        failure = {Assessment.NOT_MET, Assessment.INSUFFICIENT_EVIDENCE}
        for definition in policy.criteria:
            if (
                definition.blocking_recommendation is not None
                and by_id[definition.criterion_id].assessment in failure
            ):
                return definition.blocking_recommendation
        if any(
            by_id[definition.criterion_id].assessment is not Assessment.MET
            for definition in policy.criteria
        ):
            return policy.gap_recommendation
        return policy.all_met_recommendation


__all__ = [
    "MODEL_EVALUATOR_ID",
    "ModelCriterionFinding",
    "ModelReviewOutput",
    "StructuredModelEvaluator",
    "StructuredModelOutputError",
]
