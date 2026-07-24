from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "pipelines" / "validate_evaluation_owner_package.py"
PACKAGE = ROOT / "docs" / "evaluation" / "templates" / "evaluation-owner-package"


def test_owner_template_script_reports_non_official_draft() -> None:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        [str(ROOT / "src"), str(ROOT), environment.get("PYTHONPATH", "")]
    )
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--package",
            str(PACKAGE),
            "--allow-draft",
            "--print-hashes",
        ],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["valid"] is True
    assert payload["status"] == "draft"
    assert payload["official_quality_executable"] is False
    assert payload["registration_labels"] == 1
    assert payload["completion_labels"] == 1


def test_owner_template_script_fails_closed_without_draft_opt_in() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--package", str(PACKAGE)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 2
    assert "not executable" in result.stderr


def test_owner_template_script_can_compute_hashes_before_validation() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--package",
            str(PACKAGE),
            "--hashes-only",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    hashes = json.loads(result.stdout)["hashes"]
    assert len(hashes["policy_canonical_sha256"]) == 64
    assert len(hashes["labels_sha256"]) == 64
    assert len(hashes["approval_sha256"]) == 64
