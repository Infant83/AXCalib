"""Filesystem idempotency records for resumable local pipelines."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from axcalib.dossier import atomic_write_text, canonical_json_bytes, exclusive_file_lock

ResultT = TypeVar("ResultT", bound=BaseModel)
KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class IdempotencyError(RuntimeError):
    """Base idempotency contract error."""


class IdempotencyConflictError(IdempotencyError):
    """Raised when a key is reused for a different request."""


class LocalIdempotencyStore:
    """Cache successful typed pipeline results by key and request hash."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def execute(
        self,
        *,
        key: str,
        operation: str,
        request: BaseModel,
        result_type: type[ResultT],
        call: Callable[[], ResultT],
    ) -> ResultT:
        """Run once or return the previously validated result."""

        if KEY_PATTERN.fullmatch(key) is None:
            raise IdempotencyError("invalid idempotency key")
        path = self._path(key)
        request_sha256 = hashlib.sha256(
            canonical_json_bytes(request.model_dump(mode="json"))
        ).hexdigest()
        with exclusive_file_lock(path, timeout_seconds=300.0):
            existing = self._load(path)
            if existing:
                if (
                    existing.get("operation") != operation
                    or existing.get("request_sha256") != request_sha256
                ):
                    raise IdempotencyConflictError(
                        "idempotency key was already used for a different request"
                    )
                if existing.get("status") == "succeeded":
                    return result_type.model_validate(existing["result"])
            started: dict[str, object] = {
                "schema_version": "axcalib.idempotency/v1alpha1",
                "key": key,
                "operation": operation,
                "request_sha256": request_sha256,
                "status": "running",
                "updated_at": datetime.now(UTC).isoformat(),
            }
            self._write(path, started)
            try:
                result = call()
            except Exception as error:
                self._write(
                    path,
                    {
                        **started,
                        "status": "retryable_failure",
                        # Keep only the error class; messages may contain source data or secrets.
                        "last_error": type(error).__name__,
                        "updated_at": datetime.now(UTC).isoformat(),
                    },
                )
                raise
            self._write(
                path,
                {
                    **started,
                    "status": "succeeded",
                    "result": result.model_dump(mode="json"),
                    "updated_at": datetime.now(UTC).isoformat(),
                },
            )
            return result

    def _path(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self.root / f"idempotency-{digest[:24]}.json"

    @staticmethod
    def _load(path: Path) -> dict[str, object] | None:
        if not path.exists():
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise IdempotencyError(f"invalid idempotency record: {path}")
        return value

    @staticmethod
    def _write(path: Path, value: dict[str, object]) -> None:
        atomic_write_text(
            path,
            json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        )


__all__ = [
    "IdempotencyConflictError",
    "IdempotencyError",
    "LocalIdempotencyStore",
]
