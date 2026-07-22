"""Minimal public facade shared by local scripts and future delivery adapters."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from axcalib.evaluation import (
    EvidenceEvaluator,
    OfflineEvidenceEvaluator,
    StructuredModelEvaluator,
)
from axcalib.ingest import DoclingPptxParser
from axcalib.models import OpenAICompatibleClient
from axcalib.notifications.base import NotificationPort, RecordingNotifier
from axcalib.pipelines import (
    DossierFreezePipeline,
    DossierFreezeRequest,
    DossierInitializePipeline,
    DossierInitializeRequest,
    DossierUpdatePipeline,
    DossierUpdateRequest,
    EducationCommand,
    EducationProgramPipeline,
    EducationTransactionReconcilePipeline,
    EducationTransactionReconcilePipelineResult,
    LocalProjectService,
    PipelineContext,
    PipelineRegistry,
    TransactionReconcilePipeline,
    TransactionReconcilePipelineResult,
    TransactionReconcileRequest,
    TwoGatePptxPipeline,
    TwoGatePptxRequest,
    WorkspaceMaintenancePipeline,
    WorkspaceMaintenanceRequest,
)
from axcalib.policies import DEFAULT_REVIEW_PROFILE, ReviewProfileRegistry
from axcalib.programs import EducationProgramService
from axcalib.retrieval import LexicalRetriever, load_historical_cases
from axcalib.runtime import (
    BatchManifest,
    BatchResult,
    LocalBatchRunner,
    LocalIdempotencyStore,
    LocalPipelineExecutor,
    LocalPipelineJobQueue,
    LocalPipelineWorker,
    LocalWorkspaceMaintenance,
    MaintenanceResult,
    PipelineExecutionResult,
    load_runtime_config,
)
from axcalib.schemas import (
    DossierFreezeResult,
    EducationPipelineResult,
    EducationProgram,
    EffectiveConfigRef,
    PipelineResult,
    ProgramRef,
    ProjectDossier,
    ReviewContext,
    ReviewerAdjustment,
    ReviewStage,
    WorkflowRunSummary,
)
from axcalib.workflows.two_gate import ActorRole


class _ProjectDecisionReplayInput(BaseModel):
    """Canonical command identity stored by the local idempotency adapter."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: str
    stage: ReviewStage
    actor_id: str
    authority_context: str
    expected_revision: int
    command: str
    rationale: str
    adjustments: tuple[ReviewerAdjustment, ...]


class AXCalib:
    """Small library-first interface for the two-gate reference workflow."""

    def __init__(
        self,
        workspace: Path | str,
        *,
        notifier: NotificationPort | None = None,
        evaluator: EvidenceEvaluator | None = None,
        review_profiles: ReviewProfileRegistry | None = None,
        default_review_profile: str = DEFAULT_REVIEW_PROFILE,
        docling_parser: DoclingPptxParser | None = None,
        effective_config: EffectiveConfigRef | None = None,
    ) -> None:
        self.service = LocalProjectService(
            Path(workspace),
            notifier=notifier or RecordingNotifier(),
            evaluator=evaluator,
            review_profiles=review_profiles,
            default_review_profile=default_review_profile,
            docling_parser=docling_parser,
            effective_config=effective_config,
        )
        self.idempotency = LocalIdempotencyStore(self.service.workspace / "idempotency")
        self.education = EducationProgramService(
            self.service.workspace / "education",
            dossiers=self.service.dossiers,
            notifier=self.service.notifier,
        )
        self.registry = PipelineRegistry()
        self.registry.register(
            TwoGatePptxPipeline.pipeline_id,
            TwoGatePptxPipeline.pipeline_version,
            lambda: TwoGatePptxPipeline(self.service),
            request_type=TwoGatePptxRequest,
            result_type=WorkflowRunSummary,
        )
        self.registry.register(
            DossierInitializePipeline.pipeline_id,
            DossierInitializePipeline.pipeline_version,
            lambda: DossierInitializePipeline(self.service),
            request_type=DossierInitializeRequest,
            result_type=PipelineResult,
        )
        self.registry.register(
            DossierUpdatePipeline.pipeline_id,
            DossierUpdatePipeline.pipeline_version,
            lambda: DossierUpdatePipeline(self.service),
            request_type=DossierUpdateRequest,
            result_type=PipelineResult,
        )
        self.registry.register(
            DossierFreezePipeline.pipeline_id,
            DossierFreezePipeline.pipeline_version,
            lambda: DossierFreezePipeline(self.service),
            request_type=DossierFreezeRequest,
            result_type=DossierFreezeResult,
        )
        self.registry.register(
            EducationProgramPipeline.pipeline_id,
            EducationProgramPipeline.pipeline_version,
            lambda: EducationProgramPipeline(self.education),
            request_type=EducationCommand,
            result_type=EducationPipelineResult,
        )
        self.registry.register(
            TransactionReconcilePipeline.pipeline_id,
            TransactionReconcilePipeline.pipeline_version,
            lambda: TransactionReconcilePipeline(self.service.transactions),
            request_type=TransactionReconcileRequest,
            result_type=TransactionReconcilePipelineResult,
        )
        self.registry.register(
            EducationTransactionReconcilePipeline.pipeline_id,
            EducationTransactionReconcilePipeline.pipeline_version,
            lambda: EducationTransactionReconcilePipeline(self.education.transactions),
            request_type=TransactionReconcileRequest,
            result_type=EducationTransactionReconcilePipelineResult,
        )
        self.registry.register(
            WorkspaceMaintenancePipeline.pipeline_id,
            WorkspaceMaintenancePipeline.pipeline_version,
            lambda: WorkspaceMaintenancePipeline(LocalWorkspaceMaintenance(self.service.workspace)),
            request_type=WorkspaceMaintenanceRequest,
            result_type=MaintenanceResult,
        )
        self.executor = LocalPipelineExecutor(
            self.service.workspace / "runs",
            self.registry,
        )
        self.jobs = LocalPipelineJobQueue(
            self.service.workspace / "jobs",
            self.executor,
        )
        self.batch = LocalBatchRunner(self.service.workspace / "batches", self.executor)

    def execute_pipeline(
        self,
        pipeline_id: str,
        pipeline_version: str,
        payload: object,
        *,
        context: PipelineContext | None = None,
    ) -> PipelineExecutionResult:
        """Execute one allowlisted pipeline with a durable checkpoint."""

        return self.executor.execute(
            pipeline_id,
            pipeline_version,
            payload,
            context=context,
        )

    async def aexecute_pipeline(
        self,
        pipeline_id: str,
        pipeline_version: str,
        payload: object,
        *,
        context: PipelineContext | None = None,
    ) -> PipelineExecutionResult:
        """Async equivalent of :meth:`execute_pipeline`."""

        return await self.executor.aexecute(
            pipeline_id,
            pipeline_version,
            payload,
            context=context,
        )

    def enqueue_pipeline(
        self,
        pipeline_id: str,
        pipeline_version: str,
        payload: object,
        *,
        context: PipelineContext,
    ) -> PipelineExecutionResult:
        """Persist one validated pipeline command for an explicit local worker."""

        return self.jobs.enqueue(
            pipeline_id,
            pipeline_version,
            payload,
            context=context,
        )

    def create_worker(
        self,
        *,
        worker_id: str,
        lease_seconds: float = 300.0,
    ) -> LocalPipelineWorker:
        """Create a one-job-at-a-time worker over this client's durable queue."""

        return LocalPipelineWorker(
            self.jobs,
            worker_id=worker_id,
            lease_seconds=lease_seconds,
        )

    def run_batch(
        self,
        manifest: BatchManifest,
        *,
        max_concurrency: int = 4,
    ) -> BatchResult:
        """Run a bounded local batch with per-item checkpoints."""

        return self.batch.run(manifest, max_concurrency=max_concurrency)

    @classmethod
    def from_toml(
        cls,
        config_path: Path | str,
        *,
        workspace: Path | str,
        historical_cases_path: Path | str | None = None,
        enable_docling: bool = False,
        live_model: bool = False,
    ) -> AXCalib:
        """Create an offline-safe runtime with optional Docling and model adapters."""

        path = Path(config_path).resolve()
        loaded = load_runtime_config(
            path,
            manifest_path=Path(workspace) / "runtime" / "effective-config.json",
        )
        config = loaded.value
        profile_name = config["project"]["default_profile"]
        profile = config["profiles"][profile_name]
        implemented: dict[str, set[str]] = {
            "storage": {"filesystem"},
            "evaluator": {"mock", "primary"} if live_model else {"mock"},
            "notification": {"recording"},
        }
        for key, expected in implemented.items():
            if profile.get(key) not in expected:
                raise NotImplementedError(
                    f"profile {profile_name!r} requires unimplemented {key}: {profile.get(key)!r}"
                )
        registration_config = config["retrieval"][profile["registration_retrieval"]]
        completion_config = config["retrieval"][profile["completion_retrieval"]]
        adapters = {registration_config["adapter"], completion_config["adapter"]}
        if adapters - {"lexical"}:
            raise NotImplementedError(
                "the offline runtime currently supports only the lexical retrieval adapter"
            )
        if historical_cases_path is None:
            candidate = path.parent.parent / "fixtures" / "synthetic" / "historical_cases.json"
            if not candidate.is_file():
                raise ValueError("historical_cases_path is required for lexical retrieval")
            historical_cases_path = candidate
        retriever = LexicalRetriever(load_historical_cases(Path(historical_cases_path)))
        baseline = OfflineEvidenceEvaluator(
            retriever,
            registration_similarity_portion=float(registration_config["similarity_portion"]),
            completion_similarity_portion=float(completion_config["similarity_portion"]),
        )
        evaluator: EvidenceEvaluator = baseline
        if live_model:
            evaluator = StructuredModelEvaluator(
                OpenAICompatibleClient.from_env(live=True),
                baseline=baseline,
            )
        review_profiles = ReviewProfileRegistry.with_builtin_default()
        review_profiles.load_directory(path.parent / "review_profiles")
        default_review_profile = config["project"].get(
            "default_review_profile", DEFAULT_REVIEW_PROFILE
        )
        return cls(
            workspace,
            evaluator=evaluator,
            review_profiles=review_profiles,
            default_review_profile=default_review_profile,
            docling_parser=DoclingPptxParser() if enable_docling else None,
            effective_config=loaded.reference,
        )

    def run_pptx(self, request: TwoGatePptxRequest) -> WorkflowRunSummary:
        """Run the allowlisted PPTX workflow synchronously."""

        pipeline = self.registry.create(
            TwoGatePptxPipeline.pipeline_id,
            TwoGatePptxPipeline.pipeline_version,
        )
        if request.idempotency_key:
            result = self.idempotency.execute(
                key=request.idempotency_key,
                operation=(
                    f"{TwoGatePptxPipeline.pipeline_id}@{TwoGatePptxPipeline.pipeline_version}"
                ),
                request=request,
                result_type=WorkflowRunSummary,
                call=lambda: pipeline.run(request),
            )
        else:
            result = pipeline.run(request)
        if not isinstance(result, WorkflowRunSummary):
            raise TypeError("two-gate pipeline returned an invalid result")
        return result

    async def arun_pptx(self, request: TwoGatePptxRequest) -> WorkflowRunSummary:
        """Run the same workflow asynchronously."""

        if request.idempotency_key:
            return await asyncio.to_thread(self.run_pptx, request)
        pipeline = self.registry.create(
            TwoGatePptxPipeline.pipeline_id,
            TwoGatePptxPipeline.pipeline_version,
        )
        result = await pipeline.arun(request)
        if not isinstance(result, WorkflowRunSummary):
            raise TypeError("two-gate pipeline returned an invalid result")
        return result

    def publish_program(self, program: EducationProgram) -> ProgramRef:
        """Publish an immutable, allowlisted education program definition."""

        return self.education.publish_program(program)

    def run_education(self, request: EducationCommand) -> EducationPipelineResult:
        """Run one typed education enrollment command."""

        pipeline = self.registry.create(
            EducationProgramPipeline.pipeline_id,
            EducationProgramPipeline.pipeline_version,
        )
        if request.idempotency_key:
            result = self.idempotency.execute(
                key=request.idempotency_key,
                operation=(
                    f"{EducationProgramPipeline.pipeline_id}@"
                    f"{EducationProgramPipeline.pipeline_version}:{request.action}"
                ),
                request=request,
                result_type=EducationPipelineResult,
                call=lambda: pipeline.run(request),
            )
        else:
            result = pipeline.run(request)
        if not isinstance(result, EducationPipelineResult):
            raise TypeError("education pipeline returned an invalid result")
        return result

    async def arun_education(self, request: EducationCommand) -> EducationPipelineResult:
        """Async equivalent of :meth:`run_education`."""

        return await asyncio.to_thread(self.run_education, request)

    def reconcile_transactions(
        self,
        transaction_id: str | None = None,
    ) -> TransactionReconcilePipelineResult:
        """Reconcile one or all local project transaction journals."""

        pipeline = self.registry.create(
            TransactionReconcilePipeline.pipeline_id,
            TransactionReconcilePipeline.pipeline_version,
        )
        result = pipeline.run(TransactionReconcileRequest(transaction_id=transaction_id))
        if not isinstance(result, TransactionReconcilePipelineResult):
            raise TypeError("transaction reconcile pipeline returned an invalid result")
        return result

    async def areconcile_transactions(
        self,
        transaction_id: str | None = None,
    ) -> TransactionReconcilePipelineResult:
        """Async equivalent of :meth:`reconcile_transactions`."""

        return await asyncio.to_thread(self.reconcile_transactions, transaction_id)

    def reconcile_education_transactions(
        self,
        transaction_id: str | None = None,
    ) -> EducationTransactionReconcilePipelineResult:
        """Reconcile one or all local education transaction journals."""

        pipeline = self.registry.create(
            EducationTransactionReconcilePipeline.pipeline_id,
            EducationTransactionReconcilePipeline.pipeline_version,
        )
        result = pipeline.run(TransactionReconcileRequest(transaction_id=transaction_id))
        if not isinstance(result, EducationTransactionReconcilePipelineResult):
            raise TypeError("education transaction reconcile returned an invalid result")
        return result

    async def areconcile_education_transactions(
        self,
        transaction_id: str | None = None,
    ) -> EducationTransactionReconcilePipelineResult:
        """Async equivalent of :meth:`reconcile_education_transactions`."""

        return await asyncio.to_thread(
            self.reconcile_education_transactions,
            transaction_id,
        )

    def register_case(
        self,
        proposal_path: Path | str,
        *,
        title: str,
        sidecar_path: Path | str | None = None,
        project_id: str | None = None,
        review_profile: str | None = None,
        review_context: ReviewContext | None = None,
        actor_id: str = "submitter:local",
        actor_role: Literal["submitter", "project_owner", "administrator"] = "submitter",
        expected_proposal_sha256: str | None = None,
        expected_sidecar_sha256: str | None = None,
    ) -> ProjectDossier:
        """Register source evidence as one policy-bound AXCalib dossier."""

        return self.service.create_project(
            Path(proposal_path),
            title=title,
            sidecar_path=Path(sidecar_path) if sidecar_path else None,
            project_id=project_id,
            review_profile=review_profile,
            review_context=review_context,
            actor_id=actor_id,
            actor_role=ActorRole(actor_role),
            expected_proposal_sha256=expected_proposal_sha256,
            expected_sidecar_sha256=expected_sidecar_sha256,
        )

    def create_project(
        self,
        proposal_path: Path | str,
        *,
        title: str,
        sidecar_path: Path | str | None = None,
        project_id: str | None = None,
        review_profile: str | None = None,
        review_context: ReviewContext | None = None,
        actor_id: str = "submitter:local",
        actor_role: Literal["submitter", "project_owner", "administrator"] = "submitter",
        expected_proposal_sha256: str | None = None,
        expected_sidecar_sha256: str | None = None,
    ) -> ProjectDossier:
        """Backward-compatible alias for :meth:`register_case`."""

        return self.register_case(
            proposal_path,
            title=title,
            sidecar_path=sidecar_path,
            project_id=project_id,
            review_profile=review_profile,
            review_context=review_context,
            actor_id=actor_id,
            actor_role=actor_role,
            expected_proposal_sha256=expected_proposal_sha256,
            expected_sidecar_sha256=expected_sidecar_sha256,
        )

    def submit_registration(self, project_id: str) -> PipelineResult:
        """Move a draft to the registration evaluation checkpoint."""

        return self.service.submit_registration(project_id)

    def assign_mentor(self, project_id: str, *, mentor_ref: str) -> PipelineResult:
        """Assign an optional mentor after registration approval."""

        return self.service.assign_mentor(project_id, mentor_ref=mentor_ref)

    def start_execution(self, project_id: str) -> PipelineResult:
        """Start execution after registration approval."""

        return self.service.start_execution(project_id)

    def record_progress(
        self,
        project_id: str,
        *,
        note: str,
        artifact_path: Path | str | None = None,
        sidecar_path: Path | str | None = None,
    ) -> PipelineResult:
        """Append an execution note and optional PPTX evidence reference."""

        return self.service.record_progress(
            project_id,
            note=note,
            artifact_path=Path(artifact_path) if artifact_path else None,
            sidecar_path=Path(sidecar_path) if sidecar_path else None,
        )

    def submit_completion(
        self,
        project_id: str,
        final_path: Path | str,
        *,
        sidecar_path: Path | str | None = None,
        approval_actor_id: str = "project-owner:local",
        approval_actor_role: Literal["project_owner", "mentor", "administrator"] = (
            "project_owner"
        ),
    ) -> PipelineResult:
        """Register final evidence when no mentor is assigned."""

        return self.service.submit_completion(
            project_id,
            Path(final_path),
            sidecar_path=Path(sidecar_path) if sidecar_path else None,
            approval_actor_id=approval_actor_id,
            approval_actor_role=ActorRole(approval_actor_role),
        )

    def evaluate(self, project_id: str, stage: ReviewStage | str) -> PipelineResult:
        """Evaluate one prepared gate without making a human decision."""

        normalized = ReviewStage(stage)
        if normalized is ReviewStage.REGISTRATION:
            return self.service.evaluate_registration(project_id)
        return self.service.evaluate_completion(project_id)

    async def aevaluate(self, project_id: str, stage: ReviewStage | str) -> PipelineResult:
        """Async equivalent of :meth:`evaluate`."""

        return await asyncio.to_thread(self.evaluate, project_id, stage)

    def decide_registration(
        self,
        project_id: str,
        *,
        command: Literal["approve", "reject"],
        actor_id: str,
        rationale: str,
        adjustments: tuple[ReviewerAdjustment, ...] = (),
        expected_revision: int | None = None,
        authority_context: str = "offline_unverified_actor",
        idempotency_key: str | None = None,
    ) -> PipelineResult:
        """Resume registration, optionally replaying one exact persisted command."""

        def call() -> PipelineResult:
            return self.service.decide_registration(
                project_id,
                command=command,
                actor_id=actor_id,
                rationale=rationale,
                adjustments=adjustments,
                expected_revision=expected_revision,
                authority_context=authority_context,
            )

        if idempotency_key is None:
            return call()
        if expected_revision is None:
            raise ValueError("expected_revision is required with an idempotency key")
        return self.idempotency.execute(
            key=idempotency_key,
            operation="project.decision.registration@v1alpha1",
            request=_ProjectDecisionReplayInput(
                project_id=project_id,
                stage=ReviewStage.REGISTRATION,
                actor_id=actor_id,
                authority_context=authority_context,
                expected_revision=expected_revision,
                command=command,
                rationale=rationale.strip(),
                adjustments=adjustments,
            ),
            result_type=PipelineResult,
            call=call,
        )

    def decide_completion(
        self,
        project_id: str,
        *,
        command: Literal["accept", "not_accept"],
        actor_id: str,
        rationale: str,
        adjustments: tuple[ReviewerAdjustment, ...] = (),
        expected_revision: int | None = None,
        authority_context: str = "offline_unverified_actor",
        idempotency_key: str | None = None,
    ) -> PipelineResult:
        """Resume completion, optionally replaying one exact persisted command."""

        def call() -> PipelineResult:
            return self.service.decide_completion(
                project_id,
                command=command,
                actor_id=actor_id,
                rationale=rationale,
                adjustments=adjustments,
                expected_revision=expected_revision,
                authority_context=authority_context,
            )

        if idempotency_key is None:
            return call()
        if expected_revision is None:
            raise ValueError("expected_revision is required with an idempotency key")
        return self.idempotency.execute(
            key=idempotency_key,
            operation="project.decision.completion@v1alpha1",
            request=_ProjectDecisionReplayInput(
                project_id=project_id,
                stage=ReviewStage.COMPLETION,
                actor_id=actor_id,
                authority_context=authority_context,
                expected_revision=expected_revision,
                command=command,
                rationale=rationale.strip(),
                adjustments=adjustments,
            ),
            result_type=PipelineResult,
            call=call,
        )


__all__ = ["AXCalib"]
