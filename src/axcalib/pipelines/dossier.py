"""Independent, revision-aware dossier local pipelines."""

from __future__ import annotations

import asyncio
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from axcalib.dossier import RevisionConflictError, exclusive_file_lock
from axcalib.pipelines.base import PipelineContext
from axcalib.pipelines.project import LocalProjectService
from axcalib.schemas import DossierFreezeResult, PipelineResult, PipelineStatus, ReviewContext


class DossierInitializeRequest(BaseModel):
    """Strict input for ``dossier.initialize``."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    proposal_path: Path
    title: str = Field(min_length=1, max_length=300)
    sidecar_path: Path | None = None
    project_id: str | None = None
    review_profile: str | None = None
    review_context: ReviewContext = Field(default_factory=ReviewContext)


class DossierUpdateRequest(BaseModel):
    """Safe first update command; arbitrary field patches are not accepted."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    project_id: str
    expected_revision: int = Field(ge=1)
    progress_note: str = Field(min_length=1, max_length=4000)


class DossierFreezeRequest(BaseModel):
    """Freeze one exact expected revision."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    project_id: str
    expected_revision: int = Field(ge=1)


class DossierInitializePipeline:
    pipeline_id = "dossier.initialize"
    pipeline_version = "v1alpha1"

    def __init__(self, service: LocalProjectService) -> None:
        self.service = service

    def run(
        self,
        request: DossierInitializeRequest,
        *,
        context: PipelineContext | None = None,
    ) -> PipelineResult:
        if context is not None and context.cancellation_requested():
            raise TimeoutError("pipeline execution was cancelled before start")
        dossier = self.service.create_project(
            request.proposal_path,
            title=request.title,
            sidecar_path=request.sidecar_path,
            project_id=request.project_id,
            review_profile=request.review_profile,
            review_context=request.review_context,
        )
        return PipelineResult(
            pipeline_id=self.pipeline_id,
            pipeline_version=self.pipeline_version,
            status=PipelineStatus.SUCCEEDED,
            project_id=dossier.project_id,
            dossier_status=dossier.status,
            dossier_revision=dossier.revision,
            dossier_uri=str(self.service.dossiers.path_for(dossier.project_id)),
            message="프로젝트 dossier를 초기화했습니다.",
        )

    async def arun(
        self,
        request: DossierInitializeRequest,
        *,
        context: PipelineContext | None = None,
    ) -> PipelineResult:
        return await asyncio.to_thread(self.run, request, context=context)


class DossierUpdatePipeline:
    pipeline_id = "dossier.update"
    pipeline_version = "v1alpha1"

    def __init__(self, service: LocalProjectService) -> None:
        self.service = service

    def run(
        self,
        request: DossierUpdateRequest,
        *,
        context: PipelineContext | None = None,
    ) -> PipelineResult:
        if context is not None and context.cancellation_requested():
            raise TimeoutError("pipeline execution was cancelled before start")
        dossier = self.service.dossiers.load(request.project_id)
        if dossier.revision != request.expected_revision:
            return PipelineResult(
                pipeline_id=self.pipeline_id,
                pipeline_version=self.pipeline_version,
                status=PipelineStatus.STALE,
                project_id=dossier.project_id,
                dossier_status=dossier.status,
                dossier_revision=dossier.revision,
                dossier_uri=str(self.service.dossiers.path_for(dossier.project_id)),
                message=(
                    f"expected revision {request.expected_revision}; current revision is "
                    f"{dossier.revision}"
                ),
            )
        try:
            result = self.service.record_progress(
                request.project_id,
                note=request.progress_note,
                expected_revision=request.expected_revision,
            )
        except RevisionConflictError:
            current = self.service.dossiers.load(request.project_id)
            return PipelineResult(
                pipeline_id=self.pipeline_id,
                pipeline_version=self.pipeline_version,
                status=PipelineStatus.STALE,
                project_id=current.project_id,
                dossier_status=current.status,
                dossier_revision=current.revision,
                dossier_uri=str(self.service.dossiers.path_for(current.project_id)),
                message=(
                    f"expected revision {request.expected_revision}; current revision is "
                    f"{current.revision}"
                ),
            )
        return result.model_copy(
            update={
                "pipeline_id": self.pipeline_id,
                "pipeline_version": self.pipeline_version,
            }
        )

    async def arun(
        self,
        request: DossierUpdateRequest,
        *,
        context: PipelineContext | None = None,
    ) -> PipelineResult:
        return await asyncio.to_thread(self.run, request, context=context)


class DossierFreezePipeline:
    pipeline_id = "dossier.freeze"
    pipeline_version = "v1alpha1"

    def __init__(self, service: LocalProjectService) -> None:
        self.service = service

    def run(
        self,
        request: DossierFreezeRequest,
        *,
        context: PipelineContext | None = None,
    ) -> DossierFreezeResult:
        if context is not None and context.cancellation_requested():
            raise TimeoutError("pipeline execution was cancelled before start")
        dossier_path = self.service.dossiers.path_for(request.project_id)
        with exclusive_file_lock(dossier_path):
            dossier = self.service.dossiers.load(request.project_id)
            if dossier.revision != request.expected_revision:
                return DossierFreezeResult(
                    status=PipelineStatus.STALE,
                    project_id=dossier.project_id,
                    expected_revision=request.expected_revision,
                    current_revision=dossier.revision,
                    message="요청 revision이 현재 dossier와 달라 freeze하지 않았습니다.",
                )
            snapshot = self.service.snapshots.freeze(dossier)
        return DossierFreezeResult(
            status=PipelineStatus.SUCCEEDED,
            project_id=dossier.project_id,
            expected_revision=request.expected_revision,
            current_revision=dossier.revision,
            snapshot=snapshot,
            message="요청 revision을 불변 snapshot으로 고정했습니다.",
        )

    async def arun(
        self,
        request: DossierFreezeRequest,
        *,
        context: PipelineContext | None = None,
    ) -> DossierFreezeResult:
        return await asyncio.to_thread(self.run, request, context=context)


__all__ = [
    "DossierFreezePipeline",
    "DossierFreezeRequest",
    "DossierInitializePipeline",
    "DossierInitializeRequest",
    "DossierUpdatePipeline",
    "DossierUpdateRequest",
]
