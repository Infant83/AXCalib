"""Deterministic evidence-tag evaluator for the first offline vertical slice."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from axcalib.retrieval import CaseRetriever, NullRetriever
from axcalib.schemas import (
    AgentRecommendation,
    Assessment,
    CriterionResult,
    EvaluationReport,
    EvidenceDocument,
    EvidenceLocator,
    ProjectDossier,
    RetrievalSummary,
    ReviewStage,
    SnapshotRef,
)

EVALUATOR_ID = "axcalib.offline-evidence-tags/v1"


@dataclass(frozen=True, slots=True)
class CriterionDefinition:
    """Small deterministic criterion definition."""

    criterion_id: str
    title: str
    required_tags: tuple[str, ...]
    follow_up: str
    critical: bool = False


REGISTRATION_CRITERIA = (
    CriterionDefinition(
        "REG-PROBLEM-GOAL",
        "문제와 AX 목표",
        ("problem", "goal"),
        "해결하려는 문제와 목표를 한 문장씩 명시해 주십시오.",
        True,
    ),
    CriterionDefinition(
        "REG-SCOPE-METHOD",
        "범위와 접근방법",
        ("scope", "method"),
        "포함·제외 범위와 핵심 방법을 구분해 주십시오.",
    ),
    CriterionDefinition(
        "REG-PLAN-VALIDATION",
        "로드맵과 검증계획",
        ("roadmap", "validation_plan"),
        "단계별 종료조건과 검증 책임자를 추가해 주십시오.",
    ),
    CriterionDefinition(
        "REG-KPI",
        "정량 KPI와 측정방법",
        ("kpi_plan", "quantitative_target"),
        "KPI별 baseline, target, unit, period와 측정방법을 제시해 주십시오.",
        True,
    ),
    CriterionDefinition(
        "REG-RISK",
        "위험과 한계",
        ("risk", "limitation"),
        "위험별 대응책, owner와 중단조건을 연결해 주십시오.",
    ),
    CriterionDefinition(
        "REG-DATA-GOVERNANCE",
        "데이터·보안·윤리",
        ("data", "security"),
        "데이터 출처, 접근등급, 개인정보와 외부전송 정책을 명시해 주십시오.",
        True,
    ),
    CriterionDefinition(
        "REG-ROLE-RESOURCE",
        "역할과 자원",
        ("role", "resource"),
        "과제 owner, 평가자, 필요한 인력·시스템·예산을 명시해 주십시오.",
    ),
)

COMPLETION_CRITERIA = (
    CriterionDefinition(
        "COM-DELIVERABLE",
        "완료 산출물과 작동 증거",
        ("deliverable", "result"),
        "실제 산출물 URI/hash, 실행 로그와 검증 결과를 제출해 주십시오.",
        True,
    ),
    CriterionDefinition(
        "COM-KPI",
        "KPI 관측값과 달성도",
        ("result", "quantitative_target"),
        "관측값, 단위, 기간, 측정방법과 원문 locator를 제출해 주십시오.",
        True,
    ),
    CriterionDefinition(
        "COM-EXECUTION",
        "수행·재현 증거",
        ("result", "reproducibility"),
        "버전, 환경, 테스트 및 재실행 절차를 제출해 주십시오.",
        True,
    ),
    CriterionDefinition(
        "COM-CHANGE",
        "등록안 대비 변경",
        ("change",),
        "등록 baseline 대비 변경과 승인 여부를 명시해 주십시오.",
    ),
    CriterionDefinition(
        "COM-RISK-FOLLOWUP",
        "완료 시점 위험과 후속계획",
        ("risk", "limitation"),
        "남은 위험, 운영 한계와 후속 책임자를 명시해 주십시오.",
    ),
)


class OfflineEvidenceEvaluator:
    """Produce traceable draft reports without a model or embeddings."""

    def __init__(
        self,
        retriever: CaseRetriever | None = None,
        *,
        registration_similarity_portion: float = 0.0,
        completion_similarity_portion: float = 0.0,
    ) -> None:
        for portion in (registration_similarity_portion, completion_similarity_portion):
            if not 0.0 <= portion <= 0.25:
                raise ValueError("offline similarity portions must be between 0.0 and 0.25")
        self._retriever = retriever or NullRetriever()
        self._similarity_portions = {
            ReviewStage.REGISTRATION: registration_similarity_portion,
            ReviewStage.COMPLETION: completion_similarity_portion,
        }

    def evaluate_registration(
        self,
        dossier: ProjectDossier,
        snapshot: SnapshotRef,
        evidence: EvidenceDocument,
    ) -> EvaluationReport:
        """Evaluate a proposal and create a non-binding registration recommendation."""

        criteria = tuple(
            self._evaluate_definition(definition, evidence)
            for definition in REGISTRATION_CRITERIA
        )
        by_id = {item.criterion_id: item for item in criteria}
        if by_id["REG-PROBLEM-GOAL"].assessment is Assessment.INSUFFICIENT_EVIDENCE:
            recommendation = AgentRecommendation.REJECT
            summary = "핵심 문제와 목표 근거가 없어 등록심의 반려 제안입니다."
        elif any(
            by_id[criterion_id].assessment
            in {
                Assessment.PARTIALLY_MET,
                Assessment.INSUFFICIENT_EVIDENCE,
                Assessment.NOT_MET,
            }
            for criterion_id in ("REG-KPI", "REG-DATA-GOVERNANCE")
        ) or any(item.assessment is Assessment.INSUFFICIENT_EVIDENCE for item in criteria):
            recommendation = AgentRecommendation.NEEDS_CHANGES
            summary = "접근방법은 확인되지만 KPI·거버넌스·역할 근거 보완이 필요합니다."
        else:
            recommendation = AgentRecommendation.PASS
            summary = "등록심의 기준을 충족한다는 Agent 제안이며 관리자 확인이 필요합니다."
        return self._report(
            dossier=dossier,
            stage=ReviewStage.REGISTRATION,
            snapshot=snapshot,
            evidence=evidence,
            criteria=criteria,
            recommendation=recommendation,
            summary=summary,
            rubric_id="axcalib.registration-checklist",
            rubric_version="0.1.0",
        )

    def evaluate_completion(
        self,
        dossier: ProjectDossier,
        snapshot: SnapshotRef,
        evidence: EvidenceDocument,
        registration_report: EvaluationReport,
    ) -> EvaluationReport:
        """Compare final evidence with the approved registration baseline."""

        proposal = next(
            artifact for artifact in dossier.artifacts if artifact.role == "registration_proposal"
        )
        same_artifact = proposal.sha256 == evidence.artifact.sha256
        baseline = CriterionResult(
            criterion_id="COM-REGISTRATION-BASELINE",
            title="승인된 등록 baseline 연결",
            assessment=Assessment.MET,
            observation=(
                f"등록 보고서 {registration_report.report_id}와 snapshot "
                f"{registration_report.snapshot.snapshot_id}를 비교 기준으로 사용했습니다."
            ),
            evidence_refs=(
                EvidenceLocator(
                    artifact_id=proposal.artifact_id,
                    locator=f"report:{registration_report.report_id}",
                    excerpt=registration_report.recommendation_summary,
                    source="registration_report",
                ),
            ),
        )
        criteria = [baseline]
        criteria.extend(
            self._evaluate_definition(definition, evidence)
            for definition in COMPLETION_CRITERIA
        )
        if same_artifact:
            criteria[1] = CriterionResult(
                criterion_id="COM-DELIVERABLE",
                title="완료 산출물과 작동 증거",
                assessment=Assessment.NOT_MET,
                observation=(
                    "완료 제출 파일의 SHA-256이 등록 제안서와 동일하여 수행 결과물로 확인할 "
                    "수 없습니다."
                ),
                evidence_refs=(
                    EvidenceLocator(
                        artifact_id=evidence.artifact.artifact_id,
                        locator=f"artifact:sha256={evidence.artifact.sha256}",
                        excerpt="등록 제안서와 완료 제출 파일의 content hash가 동일합니다.",
                        source="deterministic_hash_comparison",
                    ),
                ),
                risk_flags=("proposal_reused_as_final",),
                follow_up_questions=(
                    "실제 수행 산출물, 코드·실험 로그와 결과 보고서를 별도로 제출해 주십시오.",
                ),
            )
        critical_failures = {"COM-DELIVERABLE", "COM-KPI", "COM-EXECUTION"}
        if same_artifact or any(
            item.criterion_id in critical_failures
            and item.assessment
            in {Assessment.NOT_MET, Assessment.INSUFFICIENT_EVIDENCE}
            for item in criteria
        ):
            recommendation = AgentRecommendation.NOT_ACCEPT
            summary = (
                "제안서를 최종안으로 재사용해 수행·KPI·산출물 증거가 부족하므로 "
                "미수용 제안입니다."
            )
        elif any(
            item.assessment in {
                Assessment.PARTIALLY_MET,
                Assessment.INSUFFICIENT_EVIDENCE,
            }
            for item in criteria
        ):
            recommendation = AgentRecommendation.NEEDS_CHANGES
            summary = "완료평가 전 추가 수행증거가 필요합니다."
        else:
            recommendation = AgentRecommendation.ACCEPT
            summary = "완료평가 수용 Agent 제안이며 관리자 최종 확인이 필요합니다."
        return self._report(
            dossier=dossier,
            stage=ReviewStage.COMPLETION,
            snapshot=snapshot,
            evidence=evidence,
            criteria=tuple(criteria),
            recommendation=recommendation,
            summary=summary,
            rubric_id="axcalib.completion-checklist",
            rubric_version="0.1.0",
            baseline_report_id=registration_report.report_id,
            proposal_artifact_sha256=proposal.sha256,
        )

    def _evaluate_definition(
        self,
        definition: CriterionDefinition,
        evidence: EvidenceDocument,
    ) -> CriterionResult:
        present = set().union(*(set(slide.tags) for slide in evidence.slides))
        matched = [tag for tag in definition.required_tags if tag in present]
        if len(matched) == len(definition.required_tags):
            assessment = Assessment.MET
            observation = "요구 요소를 모두 확인했습니다: " + ", ".join(matched)
        elif matched:
            assessment = Assessment.PARTIALLY_MET
            missing = [tag for tag in definition.required_tags if tag not in present]
            observation = (
                "일부 근거만 확인했습니다. 확인: "
                + ", ".join(matched)
                + "; 부족: "
                + ", ".join(missing)
            )
        else:
            assessment = Assessment.INSUFFICIENT_EVIDENCE
            observation = "제출자료에서 이 기준을 판단할 근거를 찾지 못했습니다."
        refs = self._locators(evidence, set(matched or definition.required_tags))
        risk_flags = (
            ("critical_evidence_gap",)
            if definition.critical and assessment is not Assessment.MET
            else ()
        )
        questions = () if assessment is Assessment.MET else (definition.follow_up,)
        return CriterionResult(
            criterion_id=definition.criterion_id,
            title=definition.title,
            assessment=assessment,
            observation=observation,
            evidence_refs=refs,
            risk_flags=risk_flags,
            follow_up_questions=questions,
        )

    @staticmethod
    def _locators(
        evidence: EvidenceDocument,
        tags: set[str],
    ) -> tuple[EvidenceLocator, ...]:
        refs: list[EvidenceLocator] = []
        for slide in evidence.slides:
            if tags.intersection(slide.tags) and slide.text:
                refs.append(
                    EvidenceLocator(
                        artifact_id=evidence.artifact.artifact_id,
                        locator=f"{evidence.artifact.uri}#slide={slide.slide_number}",
                        excerpt=slide.text[:500],
                        source=slide.text_source,
                    )
                )
            if len(refs) == 3:
                break
        return tuple(refs)

    def _report(
        self,
        *,
        dossier: ProjectDossier,
        stage: ReviewStage,
        snapshot: SnapshotRef,
        evidence: EvidenceDocument,
        criteria: tuple[CriterionResult, ...],
        recommendation: AgentRecommendation,
        summary: str,
        rubric_id: str,
        rubric_version: str,
        baseline_report_id: str | None = None,
        proposal_artifact_sha256: str | None = None,
    ) -> EvaluationReport:
        seed = "|".join(
            (
                dossier.project_id,
                stage.value,
                str(snapshot.dossier_revision),
                snapshot.dossier_sha256,
                evidence.artifact.sha256,
                EVALUATOR_ID,
            )
        )
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
        retrieval = self._retriever.search(evidence.text, stage=stage.value, limit=5)
        limitations = [
            "결정론적 tag/checklist baseline이며 LLM 또는 VLM 의미평가를 수행하지 않았습니다.",
            "embedding/Vector DB가 없어 similarity portion은 0.0입니다.",
        ]
        if any("sidecar" in slide.text_source for slide in evidence.slides):
            limitations.append(
                "image-only slide는 원본 hash에 고정된 검토 sidecar 요약을 사용했습니다."
            )
        limitations.extend(evidence.warnings)
        return EvaluationReport(
            report_id=f"report-{stage.value}-{digest[:16]}",
            run_id=f"run-{stage.value}-{digest[16:32]}",
            project_id=dossier.project_id,
            stage=stage,
            base_revision=snapshot.dossier_revision,
            snapshot=snapshot,
            rubric_id=rubric_id,
            rubric_version=rubric_version,
            evaluator_id=EVALUATOR_ID,
            criteria=criteria,
            recommendation=recommendation,
            recommendation_summary=summary,
            retrieval=RetrievalSummary(
                status=retrieval.status,
                adapter=retrieval.adapter,
                similarity_portion=self._similarity_portions[stage],
                corpus_snapshot_id=retrieval.corpus_snapshot_id,
                case_ids=tuple(hit.case_id for hit in retrieval.hits),
            ),
            baseline_report_id=baseline_report_id,
            proposal_artifact_sha256=proposal_artifact_sha256,
            evaluated_artifact_sha256=evidence.artifact.sha256,
            limitations=tuple(dict.fromkeys(limitations)),
        )
