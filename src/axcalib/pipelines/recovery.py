"""Typed local pipeline for project transaction reconciliation."""

from __future__ import annotations

import asyncio

from pydantic import BaseModel, ConfigDict, Field

from axcalib.pipelines.base import PipelineContext
from axcalib.runtime import (
    EnrollmentReconciliationResult,
    EnrollmentTransactionCoordinator,
    LocalWorkspaceMaintenance,
    MaintenanceResult,
    ProjectTransactionCoordinator,
    TransactionReconciliationResult,
)
from axcalib.schemas import PipelineStatus


class TransactionReconcileRequest(BaseModel):
    """Reconcile one transaction or every local journal when omitted."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    transaction_id: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
    )


class TransactionReconcilePipelineResult(BaseModel):
    """Transport-neutral batch result with per-transaction status."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pipeline_id: str = "project.transaction.reconcile"
    pipeline_version: str = "v1alpha1"
    status: PipelineStatus
    results: tuple[TransactionReconciliationResult, ...]
    message: str


class TransactionReconcilePipeline:
    """Allowlisted reconciliation application service."""

    pipeline_id = "project.transaction.reconcile"
    pipeline_version = "v1alpha1"

    def __init__(self, coordinator: ProjectTransactionCoordinator) -> None:
        self.coordinator = coordinator

    def run(
        self,
        request: TransactionReconcileRequest,
        *,
        context: PipelineContext | None = None,
    ) -> TransactionReconcilePipelineResult:
        if context is not None and context.cancellation_requested():
            raise TimeoutError("pipeline execution was cancelled before start")
        if request.transaction_id:
            results = (self.coordinator.reconcile(request.transaction_id),)
        else:
            results = self.coordinator.reconcile_all()
        blocked = any(item.status == "blocked" for item in results)
        return TransactionReconcilePipelineResult(
            status=PipelineStatus.BLOCKED if blocked else PipelineStatus.SUCCEEDED,
            results=results,
            message=(
                "복구할 수 없는 불일치가 있어 자동 상태 승격을 차단했습니다."
                if blocked
                else "transaction journal 대조를 완료했습니다."
            ),
        )

    async def arun(
        self,
        request: TransactionReconcileRequest,
        *,
        context: PipelineContext | None = None,
    ) -> TransactionReconcilePipelineResult:
        return await asyncio.to_thread(self.run, request, context=context)


class EducationTransactionReconcilePipelineResult(BaseModel):
    """Per-enrollment transaction reconciliation result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pipeline_id: str = "education.transaction.reconcile"
    pipeline_version: str = "v1alpha1"
    status: PipelineStatus
    results: tuple[EnrollmentReconciliationResult, ...]
    message: str


class EducationTransactionReconcilePipeline:
    """Allowlisted reconciliation service for education transactions."""

    pipeline_id = "education.transaction.reconcile"
    pipeline_version = "v1alpha1"

    def __init__(self, coordinator: EnrollmentTransactionCoordinator) -> None:
        self.coordinator = coordinator

    def run(
        self,
        request: TransactionReconcileRequest,
        *,
        context: PipelineContext | None = None,
    ) -> EducationTransactionReconcilePipelineResult:
        if context is not None and context.cancellation_requested():
            raise TimeoutError("pipeline execution was cancelled before start")
        if request.transaction_id:
            results = (self.coordinator.reconcile(request.transaction_id),)
        else:
            results = self.coordinator.reconcile_all()
        blocked = any(item.status == "blocked" for item in results)
        return EducationTransactionReconcilePipelineResult(
            status=PipelineStatus.BLOCKED if blocked else PipelineStatus.SUCCEEDED,
            results=results,
            message=(
                "교육 transaction에 수동 확인이 필요한 불일치가 있습니다."
                if blocked
                else "교육 transaction journal 대조를 완료했습니다."
            ),
        )

    async def arun(
        self,
        request: TransactionReconcileRequest,
        *,
        context: PipelineContext | None = None,
    ) -> EducationTransactionReconcilePipelineResult:
        return await asyncio.to_thread(self.run, request, context=context)


class WorkspaceMaintenanceRequest(BaseModel):
    """Conservative local maintenance options; report-only is the default."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    apply: bool = False
    stale_after_seconds: float = Field(default=3600.0, gt=0.0)
    retention_seconds: float = Field(default=7 * 24 * 3600.0, gt=0.0)
    quarantine_blocked_journals: bool = False


class WorkspaceMaintenancePipeline:
    """Allowlisted report/apply wrapper around local workspace maintenance."""

    pipeline_id = "workspace.maintenance"
    pipeline_version = "v1alpha1"

    def __init__(self, service: LocalWorkspaceMaintenance) -> None:
        self.service = service

    def run(
        self,
        request: WorkspaceMaintenanceRequest,
        *,
        context: PipelineContext | None = None,
    ) -> MaintenanceResult:
        if context is not None and context.cancellation_requested():
            raise TimeoutError("pipeline execution was cancelled before start")
        return self.service.run(
            apply=request.apply,
            stale_after_seconds=request.stale_after_seconds,
            retention_seconds=request.retention_seconds,
            quarantine_blocked_journals=request.quarantine_blocked_journals,
        )

    async def arun(
        self,
        request: WorkspaceMaintenanceRequest,
        *,
        context: PipelineContext | None = None,
    ) -> MaintenanceResult:
        return await asyncio.to_thread(self.run, request, context=context)


__all__ = [
    "EducationTransactionReconcilePipeline",
    "EducationTransactionReconcilePipelineResult",
    "TransactionReconcilePipeline",
    "TransactionReconcilePipelineResult",
    "TransactionReconcileRequest",
    "WorkspaceMaintenancePipeline",
    "WorkspaceMaintenanceRequest",
]
