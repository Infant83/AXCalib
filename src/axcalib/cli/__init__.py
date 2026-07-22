"""Thin Typer interface over the AXCalib library registry."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Annotated, Any

import typer
from pydantic import BaseModel
from rich.console import Console
from rich.table import Table

from axcalib import AXCalib
from axcalib.pipelines import PipelineContext
from axcalib.runtime import PipelineRunStatus, load_batch_jsonl

app = typer.Typer(
    name="axcalib",
    help="Evidence-first local AX certification workflow tools.",
    no_args_is_help=True,
)
pipeline_app = typer.Typer(help="Inspect and execute allowlisted local pipelines.")
run_app = typer.Typer(help="Inspect or cooperatively cancel durable pipeline runs.")
batch_app = typer.Typer(help="Run strict JSONL batches with per-item checkpoints.")
workspace_app = typer.Typer(help="Inspect or maintain the local AXCalib workspace.")
app.add_typer(pipeline_app, name="pipeline")
app.add_typer(run_app, name="run")
app.add_typer(batch_app, name="batch")
app.add_typer(workspace_app, name="workspace")

console = Console()


def _client(workspace: Path) -> AXCalib:
    return AXCalib(workspace.resolve())


def _json_value(value: BaseModel | dict[str, Any]) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return value


def _print_json(value: BaseModel | dict[str, Any]) -> None:
    console.print_json(
        json.dumps(_json_value(value), ensure_ascii=False, sort_keys=True)
    )


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise typer.BadParameter("request must be a readable UTF-8 JSON file") from error
    if not isinstance(value, dict):
        raise typer.BadParameter("request JSON root must be an object")
    return value


def _context(
    *,
    run_id: str | None,
    actor_id: str,
    actor_role: str,
    idempotency_key: str | None,
    expected_revision: int | None,
) -> PipelineContext:
    return PipelineContext(
        run_id=run_id or f"cli-{uuid.uuid4()}",
        actor_id=actor_id,
        actor_role=actor_role,
        idempotency_key=idempotency_key,
        expected_revision=expected_revision,
    )


def _exit_for_status(status: PipelineRunStatus) -> None:
    if status in {PipelineRunStatus.SUCCEEDED, PipelineRunStatus.WAITING_HUMAN}:
        return
    if status is PipelineRunStatus.RETRYABLE_FAILURE:
        raise typer.Exit(3)
    raise typer.Exit(2 if status in {
        PipelineRunStatus.BLOCKED,
        PipelineRunStatus.STALE,
        PipelineRunStatus.CANCELLED,
    } else 1)


@pipeline_app.command("list")
def list_pipelines(
    workspace: Annotated[Path, typer.Option("--workspace", "-w")],
    json_output: Annotated[bool, typer.Option("--json-output")] = False,
) -> None:
    """List the code-owned pipeline allowlist."""

    descriptors = _client(workspace).registry.descriptors()
    if json_output:
        _print_json({"pipelines": [item.model_dump(mode="json") for item in descriptors]})
        return
    table = Table(title="AXCalib allowlisted pipelines")
    table.add_column("Pipeline")
    table.add_column("Version")
    table.add_column("Request")
    table.add_column("Result")
    for item in descriptors:
        table.add_row(
            item.pipeline_id,
            item.pipeline_version,
            item.request_type,
            item.result_type,
        )
    console.print(table)


@pipeline_app.command("run")
def run_pipeline(
    pipeline_id: str,
    pipeline_version: str,
    request: Annotated[Path, typer.Option("--request", "-r")],
    workspace: Annotated[Path, typer.Option("--workspace", "-w")],
    run_id: Annotated[str | None, typer.Option("--run-id")] = None,
    actor_id: Annotated[str, typer.Option("--actor-id")] = "operator:cli",
    actor_role: Annotated[str, typer.Option("--actor-role")] = "operator",
    idempotency_key: Annotated[str | None, typer.Option("--idempotency-key")] = None,
    expected_revision: Annotated[int | None, typer.Option("--expected-revision")] = None,
) -> None:
    """Validate and execute one allowlisted pipeline request."""

    client = _client(workspace)
    result = client.execute_pipeline(
        pipeline_id,
        pipeline_version,
        _load_json_object(request),
        context=_context(
            run_id=run_id,
            actor_id=actor_id,
            actor_role=actor_role,
            idempotency_key=idempotency_key,
            expected_revision=expected_revision,
        ),
    )
    _print_json(result)
    _exit_for_status(result.status)


@run_app.command("status")
def run_status(
    run_id: str,
    workspace: Annotated[Path, typer.Option("--workspace", "-w")],
) -> None:
    """Read one durable run checkpoint without executing it."""

    _print_json(_client(workspace).executor.load(run_id))


@run_app.command("cancel")
def cancel_run(
    run_id: str,
    workspace: Annotated[Path, typer.Option("--workspace", "-w")],
    actor_id: Annotated[str, typer.Option("--actor-id")] = "operator:cli",
) -> None:
    """Write a cooperative cancellation request; never kill a process."""

    path = _client(workspace).executor.request_cancel(run_id, actor_id=actor_id)
    _print_json({"run_id": run_id, "status": "cancel_requested", "cancel_uri": str(path)})


@batch_app.command("run")
def run_batch(
    manifest: Path,
    workspace: Annotated[Path, typer.Option("--workspace", "-w")],
    batch_id: Annotated[str | None, typer.Option("--batch-id")] = None,
    max_concurrency: Annotated[int, typer.Option("--max-concurrency", min=1, max=32)] = 1,
) -> None:
    """Run one strict JSONL batch and preserve every item status."""

    client = _client(workspace)
    result = client.run_batch(
        load_batch_jsonl(manifest, batch_id=batch_id),
        max_concurrency=max_concurrency,
    )
    _print_json(result)
    if result.status == "partial_retryable_failure":
        raise typer.Exit(3)
    if result.status != "succeeded":
        raise typer.Exit(1)


@workspace_app.command("maintain")
def maintain_workspace(
    workspace: Annotated[Path, typer.Option("--workspace", "-w")],
    apply: Annotated[bool, typer.Option("--apply")] = False,
    stale_after_seconds: Annotated[
        float,
        typer.Option("--stale-after-seconds", min=1.0),
    ] = 3600.0,
    retention_seconds: Annotated[
        float,
        typer.Option("--retention-seconds", min=1.0),
    ] = 7 * 24 * 3600.0,
    quarantine_blocked_journals: Annotated[
        bool,
        typer.Option("--quarantine-blocked-journals"),
    ] = False,
    run_id: Annotated[str | None, typer.Option("--run-id")] = None,
) -> None:
    """Report candidates by default; apply only quarantines or archives."""

    client = _client(workspace)
    result = client.execute_pipeline(
        "workspace.maintenance",
        "v1alpha1",
        {
            "apply": apply,
            "stale_after_seconds": stale_after_seconds,
            "retention_seconds": retention_seconds,
            "quarantine_blocked_journals": quarantine_blocked_journals,
        },
        context=_context(
            run_id=run_id,
            actor_id="operator:cli",
            actor_role="operator",
            idempotency_key=None,
            expected_revision=None,
        ),
    )
    _print_json(result)
    _exit_for_status(result.status)


def main() -> None:
    """Console-script entrypoint."""

    app(prog_name="axcalib")


__all__ = ["app", "main"]
