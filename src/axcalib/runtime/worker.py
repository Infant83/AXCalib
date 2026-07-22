"""Durable single-host queue and worker over the local pipeline executor."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from axcalib.dossier import atomic_write_text, canonical_json_bytes, exclusive_file_lock
from axcalib.pipelines.base import PipelineContext
from axcalib.runtime.execution import (
    TERMINAL_RUN_STATUSES,
    LocalPipelineExecutor,
    PipelineExecutionResult,
    PipelineRunStatus,
)

MAX_JOB_PAYLOAD_BYTES = 1024 * 1024
SENSITIVE_PAYLOAD_KEYS = frozenset(
    {
        "access_token",
        "api_key",
        "authorization",
        "credential",
        "password",
        "refresh_token",
        "secret",
    }
)
SAFE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class PipelineJobStatus(StrEnum):
    """Durable queue lifecycle independent from the pipeline result status."""

    QUEUED = "queued"
    CLAIMED = "claimed"
    COMPLETED = "completed"
    EXHAUSTED = "exhausted"
    BLOCKED = "blocked"


FINAL_JOB_STATUSES = frozenset(
    {
        PipelineJobStatus.COMPLETED,
        PipelineJobStatus.EXHAUSTED,
        PipelineJobStatus.BLOCKED,
    }
)


class PipelineJobRecord(BaseModel):
    """Typed persisted command envelope consumed by a local worker."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "axcalib.pipeline-job/v1alpha1"
    run_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
    pipeline_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
    pipeline_version: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
    request_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    payload: dict[str, Any]
    context: PipelineContext
    status: PipelineJobStatus
    queued_at: datetime
    updated_at: datetime
    available_at: datetime
    max_attempts: int = Field(ge=1, le=20)
    claim_id: str | None = None
    worker_id: str | None = None
    lease_expires_at: datetime | None = None
    final_run_status: PipelineRunStatus | None = None
    error_code: str | None = None

    @model_validator(mode="after")
    def validate_claim_and_time(self) -> PipelineJobRecord:
        timestamps = (self.queued_at, self.updated_at, self.available_at)
        if any(value.tzinfo is None or value.utcoffset() is None for value in timestamps):
            raise ValueError("job timestamps must be timezone-aware")
        claim_fields = (self.claim_id, self.worker_id, self.lease_expires_at)
        if self.status is PipelineJobStatus.CLAIMED:
            if any(value is None for value in claim_fields):
                raise ValueError("claimed job requires claim, worker, and lease")
            assert self.lease_expires_at is not None
            if self.lease_expires_at.tzinfo is None or self.lease_expires_at.utcoffset() is None:
                raise ValueError("job lease must be timezone-aware")
        elif any(value is not None for value in claim_fields):
            raise ValueError("only a claimed job may carry claim fields")
        if self.status is PipelineJobStatus.COMPLETED and self.final_run_status is None:
            raise ValueError("completed job requires a final run status")
        return self


class PipelineJobError(RuntimeError):
    """Base queue contract error."""


class PipelineJobConflictError(PipelineJobError):
    """Raised when a run ID is reused for a different queued request."""


class PipelineJobIntegrityError(PipelineJobError):
    """Raised when a persisted job envelope fails validation or hashing."""


class PipelineJobClaimError(PipelineJobError):
    """Raised when a worker no longer owns a valid claim."""


class PipelineJobPayloadRejectedError(PipelineJobError):
    """Raised when an envelope is too large or appears to contain a secret."""


class LocalPipelineJobQueue:
    """Persist validated requests and lease them to one or more local processes."""

    def __init__(
        self,
        root: Path,
        executor: LocalPipelineExecutor,
        *,
        max_attempts: int = 3,
        retry_backoff_seconds: float = 1.0,
    ) -> None:
        if not 1 <= max_attempts <= 20:
            raise ValueError("max_attempts must be between 1 and 20")
        if not 0 <= retry_backoff_seconds <= 300:
            raise ValueError("retry_backoff_seconds must be between 0 and 300")
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.executor = executor
        self.max_attempts = max_attempts
        self.retry_backoff_seconds = retry_backoff_seconds

    def enqueue(
        self,
        pipeline_id: str,
        pipeline_version: str,
        payload: Any,
        *,
        context: PipelineContext,
    ) -> PipelineExecutionResult:
        """Persist one exact validated command and return its prepared run."""

        validated = self.executor.registry.validate_request(
            pipeline_id,
            pipeline_version,
            payload,
        )
        payload_value = self._payload_value(validated)
        self._validate_payload(payload_value)
        request_sha256 = hashlib.sha256(canonical_json_bytes(payload_value)).hexdigest()
        path = self._job_path(context.run_id)
        with exclusive_file_lock(path):
            if path.is_file():
                existing = self._load_path(path)
                self._verify_identity(
                    existing,
                    pipeline_id=pipeline_id,
                    pipeline_version=pipeline_version,
                    request_sha256=request_sha256,
                    context=context,
                )
                return self.executor.inspect(context.run_id).model_copy(update={"replayed": True})

        prepared = self.executor.prepare(
            pipeline_id,
            pipeline_version,
            validated,
            context=context,
        )
        if prepared.status is PipelineRunStatus.RUNNING:
            raise PipelineJobConflictError("run is already executing outside the local queue")
        now = datetime.now(UTC)
        status = PipelineJobStatus.QUEUED
        final_run_status = None
        if prepared.status in TERMINAL_RUN_STATUSES:
            status = PipelineJobStatus.COMPLETED
            final_run_status = prepared.status
        elif (
            prepared.status is PipelineRunStatus.RETRYABLE_FAILURE
            and prepared.attempt >= self.max_attempts
        ):
            status = PipelineJobStatus.EXHAUSTED
        candidate = PipelineJobRecord(
            run_id=context.run_id,
            pipeline_id=pipeline_id,
            pipeline_version=pipeline_version,
            request_sha256=request_sha256,
            payload=payload_value,
            context=context,
            status=status,
            queued_at=now,
            updated_at=now,
            available_at=now,
            max_attempts=self.max_attempts,
            final_run_status=final_run_status,
            error_code=prepared.error_code,
        )
        with exclusive_file_lock(path):
            if path.is_file():
                existing = self._load_path(path)
                self._verify_identity(
                    existing,
                    pipeline_id=pipeline_id,
                    pipeline_version=pipeline_version,
                    request_sha256=request_sha256,
                    context=context,
                )
                return self.executor.inspect(context.run_id).model_copy(update={"replayed": True})
            else:
                self._write(path, candidate)
        return prepared

    def claim_next(
        self,
        *,
        worker_id: str,
        lease_seconds: float = 300.0,
        now: datetime | None = None,
    ) -> PipelineJobRecord | None:
        """Claim the oldest available job or reclaim an expired claim."""

        self._validate_safe_id(worker_id, label="worker_id")
        if not 1 <= lease_seconds <= 86400:
            raise ValueError("lease_seconds must be between 1 and 86400")
        current_time = now or datetime.now(UTC)
        self._validate_aware(current_time, label="now")
        candidates: list[tuple[datetime, str, Path]] = []
        for path in sorted(self.root.glob("job-*.json")):
            with exclusive_file_lock(path):
                record = self._load_path(path)
                if self._is_available(record, current_time):
                    candidates.append((record.queued_at, record.run_id, path))
        for _, _, path in sorted(candidates):
            with exclusive_file_lock(path):
                record = self._load_path(path)
                if not self._is_available(record, current_time):
                    continue
                claimed = record.model_copy(
                    update={
                        "status": PipelineJobStatus.CLAIMED,
                        "updated_at": current_time,
                        "claim_id": f"claim-{uuid.uuid4().hex}",
                        "worker_id": worker_id,
                        "lease_expires_at": current_time + timedelta(seconds=lease_seconds),
                        "final_run_status": None,
                    }
                )
                self._write(path, claimed)
                return claimed
        return None

    def execute_claim(
        self,
        claim: PipelineJobRecord,
        *,
        worker_id: str,
        now: datetime | None = None,
    ) -> PipelineExecutionResult:
        """Execute one owned claim and durably finalize or requeue it."""

        self._validate_safe_id(worker_id, label="worker_id")
        path = self._job_path(claim.run_id)
        started_at = now or datetime.now(UTC)
        self._validate_aware(started_at, label="now")
        with exclusive_file_lock(path):
            current = self._load_path(path)
            if (
                current.status is not PipelineJobStatus.CLAIMED
                or current.claim_id != claim.claim_id
                or current.worker_id != worker_id
                or current.lease_expires_at is None
                or current.lease_expires_at <= started_at
            ):
                raise PipelineJobClaimError("worker does not own an active job claim")
        try:
            result = self.executor.execute(
                current.pipeline_id,
                current.pipeline_version,
                current.payload,
                context=current.context,
            )
        except Exception as error:
            self._block_claim(current, worker_id=worker_id, error_code=type(error).__name__)
            raise
        finished_at = datetime.now(UTC)
        with exclusive_file_lock(path):
            latest = self._load_path(path)
            if latest.claim_id != current.claim_id or latest.worker_id != worker_id:
                raise PipelineJobClaimError("job claim changed while the pipeline was executing")
            if result.status is PipelineRunStatus.RETRYABLE_FAILURE:
                if result.attempt < latest.max_attempts:
                    delay = min(
                        self.retry_backoff_seconds * (2 ** max(result.attempt - 1, 0)),
                        300.0,
                    )
                    status = PipelineJobStatus.QUEUED
                    available_at = finished_at + timedelta(seconds=delay)
                else:
                    status = PipelineJobStatus.EXHAUSTED
                    available_at = finished_at
                final_status = None
            else:
                status = PipelineJobStatus.COMPLETED
                available_at = finished_at
                final_status = result.status
            updated = latest.model_copy(
                update={
                    "status": status,
                    "updated_at": finished_at,
                    "available_at": available_at,
                    "claim_id": None,
                    "worker_id": None,
                    "lease_expires_at": None,
                    "final_run_status": final_status,
                    "error_code": result.error_code,
                }
            )
            self._write(path, updated)
        return result

    def run_once(
        self,
        *,
        worker_id: str,
        lease_seconds: float = 300.0,
    ) -> PipelineExecutionResult | None:
        """Claim and process at most one available job."""

        claim = self.claim_next(worker_id=worker_id, lease_seconds=lease_seconds)
        if claim is None:
            return None
        return self.execute_claim(claim, worker_id=worker_id)

    def load(self, run_id: str) -> PipelineJobRecord:
        """Load and hash-verify one queued command envelope."""

        path = self._job_path(run_id)
        if not path.is_file():
            raise FileNotFoundError(f"pipeline job not found: {run_id}")
        return self._load_path(path)

    def _block_claim(
        self,
        claim: PipelineJobRecord,
        *,
        worker_id: str,
        error_code: str,
    ) -> None:
        path = self._job_path(claim.run_id)
        with exclusive_file_lock(path):
            latest = self._load_path(path)
            if latest.claim_id != claim.claim_id or latest.worker_id != worker_id:
                return
            now = datetime.now(UTC)
            blocked = latest.model_copy(
                update={
                    "status": PipelineJobStatus.BLOCKED,
                    "updated_at": now,
                    "available_at": now,
                    "claim_id": None,
                    "worker_id": None,
                    "lease_expires_at": None,
                    "error_code": error_code,
                }
            )
            self._write(path, blocked)

    def _load_path(self, path: Path) -> PipelineJobRecord:
        try:
            record = PipelineJobRecord.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception as error:
            raise PipelineJobIntegrityError("pipeline job record is invalid") from error
        if path.resolve() != self._job_path(record.run_id).resolve():
            raise PipelineJobIntegrityError("pipeline job path does not match its run ID")
        actual_sha256 = hashlib.sha256(canonical_json_bytes(record.payload)).hexdigest()
        if actual_sha256 != record.request_sha256:
            raise PipelineJobIntegrityError("pipeline job payload hash does not match")
        if record.context.run_id != record.run_id:
            raise PipelineJobIntegrityError("pipeline job context run ID does not match")
        self._validate_payload(record.payload)
        return record

    def _verify_identity(
        self,
        record: PipelineJobRecord,
        *,
        pipeline_id: str,
        pipeline_version: str,
        request_sha256: str,
        context: PipelineContext,
    ) -> None:
        if (
            record.pipeline_id != pipeline_id
            or record.pipeline_version != pipeline_version
            or record.request_sha256 != request_sha256
            or self._context_identity(record.context) != self._context_identity(context)
            or record.max_attempts != self.max_attempts
        ):
            raise PipelineJobConflictError(
                "run ID was reused for a different queued pipeline or request"
            )

    def _job_path(self, run_id: str) -> Path:
        PipelineContext(run_id=run_id)
        return self.root / f"job-{run_id}.json"

    @staticmethod
    def _payload_value(value: Any) -> dict[str, Any]:
        if isinstance(value, BaseModel):
            payload = value.model_dump(mode="json")
        else:
            adapter = getattr(value, "model_dump", None)
            payload = adapter(mode="json") if callable(adapter) else value
        if not isinstance(payload, dict):
            raise PipelineJobPayloadRejectedError("queued pipeline payload must be an object")
        return payload

    @classmethod
    def _validate_payload(cls, payload: dict[str, Any]) -> None:
        content = canonical_json_bytes(payload)
        if len(content) > MAX_JOB_PAYLOAD_BYTES:
            raise PipelineJobPayloadRejectedError("queued pipeline payload exceeds 1 MiB")
        if cls._sensitive_location(payload) is not None:
            raise PipelineJobPayloadRejectedError(
                "queued pipeline payload contains a forbidden key"
            )

    @classmethod
    def _sensitive_location(cls, value: Any) -> str | None:
        if isinstance(value, dict):
            for key, nested in value.items():
                if str(key).casefold() in SENSITIVE_PAYLOAD_KEYS:
                    return str(key)
                found = cls._sensitive_location(nested)
                if found is not None:
                    return found
        elif isinstance(value, list):
            for nested in value:
                found = cls._sensitive_location(nested)
                if found is not None:
                    return found
        return None

    @staticmethod
    def _context_identity(context: PipelineContext) -> tuple[Any, ...]:
        return (
            context.actor_id,
            context.actor_role,
            context.idempotency_key,
            context.expected_revision,
            tuple(sorted(context.metadata.items())),
        )

    @staticmethod
    def _validate_safe_id(value: str, *, label: str) -> None:
        if SAFE_ID_PATTERN.fullmatch(value) is None:
            raise ValueError(f"{label} must be a safe identifier")

    @staticmethod
    def _validate_aware(value: datetime, *, label: str) -> None:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"{label} must be timezone-aware")

    @staticmethod
    def _is_available(record: PipelineJobRecord, current_time: datetime) -> bool:
        if record.status in FINAL_JOB_STATUSES:
            return False
        if record.status is PipelineJobStatus.QUEUED:
            return record.available_at <= current_time
        if record.status is PipelineJobStatus.CLAIMED:
            assert record.lease_expires_at is not None
            return record.lease_expires_at <= current_time
        return False

    @staticmethod
    def _write(path: Path, record: PipelineJobRecord) -> None:
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


class LocalPipelineWorker:
    """Small worker facade that processes at most one job per explicit call."""

    def __init__(
        self,
        queue: LocalPipelineJobQueue,
        *,
        worker_id: str,
        lease_seconds: float = 300.0,
    ) -> None:
        LocalPipelineJobQueue._validate_safe_id(worker_id, label="worker_id")
        self.queue = queue
        self.worker_id = worker_id
        self.lease_seconds = lease_seconds

    def run_once(self) -> PipelineExecutionResult | None:
        """Run at most one queued command without an implicit daemon loop."""

        return self.queue.run_once(
            worker_id=self.worker_id,
            lease_seconds=self.lease_seconds,
        )


__all__ = [
    "LocalPipelineJobQueue",
    "LocalPipelineWorker",
    "PipelineJobClaimError",
    "PipelineJobConflictError",
    "PipelineJobError",
    "PipelineJobIntegrityError",
    "PipelineJobPayloadRejectedError",
    "PipelineJobRecord",
    "PipelineJobStatus",
]
