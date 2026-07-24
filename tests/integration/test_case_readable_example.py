"""Actual proposal plus synthetic completion example through the public Case facade."""

from pathlib import Path

from axcalib import AXCalib
from axcalib.schemas import AgentRecommendation, CaseSummary
from axcalib.workflows.two_gate import ProjectStatus
from examples.case_lifecycle.run_readable_pass import run_example
from examples.library_mvp_alpha_quickstart import run as run_quickstart

ROOT = Path(__file__).resolve().parents[2]
PROPOSAL = ROOT / "tests" / "sources" / "oled_qc_project_outline.pptx"
SIDECAR = ROOT / "tests" / "sources" / "oled_qc_project_outline.axcalib.json"


def test_quickstart_stops_at_hitl_and_omits_local_storage_paths(tmp_path: Path) -> None:
    result = run_quickstart(
        workspace=tmp_path / "quickstart",
        proposal=PROPOSAL,
        sidecar=SIDECAR,
        project_id="quickstart-integration-001",
    )

    assert result["status"] == "registration_hitl_pending"
    assert result["pipeline_status"] == "waiting_human"
    assert result["report_id"]
    assert "dossier_uri" not in result
    assert "report_json_uri" not in result
    assert "report_markdown_uri" not in result
    assert str(tmp_path.resolve()) not in str(result)


def test_readable_pass_example_connects_agent_and_human_results(tmp_path: Path) -> None:
    workspace = tmp_path / "readable-pass"
    summary = run_example(workspace, project_id="readable-pass-integration-001")

    assert summary.dossier_status is ProjectStatus.COMPLETION_ACCEPTED
    assert summary.registration.agent_recommendation is AgentRecommendation.PASS
    assert summary.registration.human_decision is not None
    assert summary.registration.human_decision.command == "approve"
    assert summary.completion.agent_recommendation is AgentRecommendation.ACCEPT
    assert summary.completion.human_decision is not None
    assert summary.completion.human_decision.command == "accept"
    assert summary.execution.mentor_assigned is True
    assert summary.execution.progress_note_count == 1
    assert summary.notification_count == 2

    for name in (
        "01-registration-hitl-pending.md",
        "02-completion-hitl-pending.md",
        "03-final-summary.md",
        "03-final-summary.json",
        "run-result.json",
    ):
        assert (workspace / "views" / name).is_file()
    registration_pending = (workspace / "views" / "01-registration-hitl-pending.md").read_text(
        encoding="utf-8"
    )
    final_markdown = (workspace / "views" / "03-final-summary.md").read_text(encoding="utf-8")
    assert "사람 결정: **대기 또는 미결정**" in registration_pending
    assert "| registration | pass | approve |" in final_markdown
    assert "| completion | accept | accept |" in final_markdown
    assert str(workspace.resolve()) not in final_markdown

    reopened = AXCalib(workspace).open_case(summary.project_id)
    reloaded = reopened.get_summary()
    assert isinstance(reloaded, CaseSummary)
    assert reloaded.dossier_status is ProjectStatus.COMPLETION_ACCEPTED
