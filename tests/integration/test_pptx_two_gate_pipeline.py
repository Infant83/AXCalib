import asyncio
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from axcalib import AXCalib
from axcalib.notifications.base import NotificationEvent
from axcalib.pipelines import TwoGatePptxRequest
from axcalib.schemas import AgentRecommendation, Assessment, EvaluationReport, PipelineStatus
from axcalib.workflows.two_gate import ProjectStatus

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tests" / "sources" / "oled_qc_project_outline.pptx"
SIDECAR = ROOT / "tests" / "sources" / "oled_qc_project_outline.axcalib.json"
CONFIG = ROOT / "config" / "axcalib.toml"
CASES = ROOT / "fixtures" / "synthetic" / "historical_cases.json"


def _client(workspace: Path) -> AXCalib:
    return AXCalib.from_toml(
        CONFIG,
        workspace=workspace,
        historical_cases_path=CASES,
    )


def _report(path: str | None) -> EvaluationReport:
    assert path is not None
    json_path = Path(path).with_suffix(".json")
    return EvaluationReport.model_validate_json(json_path.read_text(encoding="utf-8"))


def test_supplied_pptx_runs_both_gates_with_explicit_human_decisions(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path / "workflow")
    request = TwoGatePptxRequest(
        proposal_path=SOURCE,
        proposal_sidecar_path=SIDECAR,
        final_path=SOURCE,
        final_sidecar_path=SIDECAR,
        title="OLED QC 양자-고전 하이브리드 분자설계 과제",
        project_id="pptx-two-gate-integration-001",
        registration_decision="approve",
        registration_rationale=(
            "Agent 보완 의견을 확인했다. 동일 파일 완료평가 실패 경로를 검증하는 "
            "offline 통합 테스트에 한해 등록을 승인한다."
        ),
        completion_decision="not_accept",
        completion_rationale=(
            "제안서와 최종안의 hash가 같고 수행·KPI·산출물 증거가 없어 수용하지 않는다."
        ),
    )

    summary = client.run_pptx(request)

    assert summary.final_status is ProjectStatus.COMPLETION_NOT_ACCEPTED
    assert summary.notification_count == 2
    assert summary.registration_decision is not None
    assert summary.registration_decision.source == "explicit_command_input"
    assert summary.registration_decision.authority_context == "offline_unverified_actor"
    assert summary.completion_decision is not None
    assert Path(summary.dossier_uri).is_file()
    assert Path(summary.registration_report_uri).is_file()
    assert summary.completion_report_uri is not None
    assert Path(summary.completion_report_uri).is_file()

    registration = _report(summary.registration_report_uri)
    assert registration.recommendation is AgentRecommendation.NEEDS_CHANGES
    assert registration.retrieval.adapter == "lexical"
    assert registration.retrieval.similarity_portion == 0.0
    role_resource = next(
        item for item in registration.criteria if item.criterion_id == "REG-ROLE-RESOURCE"
    )
    assert role_resource.assessment is Assessment.INSUFFICIENT_EVIDENCE

    completion = _report(summary.completion_report_uri)
    assert completion.recommendation is AgentRecommendation.NOT_ACCEPT
    assert completion.proposal_artifact_sha256 == completion.evaluated_artifact_sha256
    deliverable = next(
        item for item in completion.criteria if item.criterion_id == "COM-DELIVERABLE"
    )
    assert deliverable.assessment is Assessment.NOT_MET
    assert "proposal_reused_as_final" in deliverable.risk_flags

    audit_lines = Path(summary.audit_uri).read_text(encoding="utf-8").splitlines()
    assert len(audit_lines) == 8
    events = [json.loads(line) for line in audit_lines]
    assert [event["event_type"] for event in events].count("registration_decided") == 1
    assert [event["event_type"] for event in events].count("completion_decided") == 1


def test_workflow_stops_at_registration_hitl_without_a_decision(tmp_path: Path) -> None:
    client = _client(tmp_path / "waiting")
    summary = client.run_pptx(
        TwoGatePptxRequest(
            proposal_path=SOURCE,
            proposal_sidecar_path=SIDECAR,
            title="관리자 대기 테스트",
            project_id="pptx-waiting-human-001",
        )
    )

    assert summary.final_status is ProjectStatus.REGISTRATION_HITL_PENDING
    assert summary.notification_count == 1
    assert summary.registration_decision is None
    assert summary.completion_report_uri is None


def test_async_workflow_has_the_same_human_wait_semantics(tmp_path: Path) -> None:
    client = _client(tmp_path / "async-waiting")
    summary = asyncio.run(
        client.arun_pptx(
            TwoGatePptxRequest(
                proposal_path=SOURCE,
                proposal_sidecar_path=SIDECAR,
                title="비동기 관리자 대기 테스트",
                project_id="pptx-async-waiting-001",
            )
        )
    )

    assert summary.final_status is ProjectStatus.REGISTRATION_HITL_PENDING
    assert summary.notification_count == 1
    assert summary.registration_decision is None


def test_progress_updates_accumulate_in_the_single_dossier(tmp_path: Path) -> None:
    client = _client(tmp_path / "progress")
    dossier = client.create_project(
        SOURCE,
        title="진행기록 테스트",
        sidecar_path=SIDECAR,
        project_id="pptx-progress-001",
    )
    client.submit_registration(dossier.project_id)
    client.evaluate(dossier.project_id, "registration")
    client.decide_registration(
        dossier.project_id,
        command="approve",
        actor_id="admin:test",
        rationale="offline 진행기록 회귀 테스트를 승인한다.",
    )
    client.start_execution(dossier.project_id)

    result = client.record_progress(
        dossier.project_id,
        note="첫 번째 검증 실험의 입력 조건을 고정했다.",
    )

    assert result.status is PipelineStatus.SUCCEEDED
    updated = client.service.dossiers.load(dossier.project_id)
    assert updated.execution.notes == ("첫 번째 검증 실험의 입력 조건을 고정했다.",)


def test_completion_decision_cannot_bypass_registration_approval(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="requires explicit registration approval"):
        TwoGatePptxRequest(
            proposal_path=SOURCE,
            title="금지된 우회",
            completion_decision="accept",
            completion_rationale="허용되지 않아야 한다.",
        )


class FailingNotifier:
    def send(self, event: NotificationEvent) -> None:
        del event
        raise RuntimeError("recording adapter unavailable")


def test_notification_failure_keeps_registration_out_of_hitl_pending(
    tmp_path: Path,
) -> None:
    client = AXCalib(tmp_path / "fail-closed", notifier=FailingNotifier())
    dossier = client.service.create_project(
        SOURCE,
        title="알림 fail-closed",
        sidecar_path=SIDECAR,
        project_id="notification-failure-001",
    )
    client.service.submit_registration(dossier.project_id)

    with pytest.raises(RuntimeError, match="adapter unavailable"):
        client.evaluate(dossier.project_id, "registration")

    unchanged = client.service.dossiers.load(dossier.project_id)
    assert unchanged.status is ProjectStatus.REGISTRATION_READY
    assert unchanged.notifications == ()
