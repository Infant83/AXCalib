"""Read-only status/validation and offline test/evaluation entrypoint."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tomllib
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any

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
    "config/axcalib.expert.example.toml",
    "docs/schemas/runtime-config.schema.json",
    "docs/api/README.md",
    "docs/api/openapi.v1alpha1.json",
    "docs/api/examples/registration-evaluation.request.json",
    "docs/api/examples/completion-evaluation.request.json",
    "docs/api/examples/run-accepted.response.json",
    "docs/product/product-brief.md",
    "docs/manuals/README.md",
    "docs/manuals/00-excalibur-concept.md",
    "docs/manuals/01-five-minute-start.md",
    "docs/manuals/02-configuration-and-api.md",
    "docs/manuals/03-webtoon-tutorial-storyboard.md",
    "docs/manuals/diagrams/authority-model.svg",
    "docs/manuals/assets/axcalib-authority-hero.jpg",
    "docs/manuals/assets/axcalib-six-panel-tutorial.jpg",
    "docs/manuals/assets/README.md",
    "docs/readiness/development-readiness-audit.md",
    "docs/evaluation/oled-qc-pptx-demo.md",
    "docs/architecture/README.md",
    "docs/architecture/composable-pipeline-plan.md",
    "docs/architecture/workflow-blueprint.md",
    "docs/architecture/module-delivery-plan.md",
    "docs/architecture/diagrams/workflow-at-a-glance.svg",
    "docs/architecture/axcalib-visual-guide.md",
    "docs/architecture/diagrams/axcalib-ecosystem-infographic.svg",
    "docs/architecture/diagrams/axcalib-ecosystem-infographic.png",
    "docs/presentations/README.md",
    "docs/presentations/AXCalib_Workflow_Architecture_v0.3-p1.pptx",
    "docs/adr/ADR-013-composable-local-pipelines.md",
    "docs/adr/ADR-014-progressive-configuration-and-openapi.md",
    "docs/adr/ADR-015-image-only-pptx-offline-evidence.md",
    "docs/workflows/two_gate_pipeline.md",
    "docs/rubrics/registration_checklist.md",
    "docs/rubrics/completion_checklist.md",
    "docs/rubrics/hitl_review_checklist.md",
    "src/axcalib/workflows/two_gate.py",
    "src/axcalib/client.py",
    "src/axcalib/pipelines/project.py",
    "src/axcalib/dossier/repository.py",
    "src/axcalib/ingest/pptx.py",
    "src/axcalib/evaluation/offline.py",
    "scripts/pipelines/run_two_gate_pptx.py",
    "tests/sources/oled_qc_project_outline.pptx",
    "tests/sources/oled_qc_project_outline.axcalib.json",
    "fixtures/synthetic/workflow_scenarios.json",
    "fixtures/synthetic/historical_cases.json",
    "evals/pptx_vertical_slice.py",
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
        "AXCalib_Concept_Overview.md",
        "docs/architecture/README.md",
        "docs/architecture/axcalib-visual-guide.md",
        "docs/architecture/workflow-blueprint.md",
        "docs/architecture/module-delivery-plan.md",
        "docs/architecture/composable-pipeline-plan.md",
        "docs/presentations/README.md",
        "docs/product/product-brief.md",
        "docs/manuals/README.md",
        "docs/manuals/00-excalibur-concept.md",
        "docs/manuals/01-five-minute-start.md",
        "docs/manuals/02-configuration-and-api.md",
        "docs/manuals/03-webtoon-tutorial-storyboard.md",
        "docs/api/README.md",
        "docs/readiness/development-readiness-audit.md",
        "apps/api/README.md",
        "apps/web/README.md",
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

    authority_svg = ROOT / "docs" / "manuals" / "diagrams" / "authority-model.svg"
    try:
        authority_root = ET.parse(authority_svg).getroot()
    except ET.ParseError as error:
        errors.append(f"authority-model.svg: invalid XML: {error}")
    else:
        namespace = {"svg": "http://www.w3.org/2000/svg"}
        title = authority_root.find("svg:title", namespace)
        description = authority_root.find("svg:desc", namespace)
        if title is None or not (title.text or "").strip():
            errors.append("authority-model.svg: accessible title is required")
        if description is None or not (description.text or "").strip():
            errors.append("authority-model.svg: accessible description is required")
        if authority_root.get("role") != "img" or not authority_root.get("aria-labelledby"):
            errors.append("authority-model.svg: role and aria-labelledby are required")

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
    for path in [
        ROOT / "config" / "axcalib.toml",
        ROOT / "config" / "axcalib.expert.example.toml",
    ]:
        for match in assignment.finditer(path.read_text(encoding="utf-8")):
            value = match.group(2)
            if not value.startswith(allowed_prefixes):
                errors.append(f"{path.relative_to(ROOT)}: possible literal secret")
    return errors


def _resolve_json_pointer(root: dict[str, Any], pointer: str) -> dict[str, Any]:
    current: Any = root
    for token in pointer.removeprefix("#/").split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        current = current[token]
    if not isinstance(current, dict):
        raise TypeError(f"schema pointer does not resolve to an object: {pointer}")
    return current


def _json_schema_errors(
    value: Any,
    schema: dict[str, Any],
    root: dict[str, Any],
    location: str,
) -> list[str]:
    """Validate the small JSON Schema subset used by harness-owned contracts."""

    errors: list[str] = []
    reference = schema.get("$ref")
    if isinstance(reference, str):
        if not reference.startswith("#/"):
            return [f"{location}: unsupported external schema reference {reference}"]
        try:
            target = _resolve_json_pointer(root, reference)
        except (KeyError, TypeError) as error:
            return [f"{location}: invalid schema reference {reference}: {error}"]
        return _json_schema_errors(value, target, root, location)

    if "const" in schema and value != schema["const"]:
        errors.append(f"{location}: must equal {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{location}: value {value!r} is not in the allowed enum")

    expected_type = schema.get("type")
    if isinstance(expected_type, list):
        type_matches = any(
            not _json_schema_errors(value, {"type": item}, root, location)
            for item in expected_type
        )
        if not type_matches:
            errors.append(f"{location}: expected one of types {expected_type}")
            return errors
    elif expected_type == "object" and not isinstance(value, dict):
        return [f"{location}: expected object"]
    elif expected_type == "array" and not isinstance(value, list):
        return [f"{location}: expected array"]
    elif expected_type == "string" and not isinstance(value, str):
        return [f"{location}: expected string"]
    elif expected_type == "boolean" and not isinstance(value, bool):
        return [f"{location}: expected boolean"]
    elif expected_type == "integer" and (
        not isinstance(value, int) or isinstance(value, bool)
    ):
        return [f"{location}: expected integer"]
    elif expected_type == "number" and (
        not isinstance(value, (int, float)) or isinstance(value, bool)
    ):
        return [f"{location}: expected number"]

    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                errors.append(f"{location}: missing required property {key}")
        minimum_properties = schema.get("minProperties")
        if isinstance(minimum_properties, int) and len(value) < minimum_properties:
            errors.append(f"{location}: requires at least {minimum_properties} properties")
        properties = schema.get("properties", {})
        additional = schema.get("additionalProperties", True)
        for key, item in value.items():
            child_location = f"{location}.{key}"
            if key in properties:
                errors.extend(
                    _json_schema_errors(item, properties[key], root, child_location)
                )
            elif additional is False:
                errors.append(f"{location}: unknown property {key}")
            elif isinstance(additional, dict):
                errors.extend(_json_schema_errors(item, additional, root, child_location))

    if isinstance(value, list):
        minimum_items = schema.get("minItems")
        if isinstance(minimum_items, int) and len(value) < minimum_items:
            errors.append(f"{location}: requires at least {minimum_items} items")
        if schema.get("uniqueItems"):
            serialized = [json.dumps(item, sort_keys=True, ensure_ascii=False) for item in value]
            if len(serialized) != len(set(serialized)):
                errors.append(f"{location}: items must be unique")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                errors.extend(
                    _json_schema_errors(item, item_schema, root, f"{location}[{index}]")
                )

    if isinstance(value, str):
        minimum_length = schema.get("minLength")
        maximum_length = schema.get("maxLength")
        if isinstance(minimum_length, int) and len(value) < minimum_length:
            errors.append(f"{location}: shorter than {minimum_length}")
        if isinstance(maximum_length, int) and len(value) > maximum_length:
            errors.append(f"{location}: longer than {maximum_length}")
        pattern = schema.get("pattern")
        if isinstance(pattern, str) and re.search(pattern, value) is None:
            errors.append(f"{location}: does not match pattern {pattern}")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        if isinstance(minimum, (int, float)) and value < minimum:
            errors.append(f"{location}: must be at least {minimum}")
        if isinstance(maximum, (int, float)) and value > maximum:
            errors.append(f"{location}: must be at most {maximum}")
    return errors


def _nested_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            keys.add(str(key))
            keys.update(_nested_keys(item))
    elif isinstance(value, list):
        for item in value:
            keys.update(_nested_keys(item))
    return keys


def _configuration_contract_errors() -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    schema = json.loads(
        (ROOT / "docs" / "schemas" / "runtime-config.schema.json").read_text(
            encoding="utf-8"
        )
    )
    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        errors.append("runtime config schema must use JSON Schema Draft 2020-12")
    if schema.get("additionalProperties") is not False:
        errors.append("runtime config schema root must reject unknown properties")

    forbidden = {
        "admin_approval_required",
        "approval_notification_required",
        "auto_approve",
        "auto_certify",
        "final_decision",
        "mandatory_hitl",
        "skip_hitl",
    }
    from axcalib.evaluation.similarity import SimilarityPolicy

    for relative in ("config/axcalib.toml", "config/axcalib.expert.example.toml"):
        path = ROOT / relative
        try:
            config = tomllib.loads(path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as error:
            errors.append(f"{relative}: invalid TOML: {error}")
            continue
        errors.extend(
            f"{relative}: {message}"
            for message in _json_schema_errors(config, schema, schema, "config")
        )
        exposed = forbidden.intersection(_nested_keys(config))
        if exposed:
            errors.append(f"{relative}: protected keys exposed: {sorted(exposed)}")

        profiles = config.get("profiles", {})
        retrieval = config.get("retrieval", {})
        notifications = config.get("notifications", {})
        default_profile = config.get("project", {}).get("default_profile")
        if default_profile not in profiles:
            errors.append(f"{relative}: default_profile does not name a configured profile")
        for profile_name, profile in profiles.items():
            notification_name = profile.get("notification")
            notification = notifications.get(notification_name)
            if not notification or not notification.get("enabled"):
                errors.append(
                    f"{relative}: profile {profile_name} requires an enabled notification"
                )
            for stage in ("registration", "completion"):
                retrieval_name = profile.get(f"{stage}_retrieval")
                raw = retrieval.get(retrieval_name)
                if raw is None:
                    errors.append(
                        f"{relative}: profile {profile_name} references missing retrieval "
                        f"{retrieval_name}"
                    )
                    continue
                policy = SimilarityPolicy(
                    adapter=str(raw.get("adapter", "null")),
                    stage=str(raw.get("stage", "")),
                    portion=float(raw.get("similarity_portion", 0.0)),
                    required_for_decision=bool(raw.get("required_for_decision", False)),
                )
                errors.extend(
                    f"{relative}: retrieval.{retrieval_name}: {message}"
                    for message in policy.errors()
                )
                warnings.extend(
                    f"{relative}: retrieval.{retrieval_name}: {message}"
                    for message in policy.warnings()
                )
                if raw.get("stage") != stage:
                    errors.append(
                        f"{relative}: retrieval {retrieval_name} must be stage {stage}"
                    )

    default = tomllib.loads(
        (ROOT / "config" / "axcalib.toml").read_text(encoding="utf-8")
    )
    offline = default.get("profiles", {}).get("offline", {})
    recording = default.get("notifications", {}).get(offline.get("notification"), {})
    if recording.get("adapter") != "recording" or recording.get("enabled") is not True:
        errors.append("offline profile requires the enabled recording notification adapter")
    return errors, warnings


def _api_contract_errors() -> list[str]:
    errors: list[str] = []
    openapi_path = ROOT / "docs" / "api" / "openapi.v1alpha1.json"
    try:
        contract = json.loads(openapi_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        return [f"openapi.v1alpha1.json: invalid JSON: {error}"]
    if contract.get("openapi") != "3.1.0":
        errors.append("OpenAPI contract must be version 3.1.0")
    if contract.get("jsonSchemaDialect") != "https://json-schema.org/draft/2020-12/schema":
        errors.append("OpenAPI contract must use JSON Schema Draft 2020-12")
    if contract.get("security") != [{"bearerAuth": []}]:
        errors.append("OpenAPI contract must require bearerAuth globally")
    security_scheme = contract.get("components", {}).get("securitySchemes", {}).get(
        "bearerAuth", {}
    )
    if security_scheme.get("type") != "http" or security_scheme.get("scheme") != "bearer":
        errors.append("OpenAPI bearerAuth security scheme is incomplete")

    required_paths = {
        "/v1/projects/{project_id}/evaluations/{stage}",
        "/v1/runs/{run_id}",
        "/v1/runs/{run_id}/commands",
        "/v1/capabilities",
    }
    missing_paths = required_paths.difference(contract.get("paths", {}))
    if missing_paths:
        errors.append(f"OpenAPI contract missing paths: {sorted(missing_paths)}")
    schemas = contract.get("components", {}).get("schemas", {})
    for name in ("EvaluationOptions", "WorkflowCommandRequest"):
        if schemas.get(name, {}).get("additionalProperties") is not False:
            errors.append(f"OpenAPI schema {name} must reject unknown properties")
    forbidden = {
        "admin_approval_required",
        "approval_notification_required",
        "auto_approve",
        "auto_certify",
        "final_decision",
        "mandatory_hitl",
        "skip_hitl",
    }
    input_schemas = {
        name: schemas.get(name, {})
        for name in (
            "EvaluationRequest",
            "EvaluationOptions",
            "RetrievalOptions",
            "ModelOptions",
            "ReportOptions",
            "WorkflowCommandRequest",
        )
    }
    exposed = forbidden.intersection(_nested_keys(input_schemas))
    if exposed:
        errors.append(f"OpenAPI input schemas expose protected keys: {sorted(exposed)}")

    example_contracts = (
        (
            "docs/api/examples/registration-evaluation.request.json",
            "EvaluationRequest",
        ),
        ("docs/api/examples/completion-evaluation.request.json", "EvaluationRequest"),
        ("docs/api/examples/run-accepted.response.json", "RunAccepted"),
    )
    for relative, schema_name in example_contracts:
        try:
            example = json.loads((ROOT / relative).read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            errors.append(f"{relative}: invalid JSON: {error}")
            continue
        schema = schemas.get(schema_name)
        if not isinstance(schema, dict):
            errors.append(f"OpenAPI contract missing schema {schema_name}")
            continue
        errors.extend(
            f"{relative}: {message}"
            for message in _json_schema_errors(example, schema, contract, "example")
        )
    return errors


def _readiness_contract_errors() -> list[str]:
    errors: list[str] = []
    path = ROOT / "docs" / "readiness" / "development-readiness-audit.md"
    metadata = _frontmatter(path)
    expected = {
        "status": "offline_slice_implemented",
        "verdict": "OFFLINE_VERTICAL_SLICE_VERIFIED",
        "owner_signoff": "user_directive_for_local_offline_slice",
    }
    for key, value in expected.items():
        if metadata.get(key) != value:
            errors.append(f"development readiness audit: {key} must be {value}")
    content = path.read_text(encoding="utf-8")
    for token in ("VERIFIED", "NO-GO", "local/offline", "Product/Evaluation Owner"):
        if token not in content:
            errors.append(f"development readiness audit: missing token {token}")
    return errors


def _pptx_fixture_errors() -> list[str]:
    errors: list[str] = []
    source = ROOT / "tests" / "sources" / "oled_qc_project_outline.pptx"
    sidecar_path = (
        ROOT / "tests" / "sources" / "oled_qc_project_outline.axcalib.json"
    )
    try:
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        return [f"PPTX sidecar: invalid JSON: {error}"]
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if sidecar.get("schema_version") != "axcalib.pptx-sidecar/v1":
        errors.append("PPTX sidecar: unsupported schema_version")
    if sidecar.get("source_sha256") != digest:
        errors.append("PPTX sidecar: source_sha256 does not match supplied PPTX")
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

    from axcalib.workflows.two_gate import approval_transition_errors

    errors.extend(approval_transition_errors())

    for relative, expected_stage in CHECKLISTS:
        metadata = _frontmatter(ROOT / relative)
        for key in ("rubric_id", "version", "stage", "status", "owner"):
            if not metadata.get(key):
                errors.append(f"{relative}: missing frontmatter key {key}")
        if metadata.get("stage") != expected_stage:
            errors.append(f"{relative}: stage must be {expected_stage}")

    config_errors, config_warnings = _configuration_contract_errors()
    errors.extend(config_errors)
    warnings.extend(config_warnings)
    errors.extend(_api_contract_errors())
    errors.extend(_readiness_contract_errors())
    errors.extend(_local_markdown_link_errors())
    errors.extend(_architecture_document_errors())
    errors.extend(_pptx_fixture_errors())
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
    print("  architecture control: 8 Mermaid views + SVG + M00-M13 module board")
    print("  implemented: supplied-PPTX two-gate offline vertical slice")
    print("  boundary: T1/model/API/Web/operations are not complete")
    return 0


def show_next() -> int:
    print("Next executable slice: WP-01/03 contract hardening")
    print("  1. export dossier JSON Schema and effective-config manifest")
    print("  2. add idempotency, stale result, durable local outbox, and recovery")
    print("  3. move Markdown criteria into a structured rubric registry")
    print("  4. add actual-template field/locator fixtures when supplied")
    print("  5. connect a Typer CLI to the same allowlisted pipeline")
    print("Prerequisite for actual evaluation: Product/Evaluation Owner rubric approval")
    print("Scope guard: no real data, live model, Vector DB, deployment, or secret")
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
    for script in ("evals/workflow_smoke.py", "evals/pptx_vertical_slice.py"):
        result = _run([sys.executable, script])
        if result:
            return result
    return 0


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
