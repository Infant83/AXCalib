"""Optional authenticated FastAPI adapter for the local pipeline runtime."""

from axcalib.api.app import create_app
from axcalib.api.auth import (
    ApiPipelineGrant,
    ApiPrincipal,
    ApiRole,
    RejectAllTokenVerifier,
    TokenVerifier,
)
from axcalib.api.models import (
    CancelRunResponse,
    PipelineCatalogResponse,
    PipelineRunRequest,
    PipelineRunView,
    Problem,
)

__all__ = [
    "ApiPipelineGrant",
    "ApiPrincipal",
    "ApiRole",
    "CancelRunResponse",
    "PipelineCatalogResponse",
    "PipelineRunRequest",
    "PipelineRunView",
    "Problem",
    "RejectAllTokenVerifier",
    "TokenVerifier",
    "create_app",
]
