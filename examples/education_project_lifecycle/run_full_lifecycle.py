"""Run the actual-PPT education project lifecycle using only AXCalib library calls."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from axcalib import AXCalib  # noqa: E402
from axcalib.pipelines import (  # noqa: E402
    BindProjectCommand,
    DecideProgramCompletionCommand,
    EnrollCommand,
    ManualConfirmationCommand,
    RecordScoreCommand,
    StartMilestoneCommand,
    SyncProjectCommand,
)
from axcalib.programs import load_program  # noqa: E402
from axcalib.schemas import EvaluationReport, ReviewContext  # noqa: E402

PROGRAM = ROOT / "fixtures" / "synthetic" / "education_project_lifecycle" / "program.yaml"
PROPOSAL = ROOT / "tests" / "sources" / "oled_qc_project_outline.pptx"
PROPOSAL_SIDECAR = (
    ROOT / "tests" / "sources" / "oled_qc_project_outline.axcalib.json"
)
COMPLETION = (
    ROOT
    / "fixtures"
    / "synthetic"
    / "education_project_lifecycle"
    / "completion_report.synthetic.pptx"
)
COMPLETION_SIDECAR = COMPLETION.with_suffix(".axcalib.json")

ENROLLMENT_ID = "edu-oled-learner-001"
PROJECT_ID = "edu-oled-project-001"
LEARNER_ID = "learner:synthetic-001"


def _report(path: str | None) -> EvaluationReport:
    if path is None:
        raise RuntimeError("expected report path is missing")
    return EvaluationReport.model_validate_json(
        Path(path).with_suffix(".json").read_text(encoding="utf-8")
    )


def run(workspace: Path) -> dict[str, object]:
    """Execute one fresh, explicit human-decision example."""

    client = AXCalib.from_toml(
        ROOT / "config" / "axcalib.toml",
        workspace=workspace,
        historical_cases_path=ROOT / "fixtures" / "synthetic" / "historical_cases.json",
    )
    program = load_program(PROGRAM)
    program_ref = client.publish_program(program)

    client.run_education(
        EnrollCommand(
            program_selector=program_ref.selector,
            learner_ref=LEARNER_ID,
            enrollment_id=ENROLLMENT_ID,
            idempotency_key="education-example-enroll-v1",
        )
    )
    client.run_education(
        StartMilestoneCommand(
            enrollment_id=ENROLLMENT_ID,
            milestone_id="orientation",
            actor_id=LEARNER_ID,
            idempotency_key="education-example-orientation-start-v1",
        )
    )
    client.run_education(
        ManualConfirmationCommand(
            enrollment_id=ENROLLMENT_ID,
            milestone_id="orientation",
            requirement_id="orientation-attendance",
            actor_id="instructor:synthetic-001",
            actor_role="instructor",
            evidence_ref="synthetic://attendance/orientation-001",
            idempotency_key="education-example-orientation-confirm-v1",
        )
    )

    dossier = client.register_case(
        PROPOSAL,
        title="교육 프로젝트 · OLED 양자-고전 분자 역설계",
        sidecar_path=PROPOSAL_SIDECAR,
        project_id=PROJECT_ID,
        review_context=ReviewContext(
            program_id=program.program_id,
            program_version=program.version,
            enrollment_id=ENROLLMENT_ID,
            milestone_id="oled-project-certification",
            learner_ref=LEARNER_ID,
            business_unit_id="education-fixture",
            proposer_org_id="learner-team:synthetic",
            certification_level="foundation",
        ),
    )
    client.run_education(
        BindProjectCommand(
            enrollment_id=ENROLLMENT_ID,
            milestone_id="oled-project-certification",
            project_id=dossier.project_id,
            actor_id=LEARNER_ID,
            idempotency_key="education-example-bind-project-v1",
        )
    )

    client.submit_registration(PROJECT_ID)
    registration_wait = client.evaluate(PROJECT_ID, "registration")
    if registration_wait.allowed_commands != ("approve", "reject"):
        raise RuntimeError("registration did not stop at the administrator HITL gate")
    registration_report = _report(registration_wait.report_markdown_uri)
    client.decide_registration(
        PROJECT_ID,
        command="approve",
        actor_id="administrator:synthetic-001",
        rationale=(
            "Agent의 보완 의견을 확인했다. 실제 정책 승인이 아니라 교육 lifecycle fixture의 "
            "등록·수행·완료 연결을 검증하기 위해서만 승인한다."
        ),
    )
    client.assign_mentor(PROJECT_ID, mentor_ref="mentor:synthetic-001")
    client.start_execution(PROJECT_ID)
    client.record_progress(
        PROJECT_ID,
        note=(
            "등록 baseline을 고정하고 synthetic 완료자료의 KPI·재현성·변경·위험 증거를 "
            "준비했다."
        ),
    )
    client.submit_completion(
        PROJECT_ID,
        COMPLETION,
        sidecar_path=COMPLETION_SIDECAR,
        approval_actor_id="mentor:synthetic-001",
        approval_actor_role="mentor",
    )
    completion_wait = client.evaluate(PROJECT_ID, "completion")
    if completion_wait.allowed_commands != ("accept", "not_accept"):
        raise RuntimeError("completion did not stop at the administrator HITL gate")
    completion_report = _report(completion_wait.report_markdown_uri)
    client.decide_completion(
        PROJECT_ID,
        command="accept",
        actor_id="administrator:synthetic-001",
        rationale=(
            "별도 synthetic 완료자료의 산출물·KPI·재현·변경·위험 근거와 mentor 제출 승인을 "
            "확인했다."
        ),
    )

    client.run_education(
        SyncProjectCommand(
            enrollment_id=ENROLLMENT_ID,
            milestone_id="oled-project-certification",
            idempotency_key="education-example-sync-project-v1",
        )
    )
    client.run_education(
        StartMilestoneCommand(
            enrollment_id=ENROLLMENT_ID,
            milestone_id="final-reflection",
            actor_id=LEARNER_ID,
            idempotency_key="education-example-reflection-start-v1",
        )
    )
    program_wait = client.run_education(
        RecordScoreCommand(
            enrollment_id=ENROLLMENT_ID,
            milestone_id="final-reflection",
            requirement_id="reflection-score",
            score=85,
            actor_id="instructor:synthetic-001",
            actor_role="instructor",
            evidence_ref="synthetic://assessment/reflection-001",
            idempotency_key="education-example-reflection-score-v1",
        )
    )
    if program_wait.allowed_commands != ("approve", "return_for_revision"):
        raise RuntimeError("program did not stop at the administrator completion gate")
    final = client.run_education(
        DecideProgramCompletionCommand(
            enrollment_id=ENROLLMENT_ID,
            command="approve",
            actor_id="administrator:synthetic-001",
            actor_role="administrator",
            rationale="모든 필수 마일스톤과 프로젝트 HITL 완료를 확인했다.",
            idempotency_key="education-example-program-approve-v1",
        )
    )
    enrollment = client.education.enrollments.load(ENROLLMENT_ID)
    project = client.service.dossiers.load(PROJECT_ID)
    return {
        "synthetic": True,
        "program": program_ref.selector,
        "program_sha256": program_ref.sha256,
        "enrollment_id": enrollment.enrollment_id,
        "enrollment_status": enrollment.status.value,
        "project_id": project.project_id,
        "project_status": project.status.value,
        "registration_recommendation": registration_report.recommendation.value,
        "completion_recommendation": completion_report.recommendation.value,
        "project_notification_count": len(project.notifications),
        "program_notification_count": len(enrollment.notifications),
        "milestones": {
            item.milestone_id: item.status.value for item in enrollment.milestones
        },
        "enrollment_uri": final.enrollment_uri,
        "quality_claim": (
            "offline synthetic lifecycle contract only; no official course, learner, "
            "model, embedding, or certification quality claim"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.workspace)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
