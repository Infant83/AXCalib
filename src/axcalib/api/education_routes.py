"""Principal-bound education enrollment and milestone routes."""

import asyncio
import hashlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated, Literal, cast

from fastapi import APIRouter, Depends, Header
from fastapi import Path as ApiPath
from pydantic import ValidationError

from axcalib.client import AXCalib
from axcalib.pipelines import (
    BindProjectCommand,
    DecideProgramCompletionCommand,
    EducationCommand,
    EnrollCommand,
    ManualConfirmationCommand,
    RecordScoreCommand,
    StartMilestoneCommand,
    SyncProjectCommand,
)
from axcalib.programs import (
    EducationProgramError,
    EnrollmentRevisionConflictError,
    ProgramRepositoryError,
)
from axcalib.runtime import (
    IdempotencyConflictError,
    TransactionBlockedError,
    TransactionConflictError,
    TransactionIntegrityError,
)
from axcalib.schemas import (
    EducationEnrollment,
    EducationPipelineResult,
    EducationProgram,
    ManualConfirmationRequirement,
    MilestoneSpec,
    ProgramRef,
    ScoreRequirement,
)

from .auth import ApiPrincipal, ApiRole
from .models import (
    EducationCommandResponse,
    EducationCompletionDecisionRequest,
    EducationEnrollmentCreateRequest,
    EducationEnrollmentView,
    EducationManualConfirmationRequest,
    EducationProgramView,
    EducationProjectBindRequest,
    EducationRevisionRequest,
    EducationScoreRequest,
)
from .problems import ApiProblemError, problem_responses

AuthenticationDependency = Callable[..., Awaitable[ApiPrincipal]]
RESOURCE_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"
IDEMPOTENCY_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"


@dataclass(frozen=True)
class _EnrollmentContext:
    enrollment: EducationEnrollment
    program: EducationProgram
    program_ref: ProgramRef
    organization_id: str


def _scoped_idempotency_key(principal: ApiPrincipal, raw_key: str) -> str:
    value = f"{principal.subject}\0education\0{raw_key}".encode()
    return f"api-edu-{hashlib.sha256(value).hexdigest()[:40]}"


def _stable_enrollment_id(principal: ApiPrincipal, raw_key: str) -> str:
    value = f"{principal.subject}\0education:enroll\0{raw_key}".encode()
    return f"enrollment-api-{hashlib.sha256(value).hexdigest()[:32]}"


def _command_view(value: EducationPipelineResult) -> EducationCommandResponse:
    return EducationCommandResponse(
        enrollment_id=value.enrollment_id,
        enrollment_status=value.enrollment_status,
        enrollment_revision=value.enrollment_revision,
        active_milestone_ids=value.active_milestone_ids,
        allowed_commands=value.allowed_commands,
        status=value.status,
        message=value.message,
    )


def _enrollment_view(context: _EnrollmentContext) -> EducationEnrollmentView:
    enrollment = context.enrollment
    return EducationEnrollmentView(
        enrollment_id=enrollment.enrollment_id,
        learner_ref=enrollment.learner_ref,
        organization_id=context.organization_id,
        program_selector=enrollment.program.selector,
        program_sha256=enrollment.program.sha256,
        revision=enrollment.revision,
        status=enrollment.status,
        created_at=enrollment.created_at,
        updated_at=enrollment.updated_at,
        milestones=enrollment.milestones,
        notifications=enrollment.notifications,
        completion_decisions=enrollment.completion_decisions,
    )


def _milestone(program: EducationProgram, milestone_id: str) -> MilestoneSpec:
    for _, milestone in program.milestones():
        if milestone.milestone_id == milestone_id:
            return milestone
    raise ApiProblemError(
        status=404,
        code="education_milestone_not_found",
        title="Education milestone was not found",
    )


def _required_role(
    program: EducationProgram,
    milestone_id: str,
    requirement_id: str,
    *,
    expected_kind: Literal["manual_confirmation", "score_at_least"],
) -> str:
    milestone = _milestone(program, milestone_id)
    for requirement in milestone.requirements:
        if requirement.requirement_id != requirement_id:
            continue
        if expected_kind == "manual_confirmation" and isinstance(
            requirement, ManualConfirmationRequirement
        ):
            return requirement.required_role
        if expected_kind == "score_at_least" and isinstance(requirement, ScoreRequirement):
            return requirement.required_role
        raise ApiProblemError(
            status=409,
            code="education_requirement_kind_conflict",
            title="Education requirement does not accept this command",
        )
    raise ApiProblemError(
        status=404,
        code="education_requirement_not_found",
        title="Education requirement was not found",
    )


def create_education_router(
    client: AXCalib,
    *,
    authenticate: AuthenticationDependency,
) -> APIRouter:
    """Build education routes whose authority comes only from verified principals."""

    router = APIRouter()

    def load_program(program_id: str, program_version: str) -> tuple[EducationProgram, ProgramRef]:
        try:
            return client.education.programs.resolve(f"{program_id}@{program_version}")
        except ProgramRepositoryError as error:
            code = (
                "education_program_not_found"
                if "not found" in str(error)
                else "education_program_integrity_failure"
            )
            raise ApiProblemError(
                status=404 if code.endswith("not_found") else 409,
                code=code,
                title=(
                    "Education program was not found"
                    if code.endswith("not_found")
                    else "Education program integrity verification failed"
                ),
            ) from error
        except (ValidationError, UnicodeError) as error:
            raise ApiProblemError(
                status=409,
                code="education_program_integrity_failure",
                title="Education program integrity verification failed",
            ) from error

    def load_enrollment(enrollment_id: str) -> _EnrollmentContext:
        try:
            enrollment = client.education.enrollments.load(enrollment_id)
            program, program_ref = client.education.programs.resolve(enrollment.program.selector)
            if program_ref.sha256 != enrollment.program.sha256:
                raise ValueError("program hash changed after enrollment")
            creation = next(
                (
                    event
                    for event in client.education.audit.entries()
                    if event.get("event_id") in enrollment.audit_event_ids
                    and event.get("enrollment_id") == enrollment.enrollment_id
                    and event.get("event_type") == "learner_enrolled"
                    and event.get("enrollment_revision") == 1
                ),
                None,
            )
            if creation is None or creation.get("actor_id") != enrollment.learner_ref:
                raise ValueError("principal-bound enrollment audit is missing")
            details = creation.get("details")
            if not isinstance(details, dict):
                raise ValueError("enrollment authority details are missing")
            organization_id = details.get("organization_id")
            if not isinstance(organization_id, str) or not organization_id:
                raise ValueError("enrollment organization binding is missing")
            if (
                details.get("program") != enrollment.program.selector
                or details.get("program_sha256") != enrollment.program.sha256
            ):
                raise ValueError("enrollment program audit does not match")
            return _EnrollmentContext(
                enrollment=enrollment,
                program=program,
                program_ref=program_ref,
                organization_id=organization_id,
            )
        except ProgramRepositoryError as error:
            if "not found" in str(error):
                raise ApiProblemError(
                    status=404,
                    code="education_enrollment_not_found",
                    title="Education enrollment was not found",
                ) from error
            raise ApiProblemError(
                status=409,
                code="education_enrollment_integrity_failure",
                title="Education enrollment integrity verification failed",
            ) from error
        except (ValidationError, UnicodeError, ValueError) as error:
            raise ApiProblemError(
                status=409,
                code="education_enrollment_integrity_failure",
                title="Education enrollment integrity verification failed",
            ) from error

    def require_organization(
        principal: ApiPrincipal,
        context: _EnrollmentContext,
    ) -> None:
        organization_override = (
            principal.role is ApiRole.ADMINISTRATOR
            and "education:organization:any" in principal.scopes
        )
        if principal.organization_id != context.organization_id and not organization_override:
            raise ApiProblemError(
                status=403,
                code="education_organization_forbidden",
                title="Caller organization does not match this enrollment",
            )

    def require_learner(
        principal: ApiPrincipal,
        context: _EnrollmentContext,
    ) -> None:
        require_organization(principal, context)
        if (
            principal.role is not ApiRole.LEARNER
            or principal.subject != context.enrollment.learner_ref
            or "education:progress:self" not in principal.scopes
        ):
            raise ApiProblemError(
                status=403,
                code="education_learner_scope_forbidden",
                title="Caller is not the authorized learner for this enrollment",
            )

    def is_administrator(principal: ApiPrincipal, context: _EnrollmentContext) -> bool:
        return principal.role is ApiRole.ADMINISTRATOR and (
            "education:admin:any" in principal.scopes
            or f"education:enrollment:{context.enrollment.enrollment_id}:admin" in principal.scopes
        )

    def require_assigned_actor(
        principal: ApiPrincipal,
        context: _EnrollmentContext,
    ) -> None:
        require_organization(principal, context)
        assigned = False
        if principal.role is ApiRole.LEARNER:
            assigned = (
                principal.subject == context.enrollment.learner_ref
                and "education:progress:self" in principal.scopes
            )
        elif principal.role is ApiRole.MENTOR:
            assigned = (
                f"education:enrollment:{context.enrollment.enrollment_id}:mentor"
                in principal.scopes
            )
        elif principal.role is ApiRole.INSTRUCTOR:
            assigned = (
                f"education:program:{context.enrollment.program.selector}:instructor"
                in principal.scopes
            )
        elif principal.role is ApiRole.ADMINISTRATOR:
            assigned = is_administrator(principal, context)
        if not assigned:
            raise ApiProblemError(
                status=403,
                code="education_assignment_scope_forbidden",
                title="Caller is not assigned to this education resource",
            )

    def require_reviewer(
        principal: ApiPrincipal,
        context: _EnrollmentContext,
        required_role: str,
    ) -> None:
        require_organization(principal, context)
        if is_administrator(principal, context):
            return
        role_matches = principal.role.value == required_role
        assigned = False
        if principal.role is ApiRole.MENTOR:
            assigned = (
                f"education:enrollment:{context.enrollment.enrollment_id}:mentor"
                in principal.scopes
            )
        elif principal.role is ApiRole.INSTRUCTOR:
            assigned = (
                f"education:program:{context.enrollment.program.selector}:instructor"
                in principal.scopes
            )
        if not role_matches or not assigned:
            raise ApiProblemError(
                status=403,
                code="education_reviewer_scope_forbidden",
                title="Caller does not hold the configured reviewer assignment",
            )

    def require_administrator(
        principal: ApiPrincipal,
        context: _EnrollmentContext,
    ) -> None:
        require_organization(principal, context)
        if not is_administrator(principal, context):
            raise ApiProblemError(
                status=403,
                code="education_administrator_scope_forbidden",
                title="Administrator assignment is required",
            )

    async def execute(command: EducationCommand) -> EducationCommandResponse:
        try:
            result = await asyncio.to_thread(client.run_education, command)
        except IdempotencyConflictError as error:
            raise ApiProblemError(
                status=409,
                code="education_idempotency_conflict",
                title="Idempotency key was already used for a different command",
            ) from error
        except EnrollmentRevisionConflictError as error:
            raise ApiProblemError(
                status=409,
                code="stale_enrollment_revision",
                title="Enrollment revision is stale",
            ) from error
        except EducationProgramError as error:
            code = (
                "stale_enrollment_revision"
                if "expected enrollment revision" in str(error)
                else "education_command_conflict"
            )
            raise ApiProblemError(
                status=409,
                code=code,
                title=(
                    "Enrollment revision is stale"
                    if code == "stale_enrollment_revision"
                    else "Education command conflicts with current state or policy"
                ),
            ) from error
        except ProgramRepositoryError as error:
            raise ApiProblemError(
                status=404 if "not found" in str(error) else 409,
                code=(
                    "education_resource_not_found"
                    if "not found" in str(error)
                    else "education_resource_integrity_failure"
                ),
                title=(
                    "Education resource was not found"
                    if "not found" in str(error)
                    else "Education resource integrity verification failed"
                ),
            ) from error
        except (
            TransactionBlockedError,
            TransactionConflictError,
            TransactionIntegrityError,
            ValidationError,
            UnicodeError,
        ) as error:
            raise ApiProblemError(
                status=409,
                code="education_transaction_integrity_failure",
                title="Education transaction integrity verification failed",
            ) from error
        if not isinstance(result, EducationPipelineResult):
            raise ApiProblemError(
                status=500,
                code="education_result_invalid",
                title="Education command returned an invalid result",
            )
        return _command_view(result)

    @router.get(
        "/v1/programs/{program_id}/versions/{program_version}",
        operation_id="getEducationProgram",
        response_model=EducationProgramView,
        responses=problem_responses(401, 403, 404, 409, 422, 503),
    )
    async def get_program(
        principal: Annotated[ApiPrincipal, Depends(authenticate)],
        program_id: Annotated[str, ApiPath(pattern=RESOURCE_PATTERN)],
        program_version: Annotated[str, ApiPath(pattern=RESOURCE_PATTERN)],
    ) -> EducationProgramView:
        if "education:programs:read" not in principal.scopes:
            raise ApiProblemError(
                status=403,
                code="education_program_read_forbidden",
                title="Program read scope is required",
            )
        program, reference = load_program(program_id, program_version)
        return EducationProgramView(
            selector=reference.selector,
            sha256=reference.sha256,
            program=program,
        )

    @router.post(
        "/v1/programs/{program_id}/versions/{program_version}/enrollments",
        operation_id="createEducationEnrollment",
        response_model=EducationCommandResponse,
        responses=problem_responses(401, 403, 404, 409, 422, 503),
    )
    async def create_enrollment(
        request: EducationEnrollmentCreateRequest,
        principal: Annotated[ApiPrincipal, Depends(authenticate)],
        program_id: Annotated[str, ApiPath(pattern=RESOURCE_PATTERN)],
        program_version: Annotated[str, ApiPath(pattern=RESOURCE_PATTERN)],
        idempotency_key: Annotated[
            str,
            Header(alias="Idempotency-Key", pattern=IDEMPOTENCY_PATTERN),
        ],
    ) -> EducationCommandResponse:
        if principal.role is not ApiRole.LEARNER or "education:enroll:self" not in principal.scopes:
            raise ApiProblemError(
                status=403,
                code="education_enrollment_scope_forbidden",
                title="Learner self-enrollment scope is required",
            )
        if principal.organization_id is None:
            raise ApiProblemError(
                status=403,
                code="education_organization_required",
                title="A verified organization is required for enrollment",
            )
        _, reference = load_program(program_id, program_version)
        if reference.sha256 != request.expected_program_sha256:
            raise ApiProblemError(
                status=409,
                code="education_program_hash_conflict",
                title="Program content hash does not match the requested version",
            )
        response = await execute(
            EnrollCommand(
                program_selector=reference.selector,
                learner_ref=principal.subject,
                enrollment_id=_stable_enrollment_id(principal, idempotency_key),
                organization_id=principal.organization_id,
                actor_id=principal.subject,
                authority_context="verified_api_principal",
                idempotency_key=_scoped_idempotency_key(principal, idempotency_key),
            )
        )
        context = load_enrollment(response.enrollment_id)
        if (
            context.enrollment.learner_ref != principal.subject
            or context.organization_id != principal.organization_id
            or context.program_ref.selector != reference.selector
            or context.program_ref.sha256 != reference.sha256
        ):
            raise ApiProblemError(
                status=409,
                code="education_enrollment_integrity_failure",
                title="Education enrollment integrity verification failed",
            )
        return response

    @router.get(
        "/v1/enrollments/{enrollment_id}",
        operation_id="getEducationEnrollment",
        response_model=EducationEnrollmentView,
        responses=problem_responses(401, 403, 404, 409, 422, 503),
    )
    async def get_enrollment(
        enrollment_id: Annotated[str, ApiPath(pattern=RESOURCE_PATTERN)],
        principal: Annotated[ApiPrincipal, Depends(authenticate)],
    ) -> EducationEnrollmentView:
        context = load_enrollment(enrollment_id)
        require_assigned_actor(principal, context)
        return _enrollment_view(context)

    @router.post(
        "/v1/enrollments/{enrollment_id}/milestones/{milestone_id}/start",
        operation_id="startEducationMilestone",
        response_model=EducationCommandResponse,
        responses=problem_responses(401, 403, 404, 409, 422, 503),
    )
    async def start_milestone(
        request: EducationRevisionRequest,
        principal: Annotated[ApiPrincipal, Depends(authenticate)],
        enrollment_id: Annotated[str, ApiPath(pattern=RESOURCE_PATTERN)],
        milestone_id: Annotated[str, ApiPath(pattern=RESOURCE_PATTERN)],
        idempotency_key: Annotated[
            str,
            Header(alias="Idempotency-Key", pattern=IDEMPOTENCY_PATTERN),
        ],
    ) -> EducationCommandResponse:
        context = load_enrollment(enrollment_id)
        require_learner(principal, context)
        _milestone(context.program, milestone_id)
        return await execute(
            StartMilestoneCommand(
                enrollment_id=enrollment_id,
                milestone_id=milestone_id,
                actor_id=principal.subject,
                expected_revision=request.expected_revision,
                authority_context="verified_api_principal",
                idempotency_key=_scoped_idempotency_key(principal, idempotency_key),
            )
        )

    @router.post(
        "/v1/enrollments/{enrollment_id}/milestones/{milestone_id}/manual-confirmations",
        operation_id="recordEducationManualConfirmation",
        response_model=EducationCommandResponse,
        responses=problem_responses(401, 403, 404, 409, 422, 503),
    )
    async def record_manual_confirmation(
        request: EducationManualConfirmationRequest,
        principal: Annotated[ApiPrincipal, Depends(authenticate)],
        enrollment_id: Annotated[str, ApiPath(pattern=RESOURCE_PATTERN)],
        milestone_id: Annotated[str, ApiPath(pattern=RESOURCE_PATTERN)],
        idempotency_key: Annotated[
            str,
            Header(alias="Idempotency-Key", pattern=IDEMPOTENCY_PATTERN),
        ],
    ) -> EducationCommandResponse:
        context = load_enrollment(enrollment_id)
        require_organization(principal, context)
        role = _required_role(
            context.program,
            milestone_id,
            request.requirement_id,
            expected_kind="manual_confirmation",
        )
        require_reviewer(principal, context, role)
        return await execute(
            ManualConfirmationCommand(
                enrollment_id=enrollment_id,
                milestone_id=milestone_id,
                requirement_id=request.requirement_id,
                actor_id=principal.subject,
                actor_role=cast(
                    Literal["instructor", "mentor", "administrator"],
                    principal.role.value,
                ),
                evidence_ref=f"evidence:{request.evidence_id}",
                expected_revision=request.expected_revision,
                authority_context="verified_api_principal",
                idempotency_key=_scoped_idempotency_key(principal, idempotency_key),
            )
        )

    @router.post(
        "/v1/enrollments/{enrollment_id}/milestones/{milestone_id}/scores",
        operation_id="recordEducationScore",
        response_model=EducationCommandResponse,
        responses=problem_responses(401, 403, 404, 409, 422, 503),
    )
    async def record_score(
        request: EducationScoreRequest,
        principal: Annotated[ApiPrincipal, Depends(authenticate)],
        enrollment_id: Annotated[str, ApiPath(pattern=RESOURCE_PATTERN)],
        milestone_id: Annotated[str, ApiPath(pattern=RESOURCE_PATTERN)],
        idempotency_key: Annotated[
            str,
            Header(alias="Idempotency-Key", pattern=IDEMPOTENCY_PATTERN),
        ],
    ) -> EducationCommandResponse:
        context = load_enrollment(enrollment_id)
        require_organization(principal, context)
        role = _required_role(
            context.program,
            milestone_id,
            request.requirement_id,
            expected_kind="score_at_least",
        )
        require_reviewer(principal, context, role)
        return await execute(
            RecordScoreCommand(
                enrollment_id=enrollment_id,
                milestone_id=milestone_id,
                requirement_id=request.requirement_id,
                score=request.score,
                actor_id=principal.subject,
                actor_role=cast(
                    Literal["instructor", "mentor", "administrator"],
                    principal.role.value,
                ),
                evidence_ref=f"evidence:{request.evidence_id}",
                expected_revision=request.expected_revision,
                authority_context="verified_api_principal",
                idempotency_key=_scoped_idempotency_key(principal, idempotency_key),
            )
        )

    @router.post(
        "/v1/enrollments/{enrollment_id}/milestones/{milestone_id}/projects",
        operation_id="bindEducationProject",
        response_model=EducationCommandResponse,
        responses=problem_responses(401, 403, 404, 409, 422, 503),
    )
    async def bind_project(
        request: EducationProjectBindRequest,
        principal: Annotated[ApiPrincipal, Depends(authenticate)],
        enrollment_id: Annotated[str, ApiPath(pattern=RESOURCE_PATTERN)],
        milestone_id: Annotated[str, ApiPath(pattern=RESOURCE_PATTERN)],
        idempotency_key: Annotated[
            str,
            Header(alias="Idempotency-Key", pattern=IDEMPOTENCY_PATTERN),
        ],
    ) -> EducationCommandResponse:
        context = load_enrollment(enrollment_id)
        require_learner(principal, context)
        _milestone(context.program, milestone_id)
        return await execute(
            BindProjectCommand(
                enrollment_id=enrollment_id,
                milestone_id=milestone_id,
                project_id=request.project_id,
                actor_id=principal.subject,
                organization_id=context.organization_id,
                expected_revision=request.expected_revision,
                authority_context="verified_api_principal",
                idempotency_key=_scoped_idempotency_key(principal, idempotency_key),
            )
        )

    @router.post(
        "/v1/enrollments/{enrollment_id}/milestones/{milestone_id}/project-sync",
        operation_id="syncEducationProject",
        response_model=EducationCommandResponse,
        responses=problem_responses(401, 403, 404, 409, 422, 503),
    )
    async def sync_project(
        request: EducationRevisionRequest,
        principal: Annotated[ApiPrincipal, Depends(authenticate)],
        enrollment_id: Annotated[str, ApiPath(pattern=RESOURCE_PATTERN)],
        milestone_id: Annotated[str, ApiPath(pattern=RESOURCE_PATTERN)],
        idempotency_key: Annotated[
            str,
            Header(alias="Idempotency-Key", pattern=IDEMPOTENCY_PATTERN),
        ],
    ) -> EducationCommandResponse:
        context = load_enrollment(enrollment_id)
        require_assigned_actor(principal, context)
        _milestone(context.program, milestone_id)
        return await execute(
            SyncProjectCommand(
                enrollment_id=enrollment_id,
                milestone_id=milestone_id,
                actor_id=principal.subject,
                actor_role=cast(
                    Literal[
                        "learner",
                        "mentor",
                        "instructor",
                        "administrator",
                        "system",
                    ],
                    principal.role.value,
                ),
                organization_id=context.organization_id,
                expected_revision=request.expected_revision,
                authority_context="verified_api_principal",
                idempotency_key=_scoped_idempotency_key(principal, idempotency_key),
            )
        )

    @router.post(
        "/v1/enrollments/{enrollment_id}/completion-decisions",
        operation_id="decideEducationCompletion",
        response_model=EducationCommandResponse,
        responses=problem_responses(401, 403, 404, 409, 422, 503),
    )
    async def decide_completion(
        request: EducationCompletionDecisionRequest,
        principal: Annotated[ApiPrincipal, Depends(authenticate)],
        enrollment_id: Annotated[str, ApiPath(pattern=RESOURCE_PATTERN)],
        idempotency_key: Annotated[
            str,
            Header(alias="Idempotency-Key", pattern=IDEMPOTENCY_PATTERN),
        ],
    ) -> EducationCommandResponse:
        context = load_enrollment(enrollment_id)
        require_administrator(principal, context)
        return await execute(
            DecideProgramCompletionCommand(
                enrollment_id=enrollment_id,
                command=request.command,
                actor_id=principal.subject,
                actor_role="administrator",
                rationale=request.rationale,
                reopen_milestone_ids=request.reopen_milestone_ids,
                expected_revision=request.expected_revision,
                authority_context="verified_api_principal",
                idempotency_key=_scoped_idempotency_key(principal, idempotency_key),
            )
        )

    return router


__all__ = ["create_education_router"]
