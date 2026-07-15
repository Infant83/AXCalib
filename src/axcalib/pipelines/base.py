"""Small typed contracts for allowlisted local pipelines."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Protocol, TypeVar

InputT = TypeVar("InputT", contravariant=True)
OutputT = TypeVar("OutputT", covariant=True)


class LocalPipeline(Protocol[InputT, OutputT]):
    """Sync/async local pipeline contract shared by delivery interfaces."""

    pipeline_id: str
    pipeline_version: str

    def run(self, request: InputT) -> OutputT:
        """Run synchronously."""

        ...

    def arun(self, request: InputT) -> Awaitable[OutputT]:
        """Run asynchronously with equivalent semantics."""

        ...


PipelineFactory = Callable[[], LocalPipeline[Any, Any]]


class PipelineRegistry:
    """Allowlist pipeline IDs and versions without dynamic import paths."""

    def __init__(self) -> None:
        self._factories: dict[tuple[str, str], PipelineFactory] = {}

    def register(self, pipeline_id: str, version: str, factory: PipelineFactory) -> None:
        """Register exactly one factory for an ID/version pair."""

        key = (pipeline_id, version)
        if key in self._factories:
            raise ValueError(f"pipeline already registered: {pipeline_id}@{version}")
        if not pipeline_id or not version:
            raise ValueError("pipeline_id and version must not be empty")
        self._factories[key] = factory

    def create(self, pipeline_id: str, version: str) -> LocalPipeline[Any, Any]:
        """Instantiate an allowlisted pipeline."""

        try:
            factory = self._factories[(pipeline_id, version)]
        except KeyError as error:
            raise KeyError(f"pipeline is not allowlisted: {pipeline_id}@{version}") from error
        return factory()

    def keys(self) -> tuple[tuple[str, str], ...]:
        """Return registered pairs in deterministic order."""

        return tuple(sorted(self._factories))


__all__ = ["LocalPipeline", "PipelineRegistry"]
