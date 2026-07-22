from __future__ import annotations

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict

from axcalib.pipelines import PipelineContext, PipelineRegistry
from axcalib.runtime import (
    BatchConflictError,
    BatchItem,
    BatchManifest,
    LocalBatchRunner,
    LocalPipelineExecutor,
    PipelineRunConflictError,
    PipelineRunIntegrityError,
    PipelineRunStatus,
    load_batch_jsonl,
)


class EchoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    value: str
    fail: str | None = None


class EchoResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    status: str = "succeeded"
    value: str


class EchoPipeline:
    pipeline_id = "test.echo"
    pipeline_version = "v1"

    def run(
        self,
        request: EchoRequest,
        *,
        context: PipelineContext | None = None,
    ) -> EchoResult:
        if request.fail == "retryable":
            raise TimeoutError("provider detail must not be persisted")
        if request.fail == "terminal":
            raise ValueError("source detail must not be persisted")
        return EchoResult(value=request.value)

    async def arun(
        self,
        request: EchoRequest,
        *,
        context: PipelineContext | None = None,
    ) -> EchoResult:
        return self.run(request, context=context)


def registry() -> PipelineRegistry:
    value = PipelineRegistry()
    value.register(
        EchoPipeline.pipeline_id,
        EchoPipeline.pipeline_version,
        EchoPipeline,
        request_type=EchoRequest,
        result_type=EchoResult,
    )
    return value


def test_executor_checkpoints_and_replays_identical_run(tmp_path: Path) -> None:
    executor = LocalPipelineExecutor(tmp_path / "runs", registry())
    context = PipelineContext(run_id="run-echo", idempotency_key="echo-1")

    first = executor.execute("test.echo", "v1", {"value": "hello"}, context=context)
    second = executor.execute("test.echo", "v1", {"value": "hello"}, context=context)

    assert first.status is PipelineRunStatus.SUCCEEDED
    assert first.output == {"status": "succeeded", "value": "hello"}
    assert first.attempt == 1
    assert second.replayed is True
    assert second.attempt == 1
    assert Path(first.checkpoint_uri).is_file()
    assert "hello" not in Path(first.checkpoint_uri).read_text(encoding="utf-8")


def test_executor_rejects_tampered_result_on_replay(tmp_path: Path) -> None:
    executor = LocalPipelineExecutor(tmp_path / "runs", registry())
    context = PipelineContext(run_id="run-tampered")
    first = executor.execute("test.echo", "v1", {"value": "original"}, context=context)
    assert first.output == {"status": "succeeded", "value": "original"}
    result_path = tmp_path / "runs" / "run-run-tampered.result.json"
    result_path.write_text('{"status":"succeeded","value":"tampered"}\n', encoding="utf-8")

    with pytest.raises(PipelineRunIntegrityError):
        executor.execute("test.echo", "v1", {"value": "original"}, context=context)


def test_executor_rejects_run_id_reuse_with_different_request(tmp_path: Path) -> None:
    executor = LocalPipelineExecutor(tmp_path / "runs", registry())
    context = PipelineContext(run_id="run-conflict")
    executor.execute("test.echo", "v1", {"value": "first"}, context=context)

    with pytest.raises(PipelineRunConflictError):
        executor.execute("test.echo", "v1", {"value": "second"}, context=context)


def test_executor_cancel_and_failure_classification_are_secret_free(tmp_path: Path) -> None:
    executor = LocalPipelineExecutor(tmp_path / "runs", registry())
    executor.request_cancel("run-cancelled", actor_id="operator:one")
    cancelled = executor.execute(
        "test.echo",
        "v1",
        {"value": "never"},
        context=PipelineContext(run_id="run-cancelled"),
    )
    retryable = executor.execute(
        "test.echo",
        "v1",
        {"value": "x", "fail": "retryable"},
        context=PipelineContext(run_id="run-retryable"),
    )
    terminal = executor.execute(
        "test.echo",
        "v1",
        {"value": "x", "fail": "terminal"},
        context=PipelineContext(run_id="run-terminal"),
    )
    replayed_terminal = executor.execute(
        "test.echo",
        "v1",
        {"value": "x", "fail": "terminal"},
        context=PipelineContext(run_id="run-terminal"),
    )

    assert cancelled.status is PipelineRunStatus.CANCELLED
    assert retryable.status is PipelineRunStatus.RETRYABLE_FAILURE
    assert retryable.error_code == "TimeoutError"
    assert terminal.status is PipelineRunStatus.TERMINAL_FAILURE
    assert replayed_terminal.replayed is True
    assert replayed_terminal.attempt == 1
    checkpoint = Path(terminal.checkpoint_uri).read_text(encoding="utf-8")
    assert "source detail" not in checkpoint


def test_executor_async_semantics_match_sync(tmp_path: Path) -> None:
    executor = LocalPipelineExecutor(tmp_path / "runs", registry())
    result = asyncio.run(
        executor.aexecute(
            "test.echo",
            "v1",
            {"value": "async"},
            context=PipelineContext(run_id="run-async"),
        )
    )
    assert result.status is PipelineRunStatus.SUCCEEDED
    assert result.output == {"status": "succeeded", "value": "async"}


def test_batch_keeps_partial_failure_and_replays_completed_items(tmp_path: Path) -> None:
    executor = LocalPipelineExecutor(tmp_path / "runs", registry())
    runner = LocalBatchRunner(tmp_path / "batches", executor)
    manifest = BatchManifest(
        batch_id="batch-one",
        items=(
            BatchItem(
                item_id="ok",
                pipeline_id="test.echo",
                pipeline_version="v1",
                payload={"value": "ok"},
                idempotency_key="item-ok",
            ),
            BatchItem(
                item_id="bad",
                pipeline_id="test.echo",
                pipeline_version="v1",
                payload={"value": "bad", "fail": "terminal"},
                idempotency_key="item-bad",
            ),
        ),
    )

    first = runner.run(manifest, max_concurrency=2)
    second = runner.run(manifest, max_concurrency=2)

    assert first.status == "partial_terminal_failure"
    assert len(first.manifest_sha256) == 64
    statuses = {item.item_id: item.status for item in first.items}
    assert statuses == {
        "bad": PipelineRunStatus.TERMINAL_FAILURE,
        "ok": PipelineRunStatus.SUCCEEDED,
    }
    replayed = {item.item_id: item.replayed for item in second.items}
    assert replayed == {"bad": True, "ok": True}


def test_batch_rejects_manifest_change_and_loads_strict_jsonl(tmp_path: Path) -> None:
    source = tmp_path / "batch-jsonl.jsonl"
    source.write_text(
        '{"item_id":"one","pipeline_id":"test.echo","pipeline_version":"v1",'
        '"payload":{"value":"one"},"idempotency_key":"key-one"}\n',
        encoding="utf-8",
    )
    manifest = load_batch_jsonl(source)
    executor = LocalPipelineExecutor(tmp_path / "runs", registry())
    runner = LocalBatchRunner(tmp_path / "batches", executor)
    runner.run(manifest, max_concurrency=1)

    changed = manifest.model_copy(
        update={
            "items": (
                manifest.items[0].model_copy(update={"payload": {"value": "changed"}}),
            )
        }
    )
    with pytest.raises(BatchConflictError):
        runner.run(changed, max_concurrency=1)


def test_executor_checkpoints_invalid_typed_input(tmp_path: Path) -> None:
    executor = LocalPipelineExecutor(tmp_path / "runs", registry())

    result = executor.execute(
        "test.echo",
        "v1",
        {"unexpected": "field"},
        context=PipelineContext(run_id="run-invalid-input"),
    )

    assert result.status is PipelineRunStatus.TERMINAL_FAILURE
    assert result.error_code == "ValidationError"
    assert Path(result.checkpoint_uri).is_file()


def test_executor_rejects_context_identity_change_on_replay(tmp_path: Path) -> None:
    executor = LocalPipelineExecutor(tmp_path / "runs", registry())
    executor.execute(
        "test.echo",
        "v1",
        {"value": "first"},
        context=PipelineContext(run_id="run-context", actor_id="learner:one"),
    )

    with pytest.raises(PipelineRunConflictError):
        executor.execute(
            "test.echo",
            "v1",
            {"value": "first"},
            context=PipelineContext(run_id="run-context", actor_id="administrator:one"),
        )


def test_executor_serializes_concurrent_replay_for_same_run_id(tmp_path: Path) -> None:
    calls: list[str] = []

    class SlowPipeline(EchoPipeline):
        pipeline_id = "test.slow"

        def run(
            self,
            request: EchoRequest,
            *,
            context: PipelineContext | None = None,
        ) -> EchoResult:
            calls.append(request.value)
            time.sleep(0.1)
            return EchoResult(value=request.value)

    slow_registry = PipelineRegistry()
    slow_registry.register(
        SlowPipeline.pipeline_id,
        SlowPipeline.pipeline_version,
        SlowPipeline,
        request_type=EchoRequest,
        result_type=EchoResult,
    )
    executor = LocalPipelineExecutor(tmp_path / "runs", slow_registry)
    context = PipelineContext(run_id="run-concurrent")

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(
            pool.map(
                lambda _: executor.execute(
                    "test.slow",
                    "v1",
                    {"value": "once"},
                    context=context,
                ),
                range(2),
            )
        )

    assert calls == ["once"]
    assert sorted(item.replayed for item in results) == [False, True]


def test_pipeline_context_rejects_naive_time_and_oversized_metadata() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        PipelineContext(run_id="naive", requested_at=datetime.now())
    with pytest.raises(ValueError, match="at most 32"):
        PipelineContext(
            run_id="metadata",
            metadata={f"key-{index}": "value" for index in range(33)},
        )
    with pytest.raises(ValueError, match="later"):
        aware = datetime.now().astimezone()
        PipelineContext(
            run_id="deadline",
            requested_at=aware,
            deadline_at=aware - timedelta(seconds=1),
        )
