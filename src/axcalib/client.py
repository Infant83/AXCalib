"""Minimal public facade shared by local scripts and future delivery adapters."""

from __future__ import annotations

import asyncio
import tomllib
from pathlib import Path
from typing import Literal

from axcalib.evaluation import OfflineEvidenceEvaluator
from axcalib.notifications.base import NotificationPort, RecordingNotifier
from axcalib.pipelines import (
    LocalProjectService,
    PipelineRegistry,
    TwoGatePptxPipeline,
    TwoGatePptxRequest,
)
from axcalib.retrieval import LexicalRetriever, load_historical_cases
from axcalib.schemas import PipelineResult, ProjectDossier, ReviewStage, WorkflowRunSummary
from axcalib.workflows.two_gate import ActorRole


class AXCalib:
    """Small library-first interface for the offline two-gate MVP."""

    def __init__(
        self,
        workspace: Path | str,
        *,
        notifier: NotificationPort | None = None,
        evaluator: OfflineEvidenceEvaluator | None = None,
    ) -> None:
        self.service = LocalProjectService(
            Path(workspace),
            notifier=notifier or RecordingNotifier(),
            evaluator=evaluator,
        )
        self.registry = PipelineRegistry()
        self.registry.register(
            TwoGatePptxPipeline.pipeline_id,
            TwoGatePptxPipeline.pipeline_version,
            lambda: TwoGatePptxPipeline(self.service),
        )

    @classmethod
    def from_toml(
        cls,
        config_path: Path | str,
        *,
        workspace: Path | str,
        historical_cases_path: Path | str | None = None,
    ) -> AXCalib:
        """Create the implemented offline profile from a strict TOML surface."""

        path = Path(config_path).resolve()
        config = tomllib.loads(path.read_text(encoding="utf-8"))
        profile_name = config["project"]["default_profile"]
        profile = config["profiles"][profile_name]
        implemented = {
            "storage": "filesystem",
            "evaluator": "mock",
            "notification": "recording",
        }
        for key, expected in implemented.items():
            if profile.get(key) != expected:
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
        evaluator = OfflineEvidenceEvaluator(
            retriever,
            registration_similarity_portion=float(registration_config["similarity_portion"]),
            completion_similarity_portion=float(completion_config["similarity_portion"]),
        )
        return cls(workspace, evaluator=evaluator)

    def run_pptx(self, request: TwoGatePptxRequest) -> WorkflowRunSummary:
        """Run the allowlisted PPTX workflow synchronously."""

        pipeline = self.registry.create(
            TwoGatePptxPipeline.pipeline_id,
            TwoGatePptxPipeline.pipeline_version,
        )
        result = pipeline.run(request)
        if not isinstance(result, WorkflowRunSummary):
            raise TypeError("two-gate pipeline returned an invalid result")
        return result

    async def arun_pptx(self, request: TwoGatePptxRequest) -> WorkflowRunSummary:
        """Run the same workflow asynchronously."""

        pipeline = self.registry.create(
            TwoGatePptxPipeline.pipeline_id,
            TwoGatePptxPipeline.pipeline_version,
        )
        result = await pipeline.arun(request)
        if not isinstance(result, WorkflowRunSummary):
            raise TypeError("two-gate pipeline returned an invalid result")
        return result

    def create_project(
        self,
        proposal_path: Path | str,
        *,
        title: str,
        sidecar_path: Path | str | None = None,
        project_id: str | None = None,
    ) -> ProjectDossier:
        """Initialize a local dossier without submitting it."""

        return self.service.create_project(
            Path(proposal_path),
            title=title,
            sidecar_path=Path(sidecar_path) if sidecar_path else None,
            project_id=project_id,
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
    ) -> PipelineResult:
        """Resume registration with an explicit administrator command."""

        return self.service.decide_registration(
            project_id,
            command=command,
            actor_id=actor_id,
            rationale=rationale,
        )

    def decide_completion(
        self,
        project_id: str,
        *,
        command: Literal["accept", "not_accept"],
        actor_id: str,
        rationale: str,
    ) -> PipelineResult:
        """Resume completion with an explicit administrator command."""

        return self.service.decide_completion(
            project_id,
            command=command,
            actor_id=actor_id,
            rationale=rationale,
        )


__all__ = ["AXCalib"]
