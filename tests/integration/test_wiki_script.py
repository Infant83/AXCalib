from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from harness.wiki import WikiPublishError, publish_wiki

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "wiki" / "sync_wiki.py"


def test_wiki_script_validates_and_exports_both_targets(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    validated = subprocess.run(
        [sys.executable, str(SCRIPT), "validate"],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert validated.returncode == 0, validated.stdout + validated.stderr
    for target, sidebar in (("github", "_Sidebar.md"), ("gitlab", "_sidebar.md")):
        output = tmp_path / target
        exported = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "export",
                "--target",
                target,
                "--output",
                str(output),
            ],
            cwd=ROOT,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        assert exported.returncode == 0, exported.stdout + exported.stderr
        assert (output / "Home.md").is_file()
        assert (output / "Development-Ledger.md").is_file()
        assert (output / sidebar).is_file()


def test_publish_to_local_bare_wiki_is_idempotent(tmp_path: Path) -> None:
    remote = tmp_path / "wiki.git"
    initialized = subprocess.run(
        ["git", "init", "--bare", str(remote)],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    checkout = tmp_path / "checkout"

    dry_run = publish_wiki(ROOT, "gitlab", str(remote), checkout)
    first = publish_wiki(ROOT, "gitlab", str(remote), checkout, push=True)
    second = publish_wiki(ROOT, "gitlab", str(remote), checkout, push=True)

    assert dry_run.changed is True
    assert dry_run.committed is False
    assert dry_run.pushed is False
    assert first.changed is True
    assert first.committed is True
    assert first.pushed is True
    assert second.changed is False
    assert second.committed is False
    assert second.pushed is False
    assert (checkout / "Home.md").is_file()
    assert (checkout / "_sidebar.md").is_file()


def test_resumed_dry_run_rejects_foreign_changes(tmp_path: Path) -> None:
    remote = tmp_path / "wiki.git"
    initialized = subprocess.run(
        ["git", "init", "--bare", str(remote)],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    checkout = tmp_path / "checkout"
    publish_wiki(ROOT, "github", str(remote), checkout)
    (checkout / "Team-Notes.md").write_text("do not commit", encoding="utf-8")

    with pytest.raises(WikiPublishError, match="outside the AXCalib managed manifest"):
        publish_wiki(ROOT, "github", str(remote), checkout, push=True)
