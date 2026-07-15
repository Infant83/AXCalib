from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

from harness.prep import ROOT, validate_workspace

READ_ONLY_SURFACES = [
    ROOT / "PROJECT_STATE.md",
    ROOT / "config" / "axcalib.toml",
    ROOT / "config" / "axcalib.expert.example.toml",
    ROOT / "docs" / "schemas" / "runtime-config.schema.json",
    ROOT / "docs" / "api" / "openapi.v1alpha1.json",
    ROOT / "docs" / "readiness" / "development-readiness-audit.md",
    ROOT / "docs" / "manuals" / "diagrams" / "authority-model.svg",
    ROOT / "docs" / "rubrics" / "registration_checklist.md",
    ROOT / "docs" / "rubrics" / "completion_checklist.md",
    ROOT / "docs" / "rubrics" / "hitl_review_checklist.md",
]


def _hashes() -> dict[Path, str]:
    return {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in READ_ONLY_SURFACES}


def test_workspace_contract_validates() -> None:
    errors, _warnings = validate_workspace()
    assert errors == []


def test_status_and_validate_are_read_only() -> None:
    before = _hashes()
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    for command in ("status", "validate"):
        completed = subprocess.run(
            [sys.executable, "harness/prep.py", command],
            cwd=ROOT,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
    assert _hashes() == before
