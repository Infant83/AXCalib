from pathlib import Path

import pytest
from pydantic import ValidationError

from axcalib import AXCalib
from axcalib.pipelines import BindProjectCommand, EnrollCommand
from axcalib.programs import EducationProgramError, ProgramRepositoryError, load_program
from axcalib.runtime import IdempotencyConflictError
from axcalib.schemas import EducationEnrollment, EducationProgram, ReviewContext

ROOT = Path(__file__).resolve().parents[2]
PROGRAM_PATH = (
    ROOT / "fixtures" / "synthetic" / "education_project_lifecycle" / "program.yaml"
)
PROJECT_SOURCE = ROOT / "tests" / "sources" / "oled_qc_project_outline.pptx"
PROJECT_SIDECAR = ROOT / "tests" / "sources" / "oled_qc_project_outline.axcalib.json"


def test_program_generates_ordered_goals_and_idempotent_enrollment(tmp_path: Path) -> None:
    client = AXCalib(tmp_path)
    reference = client.publish_program(load_program(PROGRAM_PATH))
    command = EnrollCommand(
        program_selector=reference.selector,
        learner_ref="learner:test",
        enrollment_id="enrollment-test-001",
        idempotency_key="enroll-test-001",
    )

    first = client.run_education(command)
    second = client.run_education(command)

    assert first == second
    enrollment = client.education.enrollments.load(first.enrollment_id)
    assert [item.status.value for item in enrollment.milestones] == [
        "available",
        "locked",
        "locked",
    ]
    with pytest.raises(IdempotencyConflictError):
        client.run_education(
            command.model_copy(update={"learner_ref": "learner:different"})
        )


def test_program_rejects_forward_prerequisite() -> None:
    raw = load_program(PROGRAM_PATH).model_dump(mode="json")
    raw["levels"][0]["milestones"][0]["prerequisites"] = [
        "oled-project-certification"
    ]
    with pytest.raises(ValidationError, match="prerequisite must precede"):
        EducationProgram.model_validate(raw)


def test_program_rejects_arbitrary_pipeline(tmp_path: Path) -> None:
    client = AXCalib(tmp_path)
    program = load_program(PROGRAM_PATH)
    first_level = program.levels[0]
    first_milestone = first_level.milestones[0].model_copy(
        update={"pipeline_id": "arbitrary.python.import"}
    )
    changed = program.model_copy(
        update={
            "levels": (
                first_level.model_copy(
                    update={
                        "milestones": (first_milestone, *first_level.milestones[1:])
                    }
                ),
                *program.levels[1:],
            )
        }
    )
    with pytest.raises(EducationProgramError, match="non-allowlisted"):
        client.publish_program(changed)


def test_project_binding_requires_exact_enrollment_context(tmp_path: Path) -> None:
    client = AXCalib(tmp_path)
    program = load_program(PROGRAM_PATH)
    reference = client.publish_program(program)
    client.run_education(
        EnrollCommand(
            program_selector=reference.selector,
            learner_ref="learner:expected",
            enrollment_id="enrollment-binding-001",
        )
    )
    dossier = client.register_case(
        PROJECT_SOURCE,
        sidecar_path=PROJECT_SIDECAR,
        title="잘못된 가입 맥락의 프로젝트",
        project_id="project-binding-001",
        review_context=ReviewContext(
            program_id=program.program_id,
            program_version=program.version,
            enrollment_id="enrollment-other",
            milestone_id="oled-project-certification",
            learner_ref="learner:other",
        ),
    )

    with pytest.raises(EducationProgramError, match="education context"):
        client.run_education(
            BindProjectCommand(
                enrollment_id="enrollment-binding-001",
                milestone_id="oled-project-certification",
                project_id=dossier.project_id,
                actor_id="learner:expected",
            )
        )


def test_program_and_enrollment_content_ids_must_match_repository_paths(
    tmp_path: Path,
) -> None:
    client = AXCalib(tmp_path)
    reference = client.publish_program(load_program(PROGRAM_PATH))
    program_path = Path(reference.source_uri)
    program_path.write_text(
        program_path.read_text(encoding="utf-8").replace(
            "program_id: ax-oled-project-foundations",
            "program_id: ax-oled-project-other",
        ),
        encoding="utf-8",
    )
    with pytest.raises(ProgramRepositoryError, match="does not match"):
        client.education.programs.resolve(reference.selector)

    clean = AXCalib(tmp_path / "enrollment")
    clean_reference = clean.publish_program(load_program(PROGRAM_PATH))
    enrolled = clean.run_education(
        EnrollCommand(
            program_selector=clean_reference.selector,
            learner_ref="learner:path-check",
            enrollment_id="enrollment-path-check",
        )
    )
    enrollment_path = clean.education.enrollments.path_for(enrolled.enrollment_id)
    enrollment_path.write_text(
        enrollment_path.read_text(encoding="utf-8").replace(
            "enrollment_id: enrollment-path-check",
            "enrollment_id: enrollment-other",
        ),
        encoding="utf-8",
    )
    with pytest.raises(ProgramRepositoryError, match="does not match"):
        clean.education.enrollments.load(enrolled.enrollment_id)


def test_enrollment_cannot_claim_completion_without_administrator_decision(
    tmp_path: Path,
) -> None:
    client = AXCalib(tmp_path)
    reference = client.publish_program(load_program(PROGRAM_PATH))
    result = client.run_education(
        EnrollCommand(
            program_selector=reference.selector,
            learner_ref="learner:integrity",
            enrollment_id="enrollment-integrity",
        )
    )
    enrollment = client.education.enrollments.load(result.enrollment_id)
    raw = enrollment.model_dump(mode="json")
    raw["status"] = "completed"

    with pytest.raises(ValidationError, match="administrator decision"):
        EducationEnrollment.model_validate(raw)
