from __future__ import annotations

import copy
import json
import tomllib

from harness.prep import ROOT, _json_schema_errors


def test_runtime_schema_rejects_unknown_protected_key() -> None:
    schema = json.loads(
        (ROOT / "docs" / "schemas" / "runtime-config.schema.json").read_text(
            encoding="utf-8"
        )
    )
    config = tomllib.loads(
        (ROOT / "config" / "axcalib.toml").read_text(encoding="utf-8")
    )
    modified = copy.deepcopy(config)
    modified["workflow"] = {"skip_hitl": True}

    errors = _json_schema_errors(modified, schema, schema, "config")

    assert any("unknown property workflow" in error for error in errors)


def test_openapi_request_rejects_hitl_override() -> None:
    contract = json.loads(
        (ROOT / "docs" / "api" / "openapi.v1alpha1.json").read_text(encoding="utf-8")
    )
    schema = contract["components"]["schemas"]["EvaluationRequest"]
    request = {
        "expected_revision": 3,
        "profile": "offline",
        "options": {"skip_hitl": True},
    }

    errors = _json_schema_errors(request, schema, contract, "request")

    assert any("unknown property skip_hitl" in error for error in errors)
