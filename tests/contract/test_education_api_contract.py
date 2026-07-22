from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from axcalib import AXCalib
from axcalib.api import ApiPipelineGrant, ApiPrincipal, ApiRole, create_app
from axcalib.programs import load_program
from axcalib.schemas import EducationProgram, ReviewContext

ROOT = Path(__file__).resolve().parents[2]
PROGRAM_PATH = ROOT / "fixtures" / "synthetic" / "education_project_lifecycle" / "program.yaml"
PROJECT_SOURCE = ROOT / "tests" / "sources" / "oled_qc_project_outline.pptx"
PROJECT_SIDECAR = ROOT / "tests" / "sources" / "oled_qc_project_outline.axcalib.json"


def _review_program() -> EducationProgram:
    source = load_program(PROGRAM_PATH)
    level = source.levels[0]
    milestone = level.milestones[0]
    instructor_requirement = milestone.requirements[0]
    mentor_requirement = instructor_requirement.model_copy(
        update={
            "requirement_id": "mentor-safety-review",
            "title": "배정 멘토가 안전 검토를 확인",
            "required_role": "mentor",
        }
    )
    return source.model_copy(
        update={
            "program_id": "api-education-review",
            "title": "API 교육 권한 검증 프로그램",
            "levels": (
                level.model_copy(
                    update={
                        "milestones": (
                            milestone.model_copy(
                                update={
                                    "requirements": (
                                        instructor_requirement,
                                        mentor_requirement,
                                    )
                                }
                            ),
                        )
                    }
                ),
            ),
        }
    )


class _TokenVerifier:
    def __init__(self, program_selector: str) -> None:
        instructor_scope = f"education:program:{program_selector}:instructor"
        self.principals: dict[str, ApiPrincipal] = {
            "learner-token": ApiPrincipal(
                subject="learner:alpha",
                role=ApiRole.LEARNER,
                organization_id="org:alpha",
                scopes=frozenset(
                    {
                        "education:programs:read",
                        "education:enroll:self",
                        "education:progress:self",
                    }
                ),
            ),
            "other-learner-token": ApiPrincipal(
                subject="learner:other",
                role=ApiRole.LEARNER,
                organization_id="org:alpha",
                scopes=frozenset({"education:progress:self"}),
            ),
            "wrong-org-learner-token": ApiPrincipal(
                subject="learner:alpha",
                role=ApiRole.LEARNER,
                organization_id="org:other",
                scopes=frozenset({"education:progress:self"}),
            ),
            "instructor-token": ApiPrincipal(
                subject="instructor:alpha",
                role=ApiRole.INSTRUCTOR,
                organization_id="org:alpha",
                scopes=frozenset({instructor_scope}),
            ),
            "wrong-instructor-token": ApiPrincipal(
                subject="instructor:other-program",
                role=ApiRole.INSTRUCTOR,
                organization_id="org:alpha",
                scopes=frozenset({"education:program:another-program@0.1.0:instructor"}),
            ),
            "admin-token": ApiPrincipal(
                subject="administrator:alpha",
                role=ApiRole.ADMINISTRATOR,
                organization_id="org:alpha",
                scopes=frozenset({"education:admin:any"}),
            ),
            "wrong-org-admin-token": ApiPrincipal(
                subject="administrator:other",
                role=ApiRole.ADMINISTRATOR,
                organization_id="org:other",
                scopes=frozenset({"education:admin:any"}),
            ),
            "unscoped-admin-token": ApiPrincipal(
                subject="administrator:unscoped",
                role=ApiRole.ADMINISTRATOR,
                organization_id="org:alpha",
            ),
        }

    def add_mentor(self, enrollment_id: str) -> None:
        self.principals["mentor-token"] = ApiPrincipal(
            subject="mentor:alpha",
            role=ApiRole.MENTOR,
            organization_id="org:alpha",
            scopes=frozenset({f"education:enrollment:{enrollment_id}:mentor"}),
        )
        self.principals["wrong-mentor-token"] = ApiPrincipal(
            subject="mentor:wrong-assignment",
            role=ApiRole.MENTOR,
            organization_id="org:alpha",
            scopes=frozenset({"education:enrollment:another-enrollment:mentor"}),
        )

    def verify(self, token: str) -> ApiPrincipal | None:
        return self.principals.get(token)


def _headers(token: str, key: str | None = None) -> dict[str, str]:
    values = {"Authorization": f"Bearer {token}"}
    if key is not None:
        values["Idempotency-Key"] = key
    return values


def _setup(
    tmp_path: Path,
    program: EducationProgram | None = None,
) -> tuple[AXCalib, TestClient, _TokenVerifier, str, str]:
    runtime = AXCalib(tmp_path / "workspace")
    reference = runtime.publish_program(program or _review_program())
    verifier = _TokenVerifier(reference.selector)
    client = TestClient(create_app(runtime, token_verifier=verifier))
    return runtime, client, verifier, reference.selector, reference.sha256


def _enroll(
    client: TestClient,
    selector: str,
    program_hash: str,
    *,
    key: str = "education-enroll-1",
) -> dict[str, object]:
    program_id, version = selector.rsplit("@", 1)
    response = client.post(
        f"/v1/programs/{program_id}/versions/{version}/enrollments",
        headers=_headers("learner-token", key),
        json={"expected_program_sha256": program_hash},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_education_enrollment_binds_learner_org_hash_and_safe_views(
    tmp_path: Path,
) -> None:
    runtime, client, _, selector, program_hash = _setup(tmp_path)
    program_id, version = selector.rsplit("@", 1)

    program = client.get(
        f"/v1/programs/{program_id}/versions/{version}",
        headers=_headers("learner-token"),
    )
    assert program.status_code == 200, program.text
    assert program.json()["sha256"] == program_hash
    assert "source_uri" not in program.text

    enrolled = _enroll(client, selector, program_hash)
    enrollment_id = str(enrolled["enrollment_id"])
    replay = _enroll(client, selector, program_hash)
    assert replay == enrolled

    record = runtime.education.enrollments.load(enrollment_id)
    creation = next(
        event
        for event in runtime.education.audit.entries()
        if event["event_type"] == "learner_enrolled"
    )
    assert record.learner_ref == "learner:alpha"
    assert creation["actor_id"] == "learner:alpha"
    assert creation["actor_role"] == "learner"
    assert creation["details"]["organization_id"] == "org:alpha"
    assert creation["details"]["authority_context"] == "verified_api_principal"

    view = client.get(
        f"/v1/enrollments/{enrollment_id}",
        headers=_headers("learner-token"),
    )
    assert view.status_code == 200, view.text
    assert view.json()["organization_id"] == "org:alpha"
    assert "source_uri" not in view.text
    assert "enrollment_uri" not in view.text

    other_learner = client.get(
        f"/v1/enrollments/{enrollment_id}",
        headers=_headers("other-learner-token"),
    )
    assert other_learner.status_code == 403
    assert other_learner.json()["code"] == "education_assignment_scope_forbidden"

    wrong_hash = client.post(
        f"/v1/programs/{program_id}/versions/{version}/enrollments",
        headers=_headers("learner-token", "education-enroll-bad-hash"),
        json={"expected_program_sha256": "0" * 64},
    )
    assert wrong_hash.status_code == 409
    assert wrong_hash.json()["code"] == "education_program_hash_conflict"


def test_learner_progress_uses_principal_revision_and_semantic_replay(
    tmp_path: Path,
) -> None:
    runtime, client, _, selector, program_hash = _setup(tmp_path)
    enrolled = _enroll(client, selector, program_hash)
    enrollment_id = str(enrolled["enrollment_id"])
    path = f"/v1/enrollments/{enrollment_id}/milestones/orientation/start"
    request = {"expected_revision": 1}

    impersonated = client.post(
        path,
        headers=_headers("learner-token", "start-impersonated"),
        json=request | {"actor_id": "learner:impersonated"},
    )
    assert impersonated.status_code == 422
    assert "impersonated" not in impersonated.text

    wrong_learner = client.post(
        path,
        headers=_headers("other-learner-token", "start-wrong-learner"),
        json=request,
    )
    assert wrong_learner.status_code == 403
    wrong_org = client.post(
        path,
        headers=_headers("wrong-org-learner-token", "start-wrong-org"),
        json=request,
    )
    assert wrong_org.status_code == 403
    assert wrong_org.json()["code"] == "education_organization_forbidden"
    assert runtime.education.enrollments.load(enrollment_id).revision == 1

    stale = client.post(
        path,
        headers=_headers("learner-token", "start-stale"),
        json={"expected_revision": 99},
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "stale_enrollment_revision"

    started = client.post(
        path,
        headers=_headers("learner-token", "start-orientation"),
        json=request,
    )
    assert started.status_code == 200, started.text
    assert started.json()["enrollment_revision"] == 2
    replay = client.post(
        path,
        headers=_headers("learner-token", "start-orientation"),
        json=request,
    )
    assert replay.status_code == 200
    assert replay.json() == started.json()
    event = runtime.education.audit.entries()[-1]
    assert event["event_type"] == "milestone_started"
    assert event["actor_id"] == "learner:alpha"


def test_reviewer_and_completion_commands_bind_assignment_org_and_admin(
    tmp_path: Path,
) -> None:
    runtime, client, verifier, selector, program_hash = _setup(tmp_path)
    enrolled = _enroll(client, selector, program_hash)
    enrollment_id = str(enrolled["enrollment_id"])
    verifier.add_mentor(enrollment_id)
    start_path = f"/v1/enrollments/{enrollment_id}/milestones/orientation/start"
    client.post(
        start_path,
        headers=_headers("learner-token", "review-start"),
        json={"expected_revision": 1},
    ).raise_for_status()
    confirmation_path = (
        f"/v1/enrollments/{enrollment_id}/milestones/orientation/manual-confirmations"
    )

    wrong_instructor = client.post(
        confirmation_path,
        headers=_headers("wrong-instructor-token", "wrong-instructor"),
        json={
            "expected_revision": 2,
            "requirement_id": "orientation-attendance",
            "evidence_id": "attendance-001",
        },
    )
    assert wrong_instructor.status_code == 403
    assert wrong_instructor.json()["code"] == "education_reviewer_scope_forbidden"

    instructor = client.post(
        confirmation_path,
        headers=_headers("instructor-token", "instructor-confirmation"),
        json={
            "expected_revision": 2,
            "requirement_id": "orientation-attendance",
            "evidence_id": "attendance-001",
        },
    )
    assert instructor.status_code == 200, instructor.text
    assert instructor.json()["enrollment_revision"] == 3
    instructor_event = runtime.education.audit.entries()[-1]
    assert instructor_event["event_type"] == "requirement_recorded"
    assert instructor_event["actor_id"] == "instructor:alpha"
    assert instructor_event["actor_role"] == "instructor"
    assert instructor_event["details"]["authority_context"] == "verified_api_principal"

    wrong_mentor = client.post(
        confirmation_path,
        headers=_headers("wrong-mentor-token", "wrong-mentor"),
        json={
            "expected_revision": 3,
            "requirement_id": "mentor-safety-review",
            "evidence_id": "mentor-review-001",
        },
    )
    assert wrong_mentor.status_code == 403
    assert runtime.education.enrollments.load(enrollment_id).revision == 3

    mentor = client.post(
        confirmation_path,
        headers=_headers("mentor-token", "mentor-confirmation"),
        json={
            "expected_revision": 3,
            "requirement_id": "mentor-safety-review",
            "evidence_id": "mentor-review-001",
        },
    )
    assert mentor.status_code == 200, mentor.text
    assert mentor.json()["enrollment_status"] == "completion_hitl_pending"
    assert mentor.json()["enrollment_revision"] == 5
    mentor_replay = client.post(
        confirmation_path,
        headers=_headers("mentor-token", "mentor-confirmation"),
        json={
            "expected_revision": 3,
            "requirement_id": "mentor-safety-review",
            "evidence_id": "mentor-review-001",
        },
    )
    assert mentor_replay.status_code == 200
    assert mentor_replay.json() == mentor.json()
    mentor_event = next(
        event
        for event in runtime.education.audit.entries()
        if event["event_type"] == "requirement_recorded"
        and event["details"]["requirement_id"] == "mentor-safety-review"
    )
    assert mentor_event["actor_id"] == "mentor:alpha"
    assert mentor_event["actor_role"] == "mentor"
    assert mentor_event["details"]["authority_context"] == "verified_api_principal"

    decision_path = f"/v1/enrollments/{enrollment_id}/completion-decisions"
    decision = {
        "expected_revision": 5,
        "command": "approve",
        "rationale": "Configured evidence and human review were checked.",
    }
    wrong_org = client.post(
        decision_path,
        headers=_headers("wrong-org-admin-token", "decision-wrong-org"),
        json=decision,
    )
    assert wrong_org.status_code == 403
    unscoped = client.post(
        decision_path,
        headers=_headers("unscoped-admin-token", "decision-unscoped"),
        json=decision,
    )
    assert unscoped.status_code == 403
    stale = client.post(
        decision_path,
        headers=_headers("admin-token", "decision-stale"),
        json=decision | {"expected_revision": 4},
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "stale_enrollment_revision"
    impersonated = client.post(
        decision_path,
        headers=_headers("admin-token", "decision-impersonated"),
        json=decision | {"actor_id": "administrator:impersonated"},
    )
    assert impersonated.status_code == 422

    approved = client.post(
        decision_path,
        headers=_headers("admin-token", "decision-approved"),
        json=decision,
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["enrollment_status"] == "completed"
    completed = runtime.education.enrollments.load(enrollment_id)
    assert completed.completion_decisions[-1].authority_context == "verified_api_principal"
    final_event = runtime.education.audit.entries()[-1]
    assert final_event["event_type"] == "program_completion_decided"
    assert final_event["actor_id"] == "administrator:alpha"
    assert final_event["actor_role"] == "administrator"


def test_project_binding_rechecks_education_and_organization_context(
    tmp_path: Path,
) -> None:
    program = load_program(PROGRAM_PATH)
    runtime, client, _, selector, program_hash = _setup(tmp_path, program)
    enrolled = _enroll(client, selector, program_hash, key="project-enrollment")
    enrollment_id = str(enrolled["enrollment_id"])
    start_path = f"/v1/enrollments/{enrollment_id}/milestones/orientation/start"
    client.post(
        start_path,
        headers=_headers("learner-token", "project-orientation-start"),
        json={"expected_revision": 1},
    ).raise_for_status()
    confirmation_path = (
        f"/v1/enrollments/{enrollment_id}/milestones/orientation/manual-confirmations"
    )
    client.post(
        confirmation_path,
        headers=_headers("instructor-token", "project-orientation-confirm"),
        json={
            "expected_revision": 2,
            "requirement_id": "orientation-attendance",
            "evidence_id": "project-attendance-001",
        },
    ).raise_for_status()

    context = {
        "program_id": program.program_id,
        "program_version": program.version,
        "enrollment_id": enrollment_id,
        "milestone_id": "oled-project-certification",
        "learner_ref": "learner:alpha",
    }
    wrong = runtime.register_case(
        PROJECT_SOURCE,
        sidecar_path=PROJECT_SIDECAR,
        title="Wrong organization project",
        project_id="education-project-wrong-org",
        review_context=ReviewContext(**context, proposer_org_id="org:other"),
    )
    correct = runtime.register_case(
        PROJECT_SOURCE,
        sidecar_path=PROJECT_SIDECAR,
        title="Correct education project",
        project_id="education-project-correct",
        review_context=ReviewContext(**context, proposer_org_id="org:alpha"),
    )
    bind_path = f"/v1/enrollments/{enrollment_id}/milestones/oled-project-certification/projects"
    rejected = client.post(
        bind_path,
        headers=_headers("learner-token", "bind-wrong-org"),
        json={"expected_revision": 3, "project_id": wrong.project_id},
    )
    assert rejected.status_code == 409
    assert rejected.json()["code"] == "education_command_conflict"
    assert runtime.education.enrollments.load(enrollment_id).revision == 3

    impersonated = client.post(
        bind_path,
        headers=_headers("learner-token", "bind-impersonated"),
        json={
            "expected_revision": 3,
            "project_id": correct.project_id,
            "actor_id": "learner:impersonated",
        },
    )
    assert impersonated.status_code == 422

    bound = client.post(
        bind_path,
        headers=_headers("learner-token", "bind-correct"),
        json={"expected_revision": 3, "project_id": correct.project_id},
    )
    assert bound.status_code == 200, bound.text
    assert bound.json()["enrollment_revision"] == 4

    sync_path = (
        f"/v1/enrollments/{enrollment_id}/milestones/oled-project-certification/project-sync"
    )
    synced = client.post(
        sync_path,
        headers=_headers("learner-token", "sync-project"),
        json={"expected_revision": 4},
    )
    assert synced.status_code == 200, synced.text
    assert synced.json()["enrollment_revision"] == 5
    event = runtime.education.audit.entries()[-1]
    assert event["event_type"] == "requirement_recorded"
    assert event["actor_id"] == "learner:alpha"
    assert event["actor_role"] == "learner"


def test_education_pipeline_cannot_bypass_resource_authority(tmp_path: Path) -> None:
    runtime = AXCalib(tmp_path / "workspace")
    with pytest.raises(ValueError, match="principal-bound resource"):
        create_app(
            runtime,
            pipeline_grants=(
                ApiPipelineGrant(
                    pipeline_id="education-program-runtime",
                    pipeline_version="v1alpha1",
                ),
            ),
        )
    with pytest.raises(ValidationError, match="principal-bound resource"):
        ApiPipelineGrant(
            pipeline_id="workspace.maintenance",
            pipeline_version="v1alpha1",
            execute_roles=frozenset({ApiRole.LEARNER}),
        )
