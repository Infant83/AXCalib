from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from axcalib.runtime import LocalWorkspaceMaintenance


def _age(path: Path, seconds: float) -> None:
    timestamp = datetime.now(UTC).timestamp() - seconds
    os.utime(path, (timestamp, timestamp))


def _journal(path: Path, status: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"status": status}) + "\n", encoding="utf-8")


def test_maintenance_reports_then_quarantines_without_deletion(tmp_path: Path) -> None:
    stale_lock = tmp_path / "dossiers" / ".case.yaml.lock"
    stale_lock.parent.mkdir(parents=True)
    stale_lock.write_text("pid=99999999\n", encoding="utf-8")
    active_lock = tmp_path / "dossiers" / ".active.yaml.lock"
    active_lock.write_text(f"pid={os.getpid()}\n", encoding="utf-8")
    orphan = tmp_path / "dossiers" / ".case.yaml.orphan.tmp"
    orphan.write_text("orphan", encoding="utf-8")
    committed = tmp_path / "transactions" / "transaction-committed.jsonl"
    blocked = tmp_path / "transactions" / "transaction-blocked.jsonl"
    _journal(committed, "committed")
    _journal(blocked, "blocked")
    for path in (stale_lock, active_lock, orphan, committed, blocked):
        _age(path, 10_000)

    service = LocalWorkspaceMaintenance(tmp_path)
    report = service.run(
        apply=False,
        stale_after_seconds=60,
        retention_seconds=60,
        now=datetime.now(UTC) + timedelta(seconds=1),
    )
    assert all(path.exists() for path in (stale_lock, active_lock, orphan, committed, blocked))
    decisions = {item.relative_path: item.decision for item in report.actions}
    assert decisions[stale_lock.relative_to(tmp_path).as_posix()] == "candidate_only"
    assert decisions[active_lock.relative_to(tmp_path).as_posix()] == "active_owner"
    assert decisions[blocked.relative_to(tmp_path).as_posix()] == "manual_review_required"

    applied = service.run(
        apply=True,
        stale_after_seconds=60,
        retention_seconds=60,
        now=datetime.now(UTC) + timedelta(seconds=1),
    )
    applied_decisions = {item.relative_path: item.decision for item in applied.actions}
    assert applied_decisions[stale_lock.relative_to(tmp_path).as_posix()] == "quarantined"
    assert applied_decisions[orphan.relative_to(tmp_path).as_posix()] == "quarantined"
    assert applied_decisions[committed.relative_to(tmp_path).as_posix()] == "archived"
    assert applied_decisions[blocked.relative_to(tmp_path).as_posix()] == (
        "manual_review_required"
    )
    assert not stale_lock.exists()
    assert not orphan.exists()
    assert not committed.exists()
    assert active_lock.exists()
    assert blocked.exists()
    assert Path(applied.manifest_uri).is_file()
    assert (tmp_path / "audit" / "maintenance-events.jsonl").is_file()
