from pathlib import Path

from axcalib import AXCalib
from examples.education_project_lifecycle.run_full_lifecycle import run


def test_actual_ppt_project_rolls_up_to_program_completion(tmp_path: Path) -> None:
    result = run(tmp_path / "education-lifecycle")

    assert result["synthetic"] is True
    assert result["project_status"] == "completion_accepted"
    assert result["completion_recommendation"] == "accept"
    assert result["enrollment_status"] == "completed"
    assert result["project_notification_count"] == 2
    assert result["program_notification_count"] == 1
    assert result["milestones"] == {
        "orientation": "completed",
        "oled-project-certification": "completed",
        "final-reflection": "completed",
    }
    reloaded = AXCalib(tmp_path / "education-lifecycle")
    enrollment = reloaded.education.enrollments.load(str(result["enrollment_id"]))
    assert enrollment.completion_decisions[-1].authority_context == "offline_unverified_actor"
    outbox_entries = reloaded.service.notifier.entries()
    assert len(outbox_entries) == 3
    assert all(entry["revision"] for entry in outbox_entries)
    assert all(entry["report_ref"] for entry in outbox_entries)
