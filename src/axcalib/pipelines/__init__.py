"""Composable local pipeline contracts and implementations."""

from axcalib.pipelines.base import (
    LocalPipeline,
    PipelineContext,
    PipelineDescriptor,
    PipelineRegistry,
)
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
    ProjectSourceIntegrityError,
    TwoGatePptxPipeline,
    TwoGatePptxRequest,
)
from axcalib.pipelines.recovery import (
    EducationTransactionReconcilePipeline,
    EducationTransactionReconcilePipelineResult,
    TransactionReconcilePipeline,
    TransactionReconcilePipelineResult,
    TransactionReconcileRequest,
    WorkspaceMaintenancePipeline,
    WorkspaceMaintenanceRequest,
)

__all__ = [
    "EducationTransactionReconcilePipeline",
    "EducationTransactionReconcilePipelineResult",
    "LocalPipeline",
    "PipelineContext",
    "PipelineDescriptor",
    "DossierFreezePipeline",
    "DossierFreezeRequest",
    "DossierInitializePipeline",
    "DossierInitializeRequest",
    "DossierUpdatePipeline",
    "DossierUpdateRequest",
    "LocalProjectService",
    "ProjectSourceIntegrityError",
    "PipelineRegistry",
    "TwoGatePptxPipeline",
    "TwoGatePptxRequest",
    "TransactionReconcilePipeline",
    "TransactionReconcilePipelineResult",
    "TransactionReconcileRequest",
    "WorkspaceMaintenancePipeline",
    "WorkspaceMaintenanceRequest",
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
