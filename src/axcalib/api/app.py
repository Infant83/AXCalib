"""Authenticated FastAPI adapter over the AXCalib local pipeline runtime."""

import hashlib
import uuid
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, Security
from fastapi import Path as ApiPath
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import ValidationError

from axcalib.client import AXCalib
from axcalib.pipelines import PipelineContext
from axcalib.runtime import PipelineRunConflictError, PipelineRunIntegrityError

from .artifacts import RejectAllStagedArtifactResolver, StagedArtifactResolver
from .auth import (
    ApiPipelineGrant,
    ApiPrincipal,
    ApiRole,
    RejectAllTokenVerifier,
    TokenVerifier,
)
from .models import (
    CancelRunResponse,
    PipelineCatalogResponse,
    PipelineRunRequest,
    PipelineRunView,
    Problem,
    ValidationIssue,
)
from .problems import ApiProblemError, problem_response, problem_responses
from .project_routes import create_project_router

PROBLEM_TYPE_BASE = "https://axcalib.local/problems"
JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
RESERVED_AUTHORITY_FIELDS = frozenset(
    {
        "actor_id",
        "actor_role",
        "administrator_id",
        "registration_decision",
        "completion_decision",
        "approval_actor_id",
        "approval_actor_role",
    }
)


def _stable_run_id(
    request: PipelineRunRequest,
    principal: ApiPrincipal,
    idempotency_key: str | None,
) -> str:
    if request.run_id is not None:
        return request.run_id
    if idempotency_key is not None:
        identity = f"{principal.subject}\0{idempotency_key}".encode()
        return f"api-{hashlib.sha256(identity).hexdigest()[:32]}"
    return f"api-{uuid.uuid4()}"


def _reserved_authority_locations(value: Any, prefix: str = "payload") -> tuple[str, ...]:
    locations: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            location = f"{prefix}.{key}"
            if key in RESERVED_AUTHORITY_FIELDS:
                locations.append(location)
            locations.extend(_reserved_authority_locations(nested, location))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            locations.extend(_reserved_authority_locations(nested, f"{prefix}.{index}"))
    return tuple(locations)


def create_app(
    client: AXCalib,
    *,
    token_verifier: TokenVerifier | None = None,
    pipeline_grants: tuple[ApiPipelineGrant, ...] = (),
    artifact_resolver: StagedArtifactResolver | None = None,
) -> FastAPI:
    """Create a fail-closed HTTP adapter over one configured AXCalib client."""

    verifier = token_verifier or RejectAllTokenVerifier()
    staged_artifacts = artifact_resolver or RejectAllStagedArtifactResolver()
    grants: dict[tuple[str, str], ApiPipelineGrant] = {}
    registered = frozenset(client.registry.keys())
    for grant in pipeline_grants:
        key = (grant.pipeline_id, grant.pipeline_version)
        if key not in registered:
            raise ValueError(
                f"API pipeline grant is not registered: {grant.pipeline_id}@"
                f"{grant.pipeline_version}"
            )
        if key in grants:
            raise ValueError(
                f"duplicate API pipeline grant: {grant.pipeline_id}@{grant.pipeline_version}"
            )
        grants[key] = grant
    bearer = HTTPBearer(auto_error=False, scheme_name="bearerAuth")
    app = FastAPI(
        title="AXCalib Runtime API",
        summary="Authenticated HTTP parity for allowlisted AXCalib pipelines",
        version="v1alpha1",
        openapi_version="3.1.0",
    )

    async def authenticate(
        credentials: Annotated[
            HTTPAuthorizationCredentials | None,
            Security(bearer),
        ],
    ) -> ApiPrincipal:
        if credentials is None or credentials.scheme.lower() != "bearer":
            raise ApiProblemError(
                status=401,
                code="authentication_required",
                title="Bearer authentication is required",
            )
        try:
            raw_principal = verifier.verify(credentials.credentials)
            principal = (
                ApiPrincipal.model_validate(raw_principal) if raw_principal is not None else None
            )
        except Exception as error:
            raise ApiProblemError(
                status=503,
                code="authentication_unavailable",
                title="Authentication service is unavailable",
            ) from error
        if principal is None:
            raise ApiProblemError(
                status=401,
                code="invalid_bearer_token",
                title="Bearer token is invalid",
            )
        return principal

    @app.exception_handler(ApiProblemError)
    async def handle_api_problem(_request: Request, error: ApiProblemError) -> JSONResponse:
        return problem_response(
            Problem(
                type=f"{PROBLEM_TYPE_BASE}/{error.code}",
                title=error.title,
                status=error.status,
                code=error.code,
                detail=error.detail,
                issues=error.issues,
            )
        )

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation(
        _request: Request,
        error: RequestValidationError,
    ) -> JSONResponse:
        issues = tuple(
            ValidationIssue(
                location=".".join(str(part) for part in item.get("loc", ())),
                code=str(item.get("type", "validation_error")),
            )
            for item in error.errors()
        )
        return problem_response(
            Problem(
                type=f"{PROBLEM_TYPE_BASE}/request-invalid",
                title="Request validation failed",
                status=422,
                code="request_invalid",
                issues=issues,
            )
        )

    @app.get(
        "/v1/pipelines",
        operation_id="listPipelines",
        response_model=PipelineCatalogResponse,
        responses=problem_responses(401, 503),
    )
    async def list_pipelines(
        _principal: Annotated[ApiPrincipal, Depends(authenticate)],
    ) -> PipelineCatalogResponse:
        pipelines = tuple(
            descriptor
            for descriptor in client.registry.descriptors()
            if (descriptor.pipeline_id, descriptor.pipeline_version) in grants
        )
        return PipelineCatalogResponse(pipelines=pipelines)

    app.include_router(
        create_project_router(
            client,
            authenticate=authenticate,
            artifact_resolver=staged_artifacts,
        )
    )

    @app.post(
        "/v1/pipelines/{pipeline_id}/versions/{pipeline_version}/runs",
        operation_id="runPipeline",
        response_model=PipelineRunView,
        responses=problem_responses(401, 403, 404, 409, 422, 503),
    )
    async def run_pipeline(
        request: PipelineRunRequest,
        principal: Annotated[ApiPrincipal, Depends(authenticate)],
        pipeline_id: Annotated[
            str,
            ApiPath(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"),
        ],
        pipeline_version: Annotated[
            str,
            ApiPath(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"),
        ],
        idempotency_key_header: Annotated[
            str | None,
            Header(
                alias="Idempotency-Key",
                pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
            ),
        ] = None,
    ) -> PipelineRunView:
        grant = grants.get((pipeline_id, pipeline_version))
        if grant is None:
            raise ApiProblemError(
                status=404,
                code="pipeline_not_found",
                title="Pipeline is not exposed by the API allowlist",
            )
        if principal.role not in grant.execute_roles:
            raise ApiProblemError(
                status=403,
                code="pipeline_role_forbidden",
                title="Caller role cannot execute this pipeline",
            )
        authority_locations = _reserved_authority_locations(request.payload)
        if authority_locations:
            raise ApiProblemError(
                status=422,
                code="authority_field_forbidden",
                title="Generic pipeline payload cannot carry human authority fields",
                issues=tuple(
                    ValidationIssue(location=location, code="authority_field_forbidden")
                    for location in authority_locations
                ),
            )
        if (
            request.idempotency_key is not None
            and idempotency_key_header is not None
            and request.idempotency_key != idempotency_key_header
        ):
            raise ApiProblemError(
                status=422,
                code="idempotency_key_conflict",
                title="Body and header idempotency keys do not match",
            )
        idempotency_key = idempotency_key_header or request.idempotency_key
        try:
            validated_request = client.registry.validate_request(
                pipeline_id,
                pipeline_version,
                request.payload,
            )
        except ValidationError as error:
            issues = tuple(
                ValidationIssue(
                    location="payload." + ".".join(str(part) for part in item.get("loc", ())),
                    code=str(item.get("type", "validation_error")),
                )
                for item in error.errors()
            )
            raise ApiProblemError(
                status=422,
                code="pipeline_request_invalid",
                title="Pipeline payload validation failed",
                issues=issues,
            ) from error
        domain_revision = getattr(validated_request, "expected_revision", None)
        if (
            request.expected_revision is not None
            and isinstance(domain_revision, int)
            and request.expected_revision != domain_revision
        ):
            raise ApiProblemError(
                status=422,
                code="revision_context_conflict",
                title="Envelope and pipeline revisions do not match",
            )
        expected_revision = request.expected_revision
        if expected_revision is None and isinstance(domain_revision, int):
            expected_revision = domain_revision
        context = PipelineContext(
            run_id=_stable_run_id(request, principal, idempotency_key),
            actor_id=principal.subject,
            actor_role=principal.role.value,
            idempotency_key=idempotency_key,
            expected_revision=expected_revision,
            metadata={"transport": "api"},
        )
        try:
            result = await client.aexecute_pipeline(
                pipeline_id,
                pipeline_version,
                validated_request,
                context=context,
            )
        except PipelineRunConflictError as error:
            raise ApiProblemError(
                status=409,
                code="run_conflict",
                title="Run identity conflicts with an existing request",
            ) from error
        except (PipelineRunIntegrityError, ValidationError, UnicodeError) as error:
            raise ApiProblemError(
                status=409,
                code="run_integrity_failure",
                title="Persisted run integrity verification failed",
            ) from error
        return PipelineRunView.from_execution(result)

    @app.get(
        "/v1/runs/{run_id}",
        operation_id="getRun",
        response_model=PipelineRunView,
        responses=problem_responses(401, 403, 404, 409, 422, 503),
    )
    async def get_run(
        run_id: Annotated[
            str,
            ApiPath(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"),
        ],
        principal: Annotated[ApiPrincipal, Depends(authenticate)],
    ) -> PipelineRunView:
        try:
            record = client.executor.load(run_id)
        except FileNotFoundError as error:
            raise ApiProblemError(
                status=404,
                code="run_not_found",
                title="Pipeline run was not found",
            ) from error
        except (ValidationError, UnicodeError) as error:
            raise ApiProblemError(
                status=409,
                code="run_integrity_failure",
                title="Persisted run integrity verification failed",
            ) from error
        if (
            principal.role is not ApiRole.ADMINISTRATOR
            and "runs:read:any" not in principal.scopes
            and record.context.actor_id != principal.subject
        ):
            raise ApiProblemError(
                status=403,
                code="run_access_forbidden",
                title="Caller cannot inspect this pipeline run",
            )
        try:
            return PipelineRunView.from_execution(
                client.executor.inspect(run_id),
                updated_at=record.updated_at,
            )
        except (PipelineRunIntegrityError, ValidationError, UnicodeError) as error:
            raise ApiProblemError(
                status=409,
                code="run_integrity_failure",
                title="Persisted run integrity verification failed",
            ) from error

    @app.post(
        "/v1/runs/{run_id}/cancel",
        operation_id="cancelRun",
        response_model=CancelRunResponse,
        responses=problem_responses(401, 403, 404, 409, 422, 503),
    )
    async def cancel_run(
        run_id: Annotated[
            str,
            ApiPath(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"),
        ],
        principal: Annotated[ApiPrincipal, Depends(authenticate)],
    ) -> CancelRunResponse:
        try:
            record = client.executor.load(run_id)
        except FileNotFoundError as error:
            raise ApiProblemError(
                status=404,
                code="run_not_found",
                title="Pipeline run was not found",
            ) from error
        except (ValidationError, UnicodeError) as error:
            raise ApiProblemError(
                status=409,
                code="run_integrity_failure",
                title="Persisted run integrity verification failed",
            ) from error
        if principal.role is ApiRole.VIEWER:
            raise ApiProblemError(
                status=403,
                code="operator_role_required",
                title="Operator role is required",
            )
        if (
            principal.role is not ApiRole.ADMINISTRATOR
            and "runs:cancel:any" not in principal.scopes
            and record.context.actor_id != principal.subject
        ):
            raise ApiProblemError(
                status=403,
                code="run_access_forbidden",
                title="Caller cannot cancel this pipeline run",
            )
        client.executor.request_cancel(run_id, actor_id=principal.subject)
        return CancelRunResponse(run_id=run_id, status=record.status)

    def openapi() -> dict[str, Any]:
        if app.openapi_schema is not None:
            return app.openapi_schema
        schema = get_openapi(
            title=app.title,
            version=app.version,
            summary=app.summary,
            routes=app.routes,
            openapi_version=app.openapi_version,
        )
        schema["jsonSchemaDialect"] = JSON_SCHEMA_DIALECT
        schema["servers"] = [{"url": "/", "description": "Deployment-relative base URL"}]
        schema["x-axcalib-contract"] = {
            "status": "implemented-local-alpha",
            "scope": (
                "pipeline catalog/run/status/cancel plus principal-bound project "
                "registration and HITL decisions"
            ),
            "authority": (
                "verified principal, role, scope, organization and domain HITL guards "
                "are all required"
            ),
            "artifact_boundary": (
                "opaque staged artifact ID with byte-size and SHA-256 verification; "
                "caller local paths are forbidden"
            ),
        }
        for path_item in schema.get("paths", {}).values():
            for operation in path_item.values():
                if not isinstance(operation, dict):
                    continue
                for status, response in operation.get("responses", {}).items():
                    if not str(status).startswith(("4", "5")):
                        continue
                    content = response.get("content", {})
                    if "application/json" in content:
                        content["application/problem+json"] = content.pop("application/json")
        app.openapi_schema = schema
        return schema

    app.openapi = openapi
    return app


__all__ = ["create_app"]
