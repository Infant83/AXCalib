"""Typed contracts for allowlisted local pipelines."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

InputT = TypeVar("InputT", contravariant=True)
OutputT = TypeVar("OutputT", covariant=True)


class PipelineContext(BaseModel):
    """Transport-neutral execution context shared by CLI, API, and workers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
    actor_id: str = Field(default="system:local", min_length=1, max_length=300)
    actor_role: str = Field(default="system", min_length=1, max_length=100)
    idempotency_key: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
    )
    expected_revision: int | None = Field(default=None, ge=1)
    requested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    deadline_at: datetime | None = None
    cancel_requested: bool = False
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_deadline(self) -> PipelineContext:
        if self.requested_at.tzinfo is None or self.requested_at.utcoffset() is None:
            raise ValueError("requested_at must be timezone-aware")
        if self.deadline_at is not None and (
            self.deadline_at.tzinfo is None or self.deadline_at.utcoffset() is None
        ):
            raise ValueError("deadline_at must be timezone-aware")
        if self.deadline_at is not None and self.deadline_at <= self.requested_at:
            raise ValueError("deadline_at must be later than requested_at")
        if len(self.metadata) > 32:
            raise ValueError("metadata supports at most 32 entries")
        for key, value in self.metadata.items():
            if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", key) is None:
                raise ValueError("metadata keys must be safe identifiers")
            if len(value) > 500:
                raise ValueError("metadata values must not exceed 500 characters")
        return self

    def cancellation_requested(self) -> bool:
        """Return true for explicit cancellation or an expired deadline."""

        return self.cancel_requested or (
            self.deadline_at is not None and datetime.now(UTC) >= self.deadline_at
        )


class PipelineDescriptor(BaseModel):
    """Small serializable catalog entry for delivery adapters."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pipeline_id: str
    pipeline_version: str
    request_type: str
    result_type: str


class LocalPipeline(Protocol[InputT, OutputT]):
    """Sync/async local pipeline contract shared by delivery interfaces."""

    pipeline_id: str
    pipeline_version: str

    def run(
        self,
        request: InputT,
        *,
        context: PipelineContext | None = None,
    ) -> OutputT:
        """Run synchronously."""

        ...

    def arun(
        self,
        request: InputT,
        *,
        context: PipelineContext | None = None,
    ) -> Awaitable[OutputT]:
        """Run asynchronously with equivalent semantics."""

        ...


PipelineFactory = Callable[[], LocalPipeline[Any, Any]]


class _PipelineBinding:
    def __init__(
        self,
        factory: PipelineFactory,
        request_type: Any,
        result_type: Any,
    ) -> None:
        self.factory = factory
        self.request_type = request_type
        self.result_type = result_type
        self.request_adapter = TypeAdapter(request_type)
        self.result_adapter = TypeAdapter(result_type)


class PipelineRegistry:
    """Allowlist pipeline IDs and versions without dynamic import paths."""

    def __init__(self) -> None:
        self._bindings: dict[tuple[str, str], _PipelineBinding] = {}

    def register(
        self,
        pipeline_id: str,
        version: str,
        factory: PipelineFactory,
        *,
        request_type: Any = BaseModel,
        result_type: Any = BaseModel,
    ) -> None:
        """Register exactly one factory for an ID/version pair."""

        key = (pipeline_id, version)
        if key in self._bindings:
            raise ValueError(f"pipeline already registered: {pipeline_id}@{version}")
        if not pipeline_id or not version:
            raise ValueError("pipeline_id and version must not be empty")
        self._bindings[key] = _PipelineBinding(factory, request_type, result_type)

    def create(self, pipeline_id: str, version: str) -> LocalPipeline[Any, Any]:
        """Instantiate an allowlisted pipeline."""

        try:
            factory = self._bindings[(pipeline_id, version)].factory
        except KeyError as error:
            raise KeyError(f"pipeline is not allowlisted: {pipeline_id}@{version}") from error
        return factory()

    def validate_request(
        self,
        pipeline_id: str,
        version: str,
        value: Any,
    ) -> Any:
        """Validate JSON-compatible input against the registered request type."""

        return self._binding(pipeline_id, version).request_adapter.validate_python(value)

    def validate_result(
        self,
        pipeline_id: str,
        version: str,
        value: Any,
    ) -> Any:
        """Validate one pipeline result before a delivery adapter returns it."""

        return self._binding(pipeline_id, version).result_adapter.validate_python(value)

    def descriptors(self) -> tuple[PipelineDescriptor, ...]:
        """Return the deterministic allowlisted pipeline catalog."""

        return tuple(
            PipelineDescriptor(
                pipeline_id=pipeline_id,
                pipeline_version=version,
                request_type=self._type_name(binding.request_type),
                result_type=self._type_name(binding.result_type),
            )
            for (pipeline_id, version), binding in sorted(self._bindings.items())
        )

    def keys(self) -> tuple[tuple[str, str], ...]:
        """Return registered pairs in deterministic order."""

        return tuple(sorted(self._bindings))

    def _binding(self, pipeline_id: str, version: str) -> _PipelineBinding:
        try:
            return self._bindings[(pipeline_id, version)]
        except KeyError as error:
            raise KeyError(
                f"pipeline is not allowlisted: {pipeline_id}@{version}"
            ) from error

    @staticmethod
    def _type_name(value: Any) -> str:
        return getattr(value, "__name__", str(value).replace("typing.", ""))


__all__ = [
    "LocalPipeline",
    "PipelineContext",
    "PipelineDescriptor",
    "PipelineRegistry",
]
