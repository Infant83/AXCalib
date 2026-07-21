"""Typed local pipeline for project transaction reconciliation."""

from __future__ import annotations

import asyncio

from pydantic import BaseModel, ConfigDict, Field

from axcalib.runtime import (
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
    ) -> TransactionReconcilePipelineResult:
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
    ) -> TransactionReconcilePipelineResult:
        return await asyncio.to_thread(self.run, request)


__all__ = [
    "TransactionReconcilePipeline",
    "TransactionReconcilePipelineResult",
    "TransactionReconcileRequest",
]
