"""HTTP-only request and response models for the runtime API slice."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from axcalib.pipelines import PipelineDescriptor
from axcalib.runtime import PipelineExecutionResult, PipelineRunStatus


class PipelineCatalogResponse(BaseModel):
    """Deterministic catalog of allowlisted local pipelines."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "axcalib.api-pipeline-catalog/v1alpha1"
    pipelines: tuple[PipelineDescriptor, ...]


class PipelineRunRequest(BaseModel):
    """Transport options plus one pipeline-specific JSON payload."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
    )
    idempotency_key: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
    )
    expected_revision: int | None = Field(default=None, ge=1)
    payload: dict[str, Any]


class PipelineRunView(BaseModel):
    """Filesystem-neutral execution result safe for HTTP delivery."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "axcalib.api-pipeline-run/v1alpha1"
    run_id: str
    pipeline_id: str
    pipeline_version: str
    status: PipelineRunStatus
    attempt: int = Field(ge=0)
    output: dict[str, Any] | None = None
    error_code: str | None = None
    replayed: bool = False
    updated_at: datetime | None = None

    @classmethod
    def from_execution(
        cls,
        value: PipelineExecutionResult,
        *,
        updated_at: datetime | None = None,
    ) -> PipelineRunView:
        """Remove local checkpoint paths from a transport-neutral result."""

        return cls(
            run_id=value.run_id,
            pipeline_id=value.pipeline_id,
            pipeline_version=value.pipeline_version,
            status=value.status,
            attempt=value.attempt,
            output=value.output,
            error_code=value.error_code,
            replayed=value.replayed,
            updated_at=updated_at,
        )


class CancelRunResponse(BaseModel):
    """Acknowledgement of a cooperative cancellation request."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "axcalib.api-cancel/v1alpha1"
    run_id: str
    status: PipelineRunStatus
    cancellation_requested: bool = True


class ValidationIssue(BaseModel):
    """Redacted validation location and code without rejected input values."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    location: str
    code: str


class Problem(BaseModel):
    """RFC 9457-shaped error body with AXCalib-stable machine codes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: str
    title: str
    status: int
    code: str
    detail: str | None = None
    issues: tuple[ValidationIssue, ...] = ()


__all__ = [
    "CancelRunResponse",
    "PipelineCatalogResponse",
    "PipelineRunRequest",
    "PipelineRunView",
    "Problem",
    "ValidationIssue",
]
