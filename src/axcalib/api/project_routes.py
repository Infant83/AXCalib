"""Principal-bound project registration and HITL command routes."""

import asyncio
import hashlib
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Header
from fastapi import Path as ApiPath

from axcalib.client import AXCalib
from axcalib.dossier import (
    DossierAlreadyExistsError,
    DossierNotFoundError,
    RevisionConflictError,
)
from axcalib.ingest import PptxSourceError
from axcalib.ingest.pptx import sha256_file
from axcalib.pipelines import ProjectSourceIntegrityError
from axcalib.runtime import TransactionBlockedError
from axcalib.schemas import PipelineResult, ProjectDossier, ReviewContext
from axcalib.workflows.two_gate import WorkflowError

from .artifacts import ArtifactPurpose, StagedArtifactResolver
from .auth import ApiPrincipal, ApiRole
from .models import (
    PPTX_MEDIA_TYPE,
    CompletionDecisionRequest,
    ProjectArtifactView,
    ProjectCommandResponse,
    ProjectRegistrationRequest,
    ProjectRegistrationResponse,
    RegistrationDecisionRequest,
    StagedArtifactRef,
)
from .problems import ApiProblemError, problem_responses

JSON_MEDIA_TYPE = "application/json"
MAX_STAGED_PPTX_BYTES = 64 * 1024 * 1024
MAX_STAGED_SIDECAR_BYTES = 2 * 1024 * 1024

AuthenticationDependency = Callable[..., Awaitable[ApiPrincipal]]


def _project_id(principal: ApiPrincipal, idempotency_key: str) -> str:
    identity = f"{principal.subject}\0projects:create\0{idempotency_key}".encode()
    return f"api-{hashlib.sha256(identity).hexdigest()[:32]}"


def _project_command_view(value: PipelineResult) -> ProjectCommandResponse:
    return ProjectCommandResponse(
        project_id=value.project_id,
        status=value.status.value,
        dossier_status=value.dossier_status,
        dossier_revision=value.dossier_revision,
        report_id=value.report_id,
        allowed_commands=value.allowed_commands,
        message=value.message,
    )


def _project_registration_view(
    dossier: ProjectDossier,
    *,
    replayed: bool,
) -> ProjectRegistrationResponse:
    artifact = dossier.artifacts[0]
    proposer_org_id = dossier.review_context.proposer_org_id
    if proposer_org_id is None:
        raise RuntimeError("API-created dossier is missing proposer organization")
    return ProjectRegistrationResponse(
        project_id=dossier.project_id,
        display_id=dossier.display_id,
        title=dossier.title,
        status=dossier.status,
        revision=dossier.revision,
        proposer_org_id=proposer_org_id,
        artifact=ProjectArtifactView(
            artifact_id=artifact.artifact_id,
            role=artifact.role,
            media_type=artifact.media_type,
            sha256=artifact.sha256,
            byte_size=artifact.byte_size,
        ),
        replayed=replayed,
    )


def _matches_project_registration(
    dossier: ProjectDossier,
    request: ProjectRegistrationRequest,
    review_context: ReviewContext,
) -> bool:
    artifact = dossier.artifacts[0] if dossier.artifacts else None
    sidecar_sha = artifact.metadata.get("sidecar_sha256") if artifact else None
    sidecar_size = artifact.metadata.get("sidecar_byte_size") if artifact else None
    sidecar_media_type = artifact.metadata.get("sidecar_media_type") if artifact else None
    expected_sidecar_sha = request.sidecar.sha256 if request.sidecar else None
    expected_sidecar_size = str(request.sidecar.byte_size) if request.sidecar else None
    expected_sidecar_media_type = request.sidecar.media_type if request.sidecar else None
    return (
        dossier.title == request.title.strip()
        and dossier.review_context == review_context
        and artifact is not None
        and artifact.sha256 == request.proposal.sha256
        and artifact.byte_size == request.proposal.byte_size
        and artifact.media_type == request.proposal.media_type
        and sidecar_sha == expected_sidecar_sha
        and sidecar_size == expected_sidecar_size
        and sidecar_media_type == expected_sidecar_media_type
        and (
            request.review_profile is None
            or (
                dossier.review_profile is not None
                and dossier.review_profile.selector == request.review_profile
            )
        )
    )


def _has_principal_creation_audit(
    client: AXCalib,
    dossier: ProjectDossier,
    principal: ApiPrincipal,
) -> bool:
    return any(
        event.get("event_id") in dossier.audit_event_ids
        and event.get("project_id") == dossier.project_id
        and event.get("event_type") == "project_created"
        and event.get("actor_id") == principal.subject
        and event.get("actor_role") == principal.role.value
        and event.get("dossier_revision") == 1
        for event in client.service.audit.entries()
    )


def create_project_router(
    client: AXCalib,
    *,
    authenticate: AuthenticationDependency,
    artifact_resolver: StagedArtifactResolver,
) -> APIRouter:
    """Build project routes with deployment-owned auth and staging ports."""

    router = APIRouter()

    def validate_staged_artifact_claim(
        artifact: StagedArtifactRef,
        *,
        purpose: ArtifactPurpose,
    ) -> str:
        expected_media_type = (
            PPTX_MEDIA_TYPE if purpose == "registration_proposal" else JSON_MEDIA_TYPE
        )
        maximum_bytes = (
            MAX_STAGED_PPTX_BYTES
            if purpose == "registration_proposal"
            else MAX_STAGED_SIDECAR_BYTES
        )
        expected_suffix = ".pptx" if purpose == "registration_proposal" else ".json"
        if artifact.media_type != expected_media_type:
            raise ApiProblemError(
                status=422,
                code="staged_artifact_media_type_invalid",
                title="Staged artifact media type is not allowed for this purpose",
            )
        if artifact.byte_size > maximum_bytes:
            raise ApiProblemError(
                status=413,
                code="staged_artifact_too_large",
                title="Staged artifact exceeds the API Alpha size limit",
            )
        return expected_suffix

    async def resolve_staged_artifact(
        artifact: StagedArtifactRef,
        *,
        principal: ApiPrincipal,
        purpose: ArtifactPurpose,
    ) -> Path:
        expected_suffix = validate_staged_artifact_claim(artifact, purpose=purpose)
        try:
            candidate = await asyncio.to_thread(
                artifact_resolver.resolve,
                artifact,
                principal=principal,
                purpose=purpose,
            )
        except Exception as error:
            raise ApiProblemError(
                status=503,
                code="staged_artifact_service_unavailable",
                title="Staged artifact service is unavailable",
            ) from error
        if candidate is None:
            raise ApiProblemError(
                status=404,
                code="staged_artifact_not_found",
                title="Staged artifact is unavailable to this caller",
            )
        try:
            path = Path(candidate).resolve(strict=True)
            stat = path.stat()
        except (OSError, RuntimeError) as error:
            raise ApiProblemError(
                status=409,
                code="staged_artifact_integrity_failure",
                title="Staged artifact integrity verification failed",
            ) from error
        if (
            not path.is_file()
            or path.suffix.casefold() != expected_suffix
            or stat.st_size != artifact.byte_size
        ):
            raise ApiProblemError(
                status=409,
                code="staged_artifact_integrity_failure",
                title="Staged artifact integrity verification failed",
            )
        try:
            actual_sha256 = await asyncio.to_thread(sha256_file, path)
        except OSError as error:
            raise ApiProblemError(
                status=409,
                code="staged_artifact_integrity_failure",
                title="Staged artifact integrity verification failed",
            ) from error
        if actual_sha256 != artifact.sha256:
            raise ApiProblemError(
                status=409,
                code="staged_artifact_integrity_failure",
                title="Staged artifact integrity verification failed",
            )
        return path

    def require_project_creation(principal: ApiPrincipal) -> str:
        if principal.role not in {ApiRole.PROJECT_OWNER, ApiRole.ADMINISTRATOR}:
            raise ApiProblemError(
                status=403,
                code="project_creation_role_forbidden",
                title="Project owner or administrator role is required",
            )
        if "projects:create" not in principal.scopes:
            raise ApiProblemError(
                status=403,
                code="project_creation_scope_forbidden",
                title="Project creation scope is required",
            )
        if principal.organization_id is None:
            raise ApiProblemError(
                status=403,
                code="project_organization_required",
                title="A verified organization is required for project creation",
            )
        return principal.organization_id

    def load_authorized_decision_project(
        principal: ApiPrincipal,
        project_id: str,
    ) -> ProjectDossier:
        if principal.role is not ApiRole.ADMINISTRATOR:
            raise ApiProblemError(
                status=403,
                code="administrator_role_required",
                title="Administrator role is required",
            )
        if (
            "projects:decide:any" not in principal.scopes
            and f"project:{project_id}:decide" not in principal.scopes
        ):
            raise ApiProblemError(
                status=403,
                code="project_decision_scope_forbidden",
                title="Project decision scope is required",
            )
        try:
            dossier = client.service.dossiers.load(project_id)
        except DossierNotFoundError as error:
            raise ApiProblemError(
                status=404,
                code="project_not_found",
                title="Project was not found",
            ) from error
        organization_id = dossier.review_context.proposer_org_id
        organization_allowed = (
            "organizations:any" in principal.scopes
            or (
                organization_id is not None
                and f"organization:{organization_id}:access" in principal.scopes
            )
            or (organization_id is not None and principal.organization_id == organization_id)
        )
        if not organization_allowed:
            raise ApiProblemError(
                status=403,
                code="project_organization_forbidden",
                title="Caller organization cannot access this project",
            )
        return dossier

    @router.post(
        "/v1/projects",
        operation_id="registerProject",
        response_model=ProjectRegistrationResponse,
        responses=problem_responses(401, 403, 404, 409, 413, 422, 503),
    )
    async def register_project(
        request: ProjectRegistrationRequest,
        principal: Annotated[ApiPrincipal, Depends(authenticate)],
        idempotency_key: Annotated[
            str,
            Header(
                alias="Idempotency-Key",
                pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
            ),
        ],
    ) -> ProjectRegistrationResponse:
        organization_id = require_project_creation(principal)
        validate_staged_artifact_claim(
            request.proposal,
            purpose="registration_proposal",
        )
        if request.sidecar is not None:
            validate_staged_artifact_claim(
                request.sidecar,
                purpose="pptx_sidecar",
            )
        project_id = _project_id(principal, idempotency_key)
        review_context = ReviewContext(
            proposer_org_id=organization_id,
            certification_level=request.certification_level,
        )
        try:
            existing = client.service.dossiers.load(project_id)
        except DossierNotFoundError:
            existing = None
        if existing is not None:
            if not _has_principal_creation_audit(client, existing, principal):
                raise ApiProblemError(
                    status=409,
                    code="project_registration_integrity_failure",
                    title="Project registration audit integrity verification failed",
                )
            if not _matches_project_registration(existing, request, review_context):
                raise ApiProblemError(
                    status=409,
                    code="project_registration_conflict",
                    title="Idempotency key was reused with a different request",
                )
            return _project_registration_view(existing, replayed=True)
        proposal_path = await resolve_staged_artifact(
            request.proposal,
            principal=principal,
            purpose="registration_proposal",
        )
        sidecar_path = None
        if request.sidecar is not None:
            sidecar_path = await resolve_staged_artifact(
                request.sidecar,
                principal=principal,
                purpose="pptx_sidecar",
            )
        actor_role = "project_owner" if principal.role is ApiRole.PROJECT_OWNER else "administrator"
        try:
            dossier = await asyncio.to_thread(
                client.register_case,
                proposal_path,
                title=request.title,
                sidecar_path=sidecar_path,
                project_id=project_id,
                review_profile=request.review_profile,
                review_context=review_context,
                actor_id=principal.subject,
                actor_role=actor_role,
                expected_proposal_sha256=request.proposal.sha256,
                expected_sidecar_sha256=(
                    request.sidecar.sha256 if request.sidecar is not None else None
                ),
            )
            return _project_registration_view(dossier, replayed=False)
        except (DossierAlreadyExistsError, TransactionBlockedError):
            try:
                existing = client.service.dossiers.load(project_id)
            except DossierNotFoundError as error:
                raise ApiProblemError(
                    status=409,
                    code="project_registration_conflict",
                    title="Project registration conflicts with persisted state",
                ) from error
            if not _has_principal_creation_audit(client, existing, principal):
                raise ApiProblemError(
                    status=409,
                    code="project_registration_integrity_failure",
                    title="Project registration audit integrity verification failed",
                ) from None
            if not _matches_project_registration(existing, request, review_context):
                raise ApiProblemError(
                    status=409,
                    code="project_registration_conflict",
                    title="Idempotency key was reused with a different request",
                ) from None
            return _project_registration_view(existing, replayed=True)
        except ApiProblemError:
            raise
        except ProjectSourceIntegrityError as error:
            raise ApiProblemError(
                status=409,
                code="staged_artifact_integrity_failure",
                title="Staged artifact integrity verification failed",
            ) from error
        except (KeyError, PptxSourceError, ValueError) as error:
            raise ApiProblemError(
                status=422,
                code="project_registration_invalid",
                title="Project registration failed validation",
            ) from error

    @router.post(
        "/v1/projects/{project_id}/decisions/registration",
        operation_id="decideProjectRegistration",
        response_model=ProjectCommandResponse,
        responses=problem_responses(401, 403, 404, 409, 422, 503),
    )
    async def decide_project_registration(
        request: RegistrationDecisionRequest,
        project_id: Annotated[
            str,
            ApiPath(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$"),
        ],
        principal: Annotated[ApiPrincipal, Depends(authenticate)],
    ) -> ProjectCommandResponse:
        load_authorized_decision_project(principal, project_id)
        try:
            result = await asyncio.to_thread(
                client.decide_registration,
                project_id,
                command=request.command,
                actor_id=principal.subject,
                rationale=request.rationale,
                adjustments=request.adjustments,
                expected_revision=request.expected_revision,
            )
        except RevisionConflictError as error:
            raise ApiProblemError(
                status=409,
                code="stale_project_revision",
                title="Project revision is stale",
            ) from error
        except WorkflowError as error:
            raise ApiProblemError(
                status=409,
                code="project_transition_conflict",
                title="Project state does not allow this command",
            ) from error
        except ValueError as error:
            raise ApiProblemError(
                status=422,
                code="project_decision_invalid",
                title="Project decision failed validation",
            ) from error
        return _project_command_view(result)

    @router.post(
        "/v1/projects/{project_id}/decisions/completion",
        operation_id="decideProjectCompletion",
        response_model=ProjectCommandResponse,
        responses=problem_responses(401, 403, 404, 409, 422, 503),
    )
    async def decide_project_completion(
        request: CompletionDecisionRequest,
        project_id: Annotated[
            str,
            ApiPath(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$"),
        ],
        principal: Annotated[ApiPrincipal, Depends(authenticate)],
    ) -> ProjectCommandResponse:
        load_authorized_decision_project(principal, project_id)
        try:
            result = await asyncio.to_thread(
                client.decide_completion,
                project_id,
                command=request.command,
                actor_id=principal.subject,
                rationale=request.rationale,
                adjustments=request.adjustments,
                expected_revision=request.expected_revision,
            )
        except RevisionConflictError as error:
            raise ApiProblemError(
                status=409,
                code="stale_project_revision",
                title="Project revision is stale",
            ) from error
        except WorkflowError as error:
            raise ApiProblemError(
                status=409,
                code="project_transition_conflict",
                title="Project state does not allow this command",
            ) from error
        except ValueError as error:
            raise ApiProblemError(
                status=422,
                code="project_decision_invalid",
                title="Project decision failed validation",
            ) from error
        return _project_command_view(result)

    return router


__all__ = ["create_project_router"]
