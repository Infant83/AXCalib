"""Durable local pipeline execution, checkpoint, resume, and cancellation."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from axcalib.dossier import atomic_write_text, canonical_json_bytes, exclusive_file_lock
from axcalib.pipelines.base import PipelineContext, PipelineRegistry
from axcalib.schemas import PipelineStatus


class PipelineRunStatus(StrEnum):
    """Persisted lifecycle of one local pipeline execution."""

    PREPARED = "prepared"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    WAITING_HUMAN = "waiting_human"
    BLOCKED = "blocked"
    STALE = "stale"
    RETRYABLE_FAILURE = "retryable_failure"
    TERMINAL_FAILURE = "terminal_failure"
    CANCELLED = "cancelled"


TERMINAL_RUN_STATUSES = frozenset(
    {
        PipelineRunStatus.SUCCEEDED,
        PipelineRunStatus.WAITING_HUMAN,
        PipelineRunStatus.BLOCKED,
        PipelineRunStatus.STALE,
        PipelineRunStatus.TERMINAL_FAILURE,
        PipelineRunStatus.CANCELLED,
    }
)


class PipelineRunRecord(BaseModel):
    """Secret-free checkpoint describing one pipeline execution."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "axcalib.pipeline-run/v1alpha1"
    context: PipelineContext
    pipeline_id: str
    pipeline_version: str
    request_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    status: PipelineRunStatus
    prepared_at: datetime
    updated_at: datetime
    attempt: int = Field(ge=0)
    result_uri: str | None = None
    result_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    error_code: str | None = None

    @model_validator(mode="after")
    def validate_result_reference(self) -> PipelineRunRecord:
        if (self.result_uri is None) != (self.result_sha256 is None):
            raise ValueError("result_uri and result_sha256 must be present together")
        return self


class PipelineExecutionResult(BaseModel):
    """Transport-neutral execution envelope returned by CLI/API/worker adapters."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    pipeline_id: str
    pipeline_version: str
    status: PipelineRunStatus
    attempt: int = Field(ge=0)
    checkpoint_uri: str
    output: dict[str, Any] | None = None
    error_code: str | None = None
    replayed: bool = False


class PipelineRunConflictError(RuntimeError):
    """Raised when one run ID is reused for different input or pipeline identity."""


class PipelineRunIntegrityError(RuntimeError):
    """Raised when a persisted run result no longer matches its checkpoint."""


class LocalPipelineExecutor:
    """Execute allowlisted typed pipelines with durable local checkpoints."""

    def __init__(self, root: Path, registry: PipelineRegistry) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.registry = registry

    def execute(
        self,
        pipeline_id: str,
        pipeline_version: str,
        payload: Any,
        *,
        context: PipelineContext | None = None,
    ) -> PipelineExecutionResult:
        """Validate, checkpoint, run, and persist one local pipeline result."""

        request_value = self._json_value(payload)
        request_sha256 = hashlib.sha256(canonical_json_bytes(request_value)).hexdigest()
        execution_context = context or PipelineContext(run_id=f"run-{uuid.uuid4()}")
        with exclusive_file_lock(self._lease_path(execution_context.run_id)):
            return self._execute_locked(
                pipeline_id,
                pipeline_version,
                payload,
                request_sha256,
                execution_context,
            )

    def prepare(
        self,
        pipeline_id: str,
        pipeline_version: str,
        payload: Any,
        *,
        context: PipelineContext | None = None,
    ) -> PipelineExecutionResult:
        """Validate and checkpoint a run without invoking its pipeline."""

        validated = self.registry.validate_request(pipeline_id, pipeline_version, payload)
        request_value = self._json_value(validated)
        request_sha256 = hashlib.sha256(canonical_json_bytes(request_value)).hexdigest()
        execution_context = context or PipelineContext(run_id=f"run-{uuid.uuid4()}")
        with exclusive_file_lock(self._lease_path(execution_context.run_id)):
            existed = self._record_path(execution_context.run_id).is_file()
            record = self._prepare(
                pipeline_id,
                pipeline_version,
                request_sha256,
                execution_context,
            )
            return self._result_from_record(record, replayed=existed)

    def _execute_locked(
        self,
        pipeline_id: str,
        pipeline_version: str,
        payload: Any,
        request_sha256: str,
        execution_context: PipelineContext,
    ) -> PipelineExecutionResult:
        record = self._prepare(
            pipeline_id,
            pipeline_version,
            request_sha256,
            execution_context,
        )
        if record.status in TERMINAL_RUN_STATUSES:
            return self._result_from_record(record, replayed=True)
        if self._cancelled(execution_context.run_id, execution_context):
            record = self._update(record, PipelineRunStatus.CANCELLED)
            return self._result_from_record(record)
        record = self._update(
            record,
            PipelineRunStatus.RUNNING,
            attempt=record.attempt + 1,
        )
        try:
            request = self.registry.validate_request(
                pipeline_id,
                pipeline_version,
                payload,
            )
            pipeline = self.registry.create(pipeline_id, pipeline_version)
            output = pipeline.run(request, context=execution_context)
            validated = self.registry.validate_result(
                pipeline_id,
                pipeline_version,
                output,
            )
            output_value = self._json_value(validated)
            status = self._output_status(output_value)
            if self._cancelled(execution_context.run_id, execution_context):
                status = PipelineRunStatus.CANCELLED
                output_value = None
            record = self._store_result(record, status, output_value)
        except Exception as error:
            status = self._failure_status(error)
            record = self._update(
                record,
                status,
                error_code=type(error).__name__,
            )
        return self._result_from_record(record)

    async def aexecute(
        self,
        pipeline_id: str,
        pipeline_version: str,
        payload: Any,
        *,
        context: PipelineContext | None = None,
    ) -> PipelineExecutionResult:
        """Async equivalent using the pipeline's async entrypoint."""

        request_value = self._json_value(payload)
        request_sha256 = hashlib.sha256(canonical_json_bytes(request_value)).hexdigest()
        execution_context = context or PipelineContext(run_id=f"run-{uuid.uuid4()}")
        with exclusive_file_lock(self._lease_path(execution_context.run_id)):
            return await self._aexecute_locked(
                pipeline_id,
                pipeline_version,
                payload,
                request_sha256,
                execution_context,
            )

    async def _aexecute_locked(
        self,
        pipeline_id: str,
        pipeline_version: str,
        payload: Any,
        request_sha256: str,
        execution_context: PipelineContext,
    ) -> PipelineExecutionResult:
        record = self._prepare(
            pipeline_id,
            pipeline_version,
            request_sha256,
            execution_context,
        )
        if record.status in TERMINAL_RUN_STATUSES:
            return self._result_from_record(record, replayed=True)
        if self._cancelled(execution_context.run_id, execution_context):
            record = self._update(record, PipelineRunStatus.CANCELLED)
            return self._result_from_record(record)
        record = self._update(
            record,
            PipelineRunStatus.RUNNING,
            attempt=record.attempt + 1,
        )
        try:
            request = self.registry.validate_request(
                pipeline_id,
                pipeline_version,
                payload,
            )
            pipeline = self.registry.create(pipeline_id, pipeline_version)
            output = await pipeline.arun(request, context=execution_context)
            validated = self.registry.validate_result(
                pipeline_id,
                pipeline_version,
                output,
            )
            output_value = self._json_value(validated)
            status = self._output_status(output_value)
            if self._cancelled(execution_context.run_id, execution_context):
                status = PipelineRunStatus.CANCELLED
                output_value = None
            record = self._store_result(record, status, output_value)
        except Exception as error:
            record = self._update(
                record,
                self._failure_status(error),
                error_code=type(error).__name__,
            )
        return self._result_from_record(record)

    def request_cancel(self, run_id: str, *, actor_id: str) -> Path:
        """Persist a cooperative cancellation request without killing a process."""

        validated = PipelineContext(run_id=run_id, actor_id=actor_id)
        path = self._cancel_path(run_id)
        value = {
            "schema_version": "axcalib.pipeline-cancel/v1alpha1",
            "run_id": run_id,
            "actor_id": validated.actor_id,
            "requested_at": datetime.now(UTC).isoformat(),
        }
        with exclusive_file_lock(path):
            if path.is_file():
                return path
            atomic_write_text(path, json.dumps(value, sort_keys=True, indent=2) + "\n")
        return path

    def load(self, run_id: str) -> PipelineRunRecord:
        """Load one checkpoint for inspection or resume."""

        path = self._record_path(run_id)
        if not path.is_file():
            raise FileNotFoundError(f"pipeline run not found: {run_id}")
        return PipelineRunRecord.model_validate_json(path.read_text(encoding="utf-8"))

    def inspect(self, run_id: str) -> PipelineExecutionResult:
        """Return a hash-verified execution envelope without running the pipeline."""

        return self._result_from_record(self.load(run_id))

    def _prepare(
        self,
        pipeline_id: str,
        pipeline_version: str,
        request_sha256: str,
        context: PipelineContext,
    ) -> PipelineRunRecord:
        path = self._record_path(context.run_id)
        with exclusive_file_lock(path):
            if path.exists():
                current = PipelineRunRecord.model_validate_json(path.read_text(encoding="utf-8"))
                if (
                    current.pipeline_id != pipeline_id
                    or current.pipeline_version != pipeline_version
                    or current.request_sha256 != request_sha256
                    or self._context_identity(current.context) != self._context_identity(context)
                ):
                    raise PipelineRunConflictError(
                        "run ID was reused for a different pipeline or request"
                    )
                return current
            now = datetime.now(UTC)
            record = PipelineRunRecord(
                context=context,
                pipeline_id=pipeline_id,
                pipeline_version=pipeline_version,
                request_sha256=request_sha256,
                status=PipelineRunStatus.PREPARED,
                prepared_at=now,
                updated_at=now,
                attempt=0,
            )
            self._write_record(path, record)
            return record

    def _update(
        self,
        record: PipelineRunRecord,
        status: PipelineRunStatus,
        *,
        attempt: int | None = None,
        result_uri: str | None = None,
        result_sha256: str | None = None,
        error_code: str | None = None,
    ) -> PipelineRunRecord:
        updated = record.model_copy(
            update={
                "status": status,
                "updated_at": datetime.now(UTC),
                "attempt": record.attempt if attempt is None else attempt,
                "result_uri": result_uri,
                "result_sha256": result_sha256,
                "error_code": error_code,
            }
        )
        self._write_record(self._record_path(record.context.run_id), updated)
        return updated

    def _store_result(
        self,
        record: PipelineRunRecord,
        status: PipelineRunStatus,
        output: dict[str, Any] | None,
    ) -> PipelineRunRecord:
        if output is None:
            return self._update(record, status)
        content = json.dumps(output, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        path = self._result_path(record.context.run_id)
        atomic_write_text(path, content)
        return self._update(
            record,
            status,
            result_uri=str(path),
            result_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        )

    def _result_from_record(
        self,
        record: PipelineRunRecord,
        *,
        replayed: bool = False,
    ) -> PipelineExecutionResult:
        output: dict[str, Any] | None = None
        if record.result_uri:
            path = Path(record.result_uri).resolve()
            expected_path = self._result_path(record.context.run_id).resolve()
            if path != expected_path or not path.is_file():
                raise PipelineRunIntegrityError("pipeline result reference is invalid")
            content = path.read_bytes()
            digest = hashlib.sha256(content).hexdigest()
            if digest != record.result_sha256:
                raise PipelineRunIntegrityError("pipeline result hash does not match checkpoint")
            value = json.loads(content)
            if isinstance(value, dict):
                output = value
        return PipelineExecutionResult(
            run_id=record.context.run_id,
            pipeline_id=record.pipeline_id,
            pipeline_version=record.pipeline_version,
            status=record.status,
            attempt=record.attempt,
            checkpoint_uri=str(self._record_path(record.context.run_id)),
            output=output,
            error_code=record.error_code,
            replayed=replayed,
        )

    def _record_path(self, run_id: str) -> Path:
        self._validate_run_id(run_id)
        return self.root / f"run-{run_id}.json"

    def _result_path(self, run_id: str) -> Path:
        self._validate_run_id(run_id)
        return self.root / f"run-{run_id}.result.json"

    def _cancel_path(self, run_id: str) -> Path:
        self._validate_run_id(run_id)
        return self.root / f"run-{run_id}.cancel.json"

    def _lease_path(self, run_id: str) -> Path:
        self._validate_run_id(run_id)
        return self.root / f"lease-{run_id}"

    @staticmethod
    def _validate_run_id(run_id: str) -> None:
        PipelineContext(run_id=run_id)

    def _cancelled(self, run_id: str, context: PipelineContext) -> bool:
        return context.cancellation_requested() or self._cancel_path(run_id).is_file()

    @staticmethod
    def _json_value(value: Any) -> Any:
        if isinstance(value, BaseModel):
            return value.model_dump(mode="json")
        adapter = getattr(value, "model_dump", None)
        if callable(adapter):
            return adapter(mode="json")
        return value

    @staticmethod
    def _output_status(value: dict[str, Any]) -> PipelineRunStatus:
        raw = value.get("status", PipelineStatus.SUCCEEDED.value)
        try:
            return PipelineRunStatus(str(raw))
        except ValueError as error:
            raise ValueError("pipeline returned an unsupported status") from error

    @staticmethod
    def _context_identity(context: PipelineContext) -> tuple[Any, ...]:
        """Return replay-relevant identity without time or cancellation state."""

        return (
            context.actor_id,
            context.actor_role,
            context.idempotency_key,
            context.expected_revision,
            tuple(sorted(context.metadata.items())),
        )

    @staticmethod
    def _failure_status(error: Exception) -> PipelineRunStatus:
        if isinstance(error, (TimeoutError, ConnectionError)):
            return PipelineRunStatus.RETRYABLE_FAILURE
        return PipelineRunStatus.TERMINAL_FAILURE

    @staticmethod
    def _write_record(path: Path, record: PipelineRunRecord) -> None:
        content = (
            json.dumps(
                record.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
            + "\n"
        )
        atomic_write_text(path, content)


__all__ = [
    "LocalPipelineExecutor",
    "PipelineExecutionResult",
    "PipelineRunConflictError",
    "PipelineRunIntegrityError",
    "PipelineRunRecord",
    "PipelineRunStatus",
]
