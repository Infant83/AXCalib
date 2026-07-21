"""Composable local pipeline contracts and implementations."""

from axcalib.pipelines.base import LocalPipeline, PipelineRegistry
from axcalib.pipelines.dossier import (
    DossierFreezePipeline,
    DossierFreezeRequest,
    DossierInitializePipeline,
    DossierInitializeRequest,
    DossierUpdatePipeline,
    DossierUpdateRequest,
)
from axcalib.pipelines.education import (
    BindProjectCommand,
    DecideProgramCompletionCommand,
    EducationCommand,
    EducationProgramPipeline,
    EnrollCommand,
    ManualConfirmationCommand,
    RecordScoreCommand,
    StartMilestoneCommand,
    SyncProjectCommand,
)
from axcalib.pipelines.project import (
    LocalProjectService,
    TwoGatePptxPipeline,
    TwoGatePptxRequest,
)

__all__ = [
    "LocalPipeline",
    "DossierFreezePipeline",
    "DossierFreezeRequest",
    "DossierInitializePipeline",
    "DossierInitializeRequest",
    "DossierUpdatePipeline",
    "DossierUpdateRequest",
    "LocalProjectService",
    "PipelineRegistry",
    "TwoGatePptxPipeline",
    "TwoGatePptxRequest",
    "BindProjectCommand",
    "DecideProgramCompletionCommand",
    "EducationCommand",
    "EducationProgramPipeline",
    "EnrollCommand",
    "ManualConfirmationCommand",
    "RecordScoreCommand",
    "StartMilestoneCommand",
    "SyncProjectCommand",
]
