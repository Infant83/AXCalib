"""Read-only status/validation and offline test/evaluation entrypoint."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tomllib
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

REQUIRED_PATHS = (
    "AGENTS.md",
    "README.md",
    "WORK_SPEC.md",
    "GOAL.md",
    "DESIGN.md",
    "AXCalib_Concept_Overview.md",
    "PROJECT_STATE.md",
    "DECISIONS.md",
    "RISK_REGISTER.md",
    "pyproject.toml",
    "uv.lock",
    "prep.ps1",
    "config/axcalib.toml",
    "docs/architecture/README.md",
    "docs/architecture/composable-pipeline-plan.md",
    "docs/architecture/workflow-blueprint.md",
    "docs/architecture/module-delivery-plan.md",
    "docs/architecture/diagrams/workflow-at-a-glance.svg",
    "docs/presentations/README.md",
    "docs/presentations/AXCalib_Workflow_Architecture_v0.3-p1.pptx",
    "docs/adr/ADR-013-composable-local-pipelines.md",
    "docs/workflows/two_gate_pipeline.md",
    "docs/rubrics/registration_checklist.md",
    "docs/rubrics/completion_checklist.md",
    "docs/rubrics/hitl_review_checklist.md",
    "src/axcalib/workflows/two_gate.py",
    "fixtures/synthetic/workflow_scenarios.json",
)

CHECKLISTS = (
    ("docs/rubrics/registration_checklist.md", "registration"),
    ("docs/rubrics/completion_checklist.md", "completion"),
    ("docs/rubrics/hitl_review_checklist.md", "hitl"),
)


def _frontmatter(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    result: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return result
        if ":" in line:
            key, value = line.split(":", 1)
            result[key.strip()] = value.strip()
    return {}


def _state() -> dict[str, str]:
    return _frontmatter(ROOT / "PROJECT_STATE.md")


def _local_markdown_link_errors() -> list[str]:
    errors: list[str] = []
    pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
    for name in (
        "README.md",
        "WORK_SPEC.md",
        "GOAL.md",
        "DESIGN.md",
        "AGENTS.md",
        "docs/architecture/README.md",
        "docs/architecture/workflow-blueprint.md",
        "docs/architecture/module-delivery-plan.md",
        "docs/architecture/composable-pipeline-plan.md",
        "docs/presentations/README.md",
    ):
        path = ROOT / name
        for target in pattern.findall(path.read_text(encoding="utf-8")):
            clean = target.split("#", 1)[0].strip()
            if not clean or clean.startswith(("http://", "https://", "mailto:")):
                continue
            if not (path.parent / clean).exists():
                errors.append(f"{name}: missing local link target {clean}")
    return errors


def _architecture_document_errors() -> list[str]:
    errors: list[str] = []
    blueprint_path = ROOT / "docs" / "architecture" / "workflow-blueprint.md"
    blueprint = blueprint_path.read_text(encoding="utf-8")
    if blueprint.count("```mermaid") < 7:
        errors.append("workflow-blueprint.md: at least 7 Mermaid views are required")
    for token in (
        "two-gate-standard/v1",
        "waiting_human",
        "M00 Pipeline Kernel",
        "M13 Web Review",
        "Delivery Wave",
    ):
        if token not in blueprint:
            errors.append(f"workflow-blueprint.md: missing required token {token}")

    module_plan = (
        ROOT / "docs" / "architecture" / "module-delivery-plan.md"
    ).read_text(encoding="utf-8")
    for index in range(14):
        module_id = f"M{index:02d}"
        if module_id not in module_plan:
            errors.append(f"module-delivery-plan.md: missing module {module_id}")
    for token in (
        "Module Control Board",
        "Exit Evidence",
        "Dependency Wave",
        "다음 실행 가능한 작업",
    ):
        if token not in module_plan:
            errors.append(f"module-delivery-plan.md: missing required section {token}")

    svg_path = ROOT / "docs" / "architecture" / "diagrams" / "workflow-at-a-glance.svg"
    try:
        root = ET.parse(svg_path).getroot()
    except ET.ParseError as error:
        errors.append(f"workflow-at-a-glance.svg: invalid XML: {error}")
    else:
        namespace = {"svg": "http://www.w3.org/2000/svg"}
        title = root.find("svg:title", namespace)
        description = root.find("svg:desc", namespace)
        if title is None or not (title.text or "").strip():
            errors.append("workflow-at-a-glance.svg: accessible title is required")
        if description is None or not (description.text or "").strip():
            errors.append("workflow-at-a-glance.svg: accessible description is required")
        if root.get("role") != "img" or not root.get("aria-labelledby"):
            errors.append("workflow-at-a-glance.svg: role and aria-labelledby are required")

    deck_path = (
        ROOT
        / "docs"
        / "presentations"
        / "AXCalib_Workflow_Architecture_v0.3-p1.pptx"
    )
    try:
        with zipfile.ZipFile(deck_path) as deck:
            slide_parts = [
                name
                for name in deck.namelist()
                if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)
            ]
    except (OSError, zipfile.BadZipFile) as error:
        errors.append(f"architecture presentation: invalid PPTX package: {error}")
    else:
        if len(slide_parts) != 12:
            errors.append(
                "architecture presentation: expected 12 slides, "
                f"found {len(slide_parts)}"
            )
    return errors


def _secret_errors() -> list[str]:
    errors: list[str] = []
    assignment = re.compile(
        r"(?i)(api[_-]?key|token|password|secret)\s*[=:]\s*[\"']?([^\s\"']+)"
    )
    allowed_prefixes = ("$", "${", "<", "AXCALIB_", "not_set", "none", "env")
    for path in [ROOT / "config" / "axcalib.toml"]:
        for match in assignment.finditer(path.read_text(encoding="utf-8")):
            value = match.group(2)
            if not value.startswith(allowed_prefixes):
                errors.append(f"{path.relative_to(ROOT)}: possible literal secret")
    return errors


def validate_workspace() -> tuple[list[str], list[str]]:
    """Return validation errors and warnings without changing the workspace."""

    errors = [
        f"missing required path: {item}"
        for item in REQUIRED_PATHS
        if not (ROOT / item).exists()
    ]
    warnings: list[str] = []
    if errors:
        return errors, warnings

    config = tomllib.loads((ROOT / "config" / "axcalib.toml").read_text(encoding="utf-8"))
    workflow = config.get("workflow", {})
    if workflow.get("admin_approval_required") is not True:
        errors.append("workflow.admin_approval_required must be true")
    if workflow.get("approval_notification_required") is not True:
        errors.append("workflow.approval_notification_required must be true")
    if workflow.get("mentor_assignment") != "optional":
        errors.append("workflow.mentor_assignment must be optional")

    from axcalib.evaluation.similarity import SimilarityPolicy
    from axcalib.workflows.two_gate import approval_transition_errors

    for stage in ("registration", "completion"):
        raw = config.get("retrieval", {}).get(stage, {})
        policy = SimilarityPolicy(
            adapter=str(raw.get("adapter", "disabled")),
            stage=str(raw.get("stage", "")),
            portion=float(raw.get("similarity_portion", 0.0)),
            required_for_decision=bool(raw.get("required_for_decision", False)),
        )
        errors.extend(f"retrieval.{stage}: {message}" for message in policy.errors())
        warnings.extend(f"retrieval.{stage}: {message}" for message in policy.warnings())

    errors.extend(approval_transition_errors())

    for relative, expected_stage in CHECKLISTS:
        metadata = _frontmatter(ROOT / relative)
        for key in ("rubric_id", "version", "stage", "status", "owner"):
            if not metadata.get(key):
                errors.append(f"{relative}: missing frontmatter key {key}")
        if metadata.get("stage") != expected_stage:
            errors.append(f"{relative}: stage must be {expected_stage}")

    if config.get("project", {}).get("environment") == "offline":
        offline = config.get("notifications", {}).get("offline", {})
        if not offline.get("enabled") or offline.get("adapter") != "recording":
            errors.append("offline profile requires the recording notification adapter")

    errors.extend(_local_markdown_link_errors())
    errors.extend(_architecture_document_errors())
    errors.extend(_secret_errors())
    return errors, warnings


def show_status() -> int:
    state = _state()
    print("AXCalib workspace status")
    print(f"  baseline: {state.get('baseline', 'unknown')}")
    print(f"  phase: {state.get('phase', 'unknown')}")
    print(f"  gate: {state.get('gate', 'unknown')} ({state.get('gate_status', 'unknown')})")
    print(f"  status: {state.get('status', 'unknown')}")
    print(f"  current WP: {state.get('current_work_package', 'unknown')}")
    print(f"  next WP: {state.get('next_work_package', 'unknown')}")
    print("  data/model mode: synthetic + lexical; no live model or Vector DB")
    print("  architecture control: 7 Mermaid views + SVG + M00-M13 module board")
    return 0


def show_next() -> int:
    print("Next executable slice: WP-01 dossier vertical slice")
    print("  1. implement typed PipelineContext, PipelineRun, and allowlisted registry")
    print("  2. implement axcalib.dossier/v1alpha1 schema and dossier.freeze pipeline")
    print("  3. connect revision/hash snapshot to the two-gate state machine")
    print("  4. run the same synthetic pipeline through a thin Python script")
    print("  5. persist review request and notification outbox atomically")
    print("Prerequisites: no real data, live model, Vector DB, deployment, or secret is required")
    return 0


def run_validate() -> int:
    errors, warnings = validate_workspace()
    for warning in warnings:
        print(f"WARN: {warning}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print(f"validate: FAILED ({len(errors)} error(s), {len(warnings)} warning(s))")
        return 1
    print(f"validate: PASSED (0 errors, {len(warnings)} warning(s))")
    return 0


def _run(command: list[str]) -> int:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([str(SRC), str(ROOT), env.get("PYTHONPATH", "")])
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(command, cwd=ROOT, env=env, check=False).returncode


def run_tests() -> int:
    return _run([sys.executable, "-m", "pytest", "-q"])


def run_eval() -> int:
    return _run([sys.executable, "evals/workflow_smoke.py"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("status", "next", "validate", "test", "eval"))
    args = parser.parse_args(argv)
    commands = {
        "status": show_status,
        "next": show_next,
        "validate": run_validate,
        "test": run_tests,
        "eval": run_eval,
    }
    return commands[args.command]()


if __name__ == "__main__":
    raise SystemExit(main())
