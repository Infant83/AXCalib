from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

from harness.prep import (
    DEFAULT_TEST_SEQUENCE,
    ROOT,
    TEST_GROUPS,
    _project_ledger_errors,
    validate_workspace,
)

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
    for command in ("status", "next", "validate"):
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


def test_project_ledger_rejects_a_stale_history_pointer(tmp_path: Path) -> None:
    source = (ROOT / "PROJECT_STATE.md").read_text(encoding="utf-8")
    corrupted, replacements = re.subn(
        r"^last_history_id: HIST-\d{4}-\d{2}-\d{2}-\d{3}$",
        "last_history_id: HIST-2026-07-21-999",
        source,
        count=1,
        flags=re.MULTILINE,
    )
    assert replacements == 1
    ledger = tmp_path / "PROJECT_STATE.md"
    ledger.write_text(corrupted, encoding="utf-8")

    errors = _project_ledger_errors(ledger)

    assert "PROJECT_STATE.md: last_history_id must match the final history entry" in errors


def test_low_memory_integration_shards_cover_every_integration_file_once() -> None:
    shard_names = ("integration-core", "integration-eval", "integration-ops")
    configured = [item for name in shard_names for item in TEST_GROUPS[name]]
    discovered = sorted(
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "tests" / "integration").glob("test_*.py")
    )

    assert sorted(configured) == discovered
    assert len(configured) == len(set(configured))
    assert DEFAULT_TEST_SEQUENCE == ("unit", *shard_names, "contract")
