from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier

import pytest
from pydantic import BaseModel, ConfigDict, Field

from axcalib.pipelines import PipelineContext, PipelineRegistry
from axcalib.runtime import (
    LocalPipelineExecutor,
    LocalPipelineJobQueue,
    PipelineJobIntegrityError,
    PipelineJobPayloadRejectedError,
    PipelineJobStatus,
    PipelineRunStatus,
)


class WorkerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    value: str
    options: dict[str, str] = Field(default_factory=dict)


class WorkerResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str = "succeeded"
    value: str


def _registry(call_count: list[str], *, retry_failures: int = 0) -> PipelineRegistry:
    class WorkerPipeline:
        pipeline_id = "test.worker"
        pipeline_version = "v1"

        def run(
            self,
            request: WorkerRequest,
            *,
            context: PipelineContext | None = None,
        ) -> WorkerResult:
            del context
            call_count.append(request.value)
            if len(call_count) <= retry_failures:
                raise TimeoutError("provider detail must not be persisted")
            return WorkerResult(value=request.value)

        async def arun(
            self,
            request: WorkerRequest,
            *,
            context: PipelineContext | None = None,
        ) -> WorkerResult:
            return self.run(request, context=context)

    registry = PipelineRegistry()
    registry.register(
        WorkerPipeline.pipeline_id,
        WorkerPipeline.pipeline_version,
        WorkerPipeline,
        request_type=WorkerRequest,
        result_type=WorkerResult,
    )
    return registry


def test_queue_prepares_without_running_and_worker_restart_replays_once(
    tmp_path: Path,
) -> None:
    calls: list[str] = []
    registry = _registry(calls)
    executor = LocalPipelineExecutor(tmp_path / "runs", registry)
    queue = LocalPipelineJobQueue(tmp_path / "jobs", executor, retry_backoff_seconds=0)
    context = PipelineContext(
        run_id="queued-restart",
        actor_id="operator:one",
        idempotency_key="queued-restart-1",
    )

    prepared = queue.enqueue("test.worker", "v1", {"value": "once"}, context=context)
    assert prepared.status is PipelineRunStatus.PREPARED
    assert calls == []
    assert queue.load(context.run_id).status is PipelineJobStatus.QUEUED

    claim = queue.claim_next(worker_id="worker:before-crash")
    assert claim is not None
    committed = executor.execute("test.worker", "v1", claim.payload, context=claim.context)
    assert committed.status is PipelineRunStatus.SUCCEEDED
    assert calls == ["once"]

    restarted_executor = LocalPipelineExecutor(tmp_path / "runs", registry)
    restarted_queue = LocalPipelineJobQueue(
        tmp_path / "jobs",
        restarted_executor,
        retry_backoff_seconds=0,
    )
    reclaimed_at = claim.lease_expires_at
    assert reclaimed_at is not None
    reclaimed = restarted_queue.claim_next(
        worker_id="worker:after-crash",
        now=reclaimed_at + timedelta(microseconds=1),
    )
    assert reclaimed is not None
    replayed = restarted_queue.execute_claim(
        reclaimed,
        worker_id="worker:after-crash",
        now=reclaimed.updated_at,
    )
    assert replayed.status is PipelineRunStatus.SUCCEEDED
    assert replayed.replayed is True
    assert calls == ["once"]
    completed = restarted_queue.load(context.run_id)
    assert completed.status is PipelineJobStatus.COMPLETED
    assert completed.final_run_status is PipelineRunStatus.SUCCEEDED


def test_queue_retries_only_retryable_failures_with_a_bound(tmp_path: Path) -> None:
    calls: list[str] = []
    executor = LocalPipelineExecutor(tmp_path / "runs", _registry(calls, retry_failures=2))
    queue = LocalPipelineJobQueue(
        tmp_path / "jobs",
        executor,
        max_attempts=3,
        retry_backoff_seconds=0,
    )
    context = PipelineContext(run_id="queued-retry")
    queue.enqueue("test.worker", "v1", {"value": "retry"}, context=context)

    first = queue.run_once(worker_id="worker:retry")
    second = queue.run_once(worker_id="worker:retry")
    third = queue.run_once(worker_id="worker:retry")

    assert first is not None and first.status is PipelineRunStatus.RETRYABLE_FAILURE
    assert second is not None and second.status is PipelineRunStatus.RETRYABLE_FAILURE
    assert third is not None and third.status is PipelineRunStatus.SUCCEEDED
    assert third.attempt == 3
    assert calls == ["retry", "retry", "retry"]
    assert queue.load(context.run_id).status is PipelineJobStatus.COMPLETED
    assert queue.run_once(worker_id="worker:retry") is None


def test_queue_exhausts_retryable_failure_and_honors_prestart_cancel(
    tmp_path: Path,
) -> None:
    retry_calls: list[str] = []
    retry_executor = LocalPipelineExecutor(
        tmp_path / "retry-runs",
        _registry(retry_calls, retry_failures=99),
    )
    retry_queue = LocalPipelineJobQueue(
        tmp_path / "retry-jobs",
        retry_executor,
        max_attempts=2,
        retry_backoff_seconds=0,
    )
    retry_context = PipelineContext(run_id="queued-exhaust")
    retry_queue.enqueue("test.worker", "v1", {"value": "fail"}, context=retry_context)
    retry_queue.run_once(worker_id="worker:retry")
    retry_queue.run_once(worker_id="worker:retry")
    assert retry_queue.load(retry_context.run_id).status is PipelineJobStatus.EXHAUSTED
    assert retry_calls == ["fail", "fail"]

    cancel_calls: list[str] = []
    cancel_executor = LocalPipelineExecutor(tmp_path / "cancel-runs", _registry(cancel_calls))
    cancel_queue = LocalPipelineJobQueue(tmp_path / "cancel-jobs", cancel_executor)
    cancel_context = PipelineContext(run_id="queued-cancel")
    cancel_queue.enqueue("test.worker", "v1", {"value": "cancel"}, context=cancel_context)
    cancel_executor.request_cancel(cancel_context.run_id, actor_id="operator:one")
    cancelled = cancel_queue.run_once(worker_id="worker:cancel")
    assert cancelled is not None and cancelled.status is PipelineRunStatus.CANCELLED
    assert cancel_calls == []
    assert cancel_queue.load(cancel_context.run_id).status is PipelineJobStatus.COMPLETED


def test_queue_rejects_sensitive_oversized_and_tampered_payloads(tmp_path: Path) -> None:
    calls: list[str] = []
    executor = LocalPipelineExecutor(tmp_path / "runs", _registry(calls))
    queue = LocalPipelineJobQueue(tmp_path / "jobs", executor)

    with pytest.raises(PipelineJobPayloadRejectedError, match="forbidden key"):
        queue.enqueue(
            "test.worker",
            "v1",
            {"value": "unsafe", "options": {"api_key": "must-not-persist"}},
            context=PipelineContext(run_id="queued-secret"),
        )
    with pytest.raises(PipelineJobPayloadRejectedError, match="1 MiB"):
        queue.enqueue(
            "test.worker",
            "v1",
            {"value": "x" * (1024 * 1024 + 1)},
            context=PipelineContext(run_id="queued-large"),
        )

    context = PipelineContext(run_id="queued-tampered")
    queue.enqueue("test.worker", "v1", {"value": "original"}, context=context)
    path = tmp_path / "jobs" / "job-queued-tampered.json"
    content = path.read_text(encoding="utf-8").replace("original", "tampered")
    path.write_text(content, encoding="utf-8")
    with pytest.raises(PipelineJobIntegrityError, match="payload hash"):
        queue.load(context.run_id)


def test_claim_is_exclusive_until_lease_expiry(tmp_path: Path) -> None:
    calls: list[str] = []
    executor = LocalPipelineExecutor(tmp_path / "runs", _registry(calls))
    queue = LocalPipelineJobQueue(tmp_path / "jobs", executor)
    context = PipelineContext(run_id="queued-lease")
    queue.enqueue("test.worker", "v1", {"value": "leased"}, context=context)
    base = datetime.now(UTC) + timedelta(seconds=1)

    first = queue.claim_next(worker_id="worker:one", lease_seconds=10, now=base)
    assert first is not None
    assert (
        queue.claim_next(
            worker_id="worker:two",
            lease_seconds=10,
            now=base + timedelta(seconds=9),
        )
        is None
    )
    reclaimed = queue.claim_next(
        worker_id="worker:two",
        lease_seconds=10,
        now=base + timedelta(seconds=11),
    )
    assert reclaimed is not None
    assert reclaimed.worker_id == "worker:two"
    assert reclaimed.claim_id != first.claim_id


def test_claim_prefers_oldest_available_job_over_run_id_order(tmp_path: Path) -> None:
    calls: list[str] = []
    executor = LocalPipelineExecutor(tmp_path / "runs", _registry(calls))
    queue = LocalPipelineJobQueue(tmp_path / "jobs", executor)
    older_context = PipelineContext(run_id="z-older")
    newer_context = PipelineContext(run_id="a-newer")
    queue.enqueue("test.worker", "v1", {"value": "older"}, context=older_context)
    queue.enqueue("test.worker", "v1", {"value": "newer"}, context=newer_context)
    base = datetime.now(UTC) - timedelta(minutes=1)
    older = queue.load(older_context.run_id).model_copy(
        update={"queued_at": base, "updated_at": base, "available_at": base}
    )
    newer = queue.load(newer_context.run_id).model_copy(
        update={
            "queued_at": base + timedelta(seconds=1),
            "updated_at": base + timedelta(seconds=1),
            "available_at": base + timedelta(seconds=1),
        }
    )
    queue._write(tmp_path / "jobs" / "job-z-older.json", older)
    queue._write(tmp_path / "jobs" / "job-a-newer.json", newer)

    claimed = queue.claim_next(worker_id="worker:fifo", now=base + timedelta(seconds=2))

    assert claimed is not None
    assert claimed.run_id == older_context.run_id


def test_concurrent_exact_enqueue_creates_one_job_and_marks_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    executor = LocalPipelineExecutor(tmp_path / "runs", _registry(calls))
    queue = LocalPipelineJobQueue(tmp_path / "jobs", executor)
    context = PipelineContext(run_id="queued-concurrent")
    original_prepare = executor.prepare
    prepared_barrier = Barrier(2)

    def synchronized_prepare(
        pipeline_id: str,
        pipeline_version: str,
        payload: object,
        *,
        context: PipelineContext | None = None,
    ):
        result = original_prepare(
            pipeline_id,
            pipeline_version,
            payload,
            context=context,
        )
        prepared_barrier.wait(timeout=5)
        return result

    monkeypatch.setattr(executor, "prepare", synchronized_prepare)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(
                queue.enqueue,
                "test.worker",
                "v1",
                {"value": "once"},
                context=context,
            )
            for _ in range(2)
        ]
        results = [future.result(timeout=10) for future in futures]

    assert any(result.replayed for result in results)
    assert len(tuple((tmp_path / "jobs").glob("job-*.json"))) == 1
    assert queue.load(context.run_id).status is PipelineJobStatus.QUEUED
    assert calls == []
    executed = queue.run_once(worker_id="worker:concurrent")
    assert executed is not None and executed.status is PipelineRunStatus.SUCCEEDED
    assert calls == ["once"]
