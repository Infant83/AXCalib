"""Run one honest offline pass/accept demonstration and render readable case views."""

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
from axcalib.policies import ReviewProfileRegistry  # noqa: E402
from axcalib.schemas import AgentRecommendation, CaseStatus, CaseSummary  # noqa: E402

PROPOSAL = ROOT / "tests" / "sources" / "oled_qc_project_outline.pptx"
PROPOSAL_SIDECAR = ROOT / "tests" / "sources" / "oled_qc_project_outline.axcalib.json"
COMPLETION = (
    ROOT
    / "fixtures"
    / "synthetic"
    / "education_project_lifecycle"
    / "completion_report.synthetic.pptx"
)
COMPLETION_SIDECAR = (
    ROOT
    / "fixtures"
    / "synthetic"
    / "education_project_lifecycle"
    / "completion_report.synthetic.axcalib.json"
)
PROFILE = Path(__file__).with_name("review-profile.example.yaml")
PROFILE_SELECTOR = "example.education-project@1.0.0"


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def run_example(
    workspace: Path,
    *,
    project_id: str = "example-readable-pass-001",
) -> CaseSummary:
    """Run the supplied proposal through an example-only two-gate policy."""

    profiles = ReviewProfileRegistry.with_builtin_default()
    profiles.load_file(PROFILE)
    client = AXCalib(workspace, review_profiles=profiles)
    case = client.register_case(
        PROPOSAL,
        title="OLED 분자 역설계 교육 프로젝트 · 읽기 예제",
        sidecar_path=PROPOSAL_SIDECAR,
        project_id=project_id,
        review_profile=PROFILE_SELECTOR,
    )

    client.submit_registration(case.project_id)
    client.evaluate(case.project_id, "registration")
    registration_pending = case.get_current_status(verbose=True)
    if not isinstance(registration_pending, CaseStatus):
        raise TypeError("case status object was expected")
    if (
        registration_pending.latest_review is None
        or registration_pending.latest_review.agent_recommendation is not AgentRecommendation.PASS
    ):
        raise RuntimeError("the example policy must produce a registration pass proposal")
    registration_markdown = case.get_current_status(format="md", verbose=True)
    if not isinstance(registration_markdown, str):
        raise TypeError("rendered case status text was expected")
    _write(
        workspace / "views" / "01-registration-hitl-pending.md",
        registration_markdown,
    )

    client.decide_registration(
        case.project_id,
        command="approve",
        actor_id="administrator:offline-example",
        rationale=(
            "예제 전용 기준의 근거 locator와 한계를 확인하고 교육 lifecycle 진행을 승인한다."
        ),
        expected_revision=case.revision,
        authority_context="offline_example_explicit_admin",
    )
    client.assign_mentor(case.project_id, mentor_ref="mentor:offline-example")
    client.start_execution(case.project_id)
    client.record_progress(
        case.project_id,
        note=(
            "등록 baseline을 유지하며 synthetic 완료자료, 두 HITL 기록과 재현 가능한 "
            "Library 예제를 준비했다."
        ),
    )
    client.submit_completion(
        case.project_id,
        COMPLETION,
        sidecar_path=COMPLETION_SIDECAR,
        approval_actor_id="mentor:offline-example",
        approval_actor_role="mentor",
    )
    client.evaluate(case.project_id, "completion")
    completion_pending = case.get_current_status(verbose=True)
    if not isinstance(completion_pending, CaseStatus):
        raise TypeError("case status object was expected")
    if (
        completion_pending.latest_review is None
        or completion_pending.latest_review.agent_recommendation is not AgentRecommendation.ACCEPT
    ):
        raise RuntimeError("the example policy must produce a completion accept proposal")
    completion_markdown = case.get_current_status(format="md", verbose=True)
    if not isinstance(completion_markdown, str):
        raise TypeError("rendered case status text was expected")
    _write(
        workspace / "views" / "02-completion-hitl-pending.md",
        completion_markdown,
    )

    client.decide_completion(
        case.project_id,
        command="accept",
        actor_id="administrator:offline-example",
        rationale=(
            "등록 baseline, 수행 기록, 완료 증거와 예제 한계를 확인하고 완료평가를 수용한다."
        ),
        expected_revision=case.revision,
        authority_context="offline_example_explicit_admin",
    )
    summary = case.get_summary(verbose=True)
    if not isinstance(summary, CaseSummary):
        raise TypeError("case summary object was expected")
    markdown = case.get_summary(format="md", verbose=True)
    json_text = case.get_summary(format="json", verbose=True)
    if not isinstance(markdown, str) or not isinstance(json_text, str):
        raise TypeError("rendered case summary text was expected")
    _write(workspace / "views" / "03-final-summary.md", markdown)
    _write(workspace / "views" / "03-final-summary.json", json_text)
    _write(
        workspace / "views" / "run-result.json",
        json.dumps(
            {
                "schema_version": "axcalib.example-result/v1alpha1",
                "project_id": summary.project_id,
                "dossier_status": summary.dossier_status.value,
                "dossier_revision": summary.revision,
                "registration_agent_recommendation": (summary.registration.agent_recommendation),
                "registration_human_decision": (
                    summary.registration.human_decision.command
                    if summary.registration.human_decision
                    else None
                ),
                "completion_agent_recommendation": (summary.completion.agent_recommendation),
                "completion_human_decision": (
                    summary.completion.human_decision.command
                    if summary.completion.human_decision
                    else None
                ),
                "policy": summary.review_profile,
                "policy_sha256": summary.review_profile_sha256,
                "limitations": [
                    "example-only reduced offline policy",
                    "supplied proposal plus synthetic completion fixture",
                    "not an official AX certification result",
                ],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    return summary


def main() -> None:
    """Parse a small CLI surface and run the example in a new workspace."""

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path("output/examples/readable-pass"),
        help="New or empty local workspace. Existing project IDs fail closed.",
    )
    parser.add_argument("--project-id", default="example-readable-pass-001")
    arguments = parser.parse_args()
    summary = run_example(arguments.workspace, project_id=arguments.project_id)
    print(
        json.dumps(
            {
                "project_id": summary.project_id,
                "status": summary.dossier_status.value,
                "summary": str(arguments.workspace / "views" / "03-final-summary.md"),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
