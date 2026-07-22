"""Bounded local JSON batch execution with per-item checkpoints."""

from __future__ import annotations

import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from axcalib.dossier import atomic_write_text, canonical_json_bytes, exclusive_file_lock
from axcalib.pipelines.base import PipelineContext
from axcalib.runtime.execution import LocalPipelineExecutor, PipelineRunStatus

BATCH_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
MAX_BATCH_ITEMS = 10_000
MAX_BATCH_JSONL_BYTES = 10 * 1024 * 1024


class BatchItem(BaseModel):
    """One independently retryable allowlisted pipeline request."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    item_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
    pipeline_id: str
    pipeline_version: str
    payload: dict[str, Any]
    idempotency_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class BatchManifest(BaseModel):
    """Strict JSONL-compatible local batch manifest."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "axcalib.batch/v1alpha1"
    batch_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
    items: tuple[BatchItem, ...] = Field(min_length=1, max_length=MAX_BATCH_ITEMS)

    @model_validator(mode="after")
    def validate_item_ids(self) -> BatchManifest:
        ids = [item.item_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("batch item IDs must be unique")
        return self


class BatchItemResult(BaseModel):
    """Per-item status; partial failures are never hidden."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    item_id: str
    run_id: str
    status: PipelineRunStatus
    attempt: int = Field(ge=0)
    checkpoint_uri: str
    error_code: str | None = None
    replayed: bool = False


class BatchResult(BaseModel):
    """Durable aggregate of independently checkpointed batch items."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "axcalib.batch-result/v1alpha1"
    batch_id: str
    manifest_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    status: str
    started_at: datetime
    completed_at: datetime
    items: tuple[BatchItemResult, ...]
    result_uri: str


class BatchConflictError(RuntimeError):
    """Raised when a batch ID is reused with a different manifest."""


class BatchCheckpoint(BaseModel):
    """Secret-free identity checkpoint for a local batch."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "axcalib.batch-checkpoint/v1alpha1"
    batch_id: str
    manifest_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    prepared_at: datetime


class LocalBatchRunner:
    """Execute a batch with bounded concurrency and idempotent resume."""

    def __init__(self, root: Path, executor: LocalPipelineExecutor) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.executor = executor

    def run(self, manifest: BatchManifest, *, max_concurrency: int = 4) -> BatchResult:
        if not 1 <= max_concurrency <= 32:
            raise ValueError("max_concurrency must be between 1 and 32")
        checkpoint = self._prepare_manifest(manifest)
        started = datetime.now(UTC)
        results: list[BatchItemResult] = []
        with ThreadPoolExecutor(max_workers=max_concurrency) as pool:
            futures = {
                pool.submit(self._run_item, manifest.batch_id, item): item.item_id
                for item in manifest.items
            }
            for future in as_completed(futures):
                item_id = futures[future]
                try:
                    results.append(future.result())
                except Exception as error:
                    results.append(
                        BatchItemResult(
                            item_id=item_id,
                            run_id=f"batch-{manifest.batch_id}-{item_id}",
                            status=PipelineRunStatus.TERMINAL_FAILURE,
                            attempt=0,
                            checkpoint_uri=str(self._progress_path(manifest.batch_id)),
                            error_code=type(error).__name__,
                        )
                    )
                self._write_progress(manifest.batch_id, started, results)
        ordered = tuple(sorted(results, key=lambda item: item.item_id))
        status = self._aggregate_status(ordered)
        completed = datetime.now(UTC)
        path = self._result_path(manifest.batch_id)
        result = BatchResult(
            batch_id=manifest.batch_id,
            manifest_sha256=checkpoint.manifest_sha256,
            status=status,
            started_at=started,
            completed_at=completed,
            items=ordered,
            result_uri=str(path),
        )
        self._write(path, result.model_dump(mode="json"))
        return result

    def _prepare_manifest(self, manifest: BatchManifest) -> BatchCheckpoint:
        path = self._checkpoint_path(manifest.batch_id)
        digest = hashlib.sha256(
            canonical_json_bytes(manifest.model_dump(mode="json"))
        ).hexdigest()
        with exclusive_file_lock(path):
            if path.is_file():
                current = BatchCheckpoint.model_validate_json(
                    path.read_text(encoding="utf-8")
                )
                if current.manifest_sha256 != digest:
                    raise BatchConflictError(
                        "batch ID was reused with a different manifest"
                    )
                return current
            checkpoint = BatchCheckpoint(
                batch_id=manifest.batch_id,
                manifest_sha256=digest,
                prepared_at=datetime.now(UTC),
            )
            self._write(path, checkpoint.model_dump(mode="json"))
            return checkpoint

    def _run_item(self, batch_id: str, item: BatchItem) -> BatchItemResult:
        execution = self.executor.execute(
            item.pipeline_id,
            item.pipeline_version,
            item.payload,
            context=PipelineContext(
                run_id=f"batch-{batch_id}-{item.item_id}",
                idempotency_key=item.idempotency_key,
                metadata={"batch_id": batch_id, "item_id": item.item_id},
            ),
        )
        return BatchItemResult(
            item_id=item.item_id,
            run_id=execution.run_id,
            status=execution.status,
            attempt=execution.attempt,
            checkpoint_uri=execution.checkpoint_uri,
            error_code=execution.error_code,
            replayed=execution.replayed,
        )

    def _write_progress(
        self,
        batch_id: str,
        started: datetime,
        items: list[BatchItemResult],
    ) -> None:
        value = {
            "schema_version": "axcalib.batch-progress/v1alpha1",
            "batch_id": batch_id,
            "started_at": started.isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
            "items": [
                item.model_dump(mode="json")
                for item in sorted(items, key=lambda value: value.item_id)
            ],
        }
        self._write(self._progress_path(batch_id), value)

    @staticmethod
    def _aggregate_status(items: tuple[BatchItemResult, ...]) -> str:
        statuses = {item.status for item in items}
        if statuses <= {PipelineRunStatus.SUCCEEDED, PipelineRunStatus.WAITING_HUMAN}:
            return "succeeded"
        if PipelineRunStatus.RETRYABLE_FAILURE in statuses:
            return "partial_retryable_failure"
        return "partial_terminal_failure"

    def _result_path(self, batch_id: str) -> Path:
        if BATCH_ID_PATTERN.fullmatch(batch_id) is None:
            raise ValueError("invalid batch_id")
        return self.root / f"batch-{batch_id}.result.json"

    def _progress_path(self, batch_id: str) -> Path:
        if BATCH_ID_PATTERN.fullmatch(batch_id) is None:
            raise ValueError("invalid batch_id")
        return self.root / f"batch-{batch_id}.progress.json"

    def _checkpoint_path(self, batch_id: str) -> Path:
        if BATCH_ID_PATTERN.fullmatch(batch_id) is None:
            raise ValueError("invalid batch_id")
        return self.root / f"batch-{batch_id}.json"

    @staticmethod
    def _write(path: Path, value: dict[str, Any]) -> None:
        atomic_write_text(
            path,
            json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        )


def load_batch_jsonl(path: Path, *, batch_id: str | None = None) -> BatchManifest:
    """Load strict one-item-per-line JSONL without retaining source text."""

    source = path.resolve()
    if source.stat().st_size > MAX_BATCH_JSONL_BYTES:
        raise ValueError("batch JSONL exceeds the 10 MiB local safety limit")
    resolved_batch_id = batch_id or source.stem
    if BATCH_ID_PATTERN.fullmatch(resolved_batch_id) is None:
        raise ValueError("batch_id must be supplied when the filename is not a valid ID")
    items: list[BatchItem] = []
    for line_number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            items.append(BatchItem.model_validate_json(line))
        except Exception as error:
            raise ValueError(f"invalid batch JSONL item at line {line_number}") from error
        if len(items) > MAX_BATCH_ITEMS:
            raise ValueError(f"batch JSONL supports at most {MAX_BATCH_ITEMS} items")
    if not items:
        raise ValueError("batch JSONL must contain at least one item")
    return BatchManifest(batch_id=resolved_batch_id, items=tuple(items))


__all__ = [
    "BatchCheckpoint",
    "BatchConflictError",
    "BatchItem",
    "BatchItemResult",
    "BatchManifest",
    "BatchResult",
    "LocalBatchRunner",
    "load_batch_jsonl",
]
