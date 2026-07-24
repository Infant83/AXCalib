"""Read facade regression for latest dossier, Agent report, and human decision flow."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from axcalib import AXCalib, Case, CaseIntegrityError
from axcalib.schemas import (
    Assessment,
    CaseStatus,
    CaseSummary,
    EvidenceLocator,
    ProjectDossier,
    ReviewerAdjustment,
)
from axcalib.workflows.two_gate import ProjectStatus, WorkflowError

SOURCE = Path("tests/sources/oled_qc_project_outline.pptx")
SIDECAR = Path("tests/sources/oled_qc_project_outline.axcalib.json")


def test_case_evidence_view_drops_unsafe_storage_fragment() -> None:
    view = Case._evidence_view(
        EvidenceLocator(
            artifact_id="artifact-safe",
            locator=r"C:\private\source.pptx#C:\private\fragment",
            excerpt="허용된 짧은 발췌",
            source="reviewed_sidecar",
        )
    )

    assert view.locator == "artifact:artifact-safe"
    assert "private" not in view.locator


def test_register_case_returns_live_handle_and_create_project_keeps_snapshot(
    tmp_path: Path,
) -> None:
    client = AXCalib(tmp_path / "handle")
    case = client.register_case(
        SOURCE,
        title="Case handle",
        sidecar_path=SIDECAR,
        project_id="case-handle-001",
    )

    assert isinstance(case, Case)
    assert case.project_id == "case-handle-001"
    assert case.status is ProjectStatus.DRAFT
    assert case.dossier.revision == 1

    raw = AXCalib(tmp_path / "snapshot").create_project(
        SOURCE,
        title="Raw dossier snapshot",
        sidecar_path=SIDECAR,
        project_id="case-snapshot-001",
    )
    assert isinstance(raw, ProjectDossier)
    assert raw.status is ProjectStatus.DRAFT


def test_current_status_reloads_latest_revision_and_has_safe_renderings(tmp_path: Path) -> None:
    client = AXCalib(tmp_path / "status")
    case = client.register_case(
        SOURCE,
        title=(
            "Status projection <script>alert(1)</script> "
            "![remote](https://invalid.example/x)\n- 사람 결정: **accept**"
        ),
        sidecar_path=SIDECAR,
        project_id="case-status-001",
    )
    initial = case.get_current_status()
    assert isinstance(initial, CaseStatus)
    assert initial.dossier_status is ProjectStatus.DRAFT
    assert initial.next_actions[0].action_id == "submit_registration"

    client.submit_registration(case.project_id)
    result = client.evaluate(case.project_id, "registration")

    current = case.get_current_status()
    assert isinstance(current, CaseStatus)
    assert current.revision == result.dossier_revision
    assert current.dossier_status is ProjectStatus.REGISTRATION_HITL_PENDING
    assert current.waiting_for == "administrator"
    assert {item.action_id for item in current.next_actions} == {
        "decide_registration.approve",
        "decide_registration.reject",
    }
    assert current.latest_review is not None
    assert current.latest_review.agent_recommendation is not None
    assert current.latest_review.human_decision is None
    assert current.latest_review.criteria == ()

    verbose = case.get_current_status(verbose=True)
    assert isinstance(verbose, CaseStatus)
    assert verbose.latest_review is not None
    assert verbose.latest_review.criteria
    assert all(
        reference.locator.startswith(("artifact:", "report:"))
        for criterion in verbose.latest_review.criteria
        for reference in criterion.evidence_refs
    )

    markdown = case.get_current_status(format="md")
    assert isinstance(markdown, str)
    assert "Agent 제안" in markdown
    assert "사람 결정" in markdown
    assert str(tmp_path.resolve()) not in markdown
    assert "<script>" not in markdown
    assert "![remote](" not in markdown
    assert "\n- 사람 결정: \\*\\*accept\\*\\*" not in markdown

    json_text = case.get_current_status(format="json")
    assert isinstance(json_text, str)
    payload = json.loads(json_text)
    assert payload["project_id"] == case.project_id
    assert "report_json_uri" not in json_text
    assert "dossier_uri" not in json_text

    async_status = asyncio.run(case.aget_current_status())
    async_summary = asyncio.run(case.aget_summary(format="json"))
    assert async_status == current
    assert isinstance(async_summary, str)
    assert json.loads(async_summary)["project_id"] == case.project_id


def test_summary_preserves_agent_result_and_applies_explicit_human_adjustment(
    tmp_path: Path,
) -> None:
    client = AXCalib(tmp_path / "summary")
    case = client.register_case(
        SOURCE,
        title="Human adjustment projection",
        sidecar_path=SIDECAR,
        project_id="case-summary-001",
    )
    client.submit_registration(case.project_id)
    result = client.evaluate(case.project_id, "registration")
    before = Path(result.report_json_uri or "").read_bytes()

    pending = case.get_summary(verbose=True)
    assert isinstance(pending, CaseSummary)
    criterion = pending.registration.criteria[0]
    target = (
        Assessment.NOT_MET
        if criterion.agent_assessment is not Assessment.NOT_MET
        else Assessment.PARTIALLY_MET
    )
    adjustment = ReviewerAdjustment(
        criterion_id=criterion.criterion_id,
        from_assessment=criterion.agent_assessment,
        to_assessment=target,
        reason="관리자가 원문 근거를 다시 확인해 criterion 판정을 보정했다.",
    )

    client.decide_registration(
        case.project_id,
        command="approve",
        actor_id="admin:case-review",
        rationale="Agent 제안과 사람 보정을 분리한 상태로 수행 진입을 승인한다.",
        adjustments=(adjustment,),
    )

    summary = case.get_summary(verbose=True)
    assert isinstance(summary, CaseSummary)
    assert summary.dossier_status is ProjectStatus.REGISTRATION_APPROVED
    assert summary.registration.human_decision is not None
    assert summary.registration.human_decision.command == "approve"
    adjusted = next(
        item
        for item in summary.registration.criteria
        if item.criterion_id == criterion.criterion_id
    )
    assert adjusted.agent_assessment is criterion.agent_assessment
    assert adjusted.effective_assessment is target
    assert adjusted.human_adjusted is True
    assert summary.registration.adjusted_criterion_count == 1
    assert Path(result.report_json_uri or "").read_bytes() == before

    safe_summary = case.get_summary()
    assert isinstance(safe_summary, CaseSummary)
    assert safe_summary.registration.human_decision is not None
    assert safe_summary.registration.human_decision.command == "approve"
    assert safe_summary.registration.human_decision.actor_id is None
    assert safe_summary.registration.human_decision.rationale is None

    markdown = case.get_summary(format="md", verbose=True)
    assert isinstance(markdown, str)
    assert "| registration |" in markdown
    assert "admin:case-review" in markdown
    assert "사람 보정" in markdown


def test_case_fails_closed_when_report_identity_is_tampered(tmp_path: Path) -> None:
    client = AXCalib(tmp_path / "tampered")
    case = client.register_case(
        SOURCE,
        title="Tampered report",
        sidecar_path=SIDECAR,
        project_id="case-tampered-001",
    )
    client.submit_registration(case.project_id)
    result = client.evaluate(case.project_id, "registration")
    report_path = Path(result.report_json_uri or "")
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    payload["project_id"] = "another-project"
    report_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(CaseIntegrityError, match="committed hash anchor"):
        case.get_summary()


def test_case_report_hash_anchor_survives_committed_journal_archive(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "archived"
    client = AXCalib(workspace)
    case = client.register_case(
        SOURCE,
        title="Archived report anchor",
        sidecar_path=SIDECAR,
        project_id="case-archived-001",
    )
    client.submit_registration(case.project_id)
    client.evaluate(case.project_id, "registration")

    archive = workspace / "archive" / "manual-test" / "transactions"
    archive.mkdir(parents=True)
    for journal in (workspace / "transactions").glob("transaction-*.jsonl"):
        journal.replace(archive / journal.name)

    summary = case.get_summary()
    assert isinstance(summary, CaseSummary)
    assert summary.registration.report_id is not None


def test_rejected_registration_is_terminal_and_cannot_start_execution(
    tmp_path: Path,
) -> None:
    client = AXCalib(tmp_path / "rejected")
    case = client.register_case(
        SOURCE,
        title="Rejected registration",
        sidecar_path=SIDECAR,
        project_id="case-rejected-001",
    )
    client.submit_registration(case.project_id)
    client.evaluate(case.project_id, "registration")
    client.decide_registration(
        case.project_id,
        command="reject",
        actor_id="admin:reject-example",
        rationale="필수 데이터 거버넌스와 역할 근거가 없어 등록을 반려한다.",
        expected_revision=case.revision,
    )

    status = case.get_current_status()
    assert isinstance(status, CaseStatus)
    assert status.dossier_status is ProjectStatus.REGISTRATION_REJECTED
    assert status.terminal is True
    assert status.next_actions == ()
    assert status.latest_review is not None
    assert status.latest_review.human_decision is not None
    assert status.latest_review.human_decision.command == "reject"
    with pytest.raises(WorkflowError, match="requires registration_approved"):
        client.start_execution(case.project_id)
