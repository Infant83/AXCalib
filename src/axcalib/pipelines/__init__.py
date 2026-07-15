"""Composable local pipeline contracts and implementations."""

from axcalib.pipelines.base import LocalPipeline, PipelineRegistry
from axcalib.pipelines.project import (
    LocalProjectService,
    TwoGatePptxPipeline,
    TwoGatePptxRequest,
)

__all__ = [
    "LocalPipeline",
    "LocalProjectService",
    "PipelineRegistry",
    "TwoGatePptxPipeline",
    "TwoGatePptxRequest",
]
