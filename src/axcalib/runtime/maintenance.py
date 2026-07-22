"""Conservative local stale-lock, orphan, and journal retention maintenance."""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from axcalib.audit import AuditLog
from axcalib.dossier import atomic_write_text
from axcalib.schemas import AuditEvent

PID_PATTERN = re.compile(r"^pid=(\d+)$", re.MULTILINE)


class MaintenanceAction(BaseModel):
    """One explainable maintenance decision without file content."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["stale_lock", "orphan_temp", "transaction_journal"]
    relative_path: str
    age_seconds: float = Field(ge=0.0)
    decision: Literal[
        "quarantined",
        "archived",
        "active_owner",
        "manual_review_required",
        "candidate_only",
    ]
    reason_code: str
    destination: str | None = None
    source_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")


class MaintenanceResult(BaseModel):
    """Immutable manifest for one report-only or apply maintenance run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "axcalib.local-maintenance/v1alpha1"
    run_id: str
    mode: Literal["report", "apply"]
    root: str
    stale_after_seconds: float
    retention_seconds: float
    actions: tuple[MaintenanceAction, ...]
    manifest_uri: str


class LocalWorkspaceMaintenance:
    """Quarantine stale local artifacts without destructive deletion."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.audit = AuditLog(self.root / "audit" / "maintenance-events.jsonl")

    def run(
        self,
        *,
        apply: bool = False,
        stale_after_seconds: float = 3600.0,
        retention_seconds: float = 7 * 24 * 3600.0,
        quarantine_blocked_journals: bool = False,
        now: datetime | None = None,
    ) -> MaintenanceResult:
        """Scan or safely move stale artifacts inside the same workspace."""

        if stale_after_seconds <= 0 or retention_seconds <= 0:
            raise ValueError("maintenance age thresholds must be positive")
        current = now or datetime.now(UTC)
        run_id = f"maintenance-{uuid.uuid4()}"
        actions: list[MaintenanceAction] = []
        for path in sorted(self.root.rglob("*")):
            if not path.is_file() or self._excluded(path):
                continue
            age = max(0.0, current.timestamp() - path.stat().st_mtime)
            if path.name.endswith(".lock") and age >= stale_after_seconds:
                actions.append(self._handle_lock(path, age, apply, run_id))
            elif path.name.endswith(".tmp") and age >= stale_after_seconds:
                actions.append(
                    self._move_action(
                        path,
                        age,
                        kind="orphan_temp",
                        apply=apply,
                        run_id=run_id,
                        target_root="quarantine",
                        reason_code="orphan_temp_exceeded_stale_threshold",
                    )
                )
            elif (
                path.parent.name == "transactions"
                and path.name.startswith("transaction-")
                and path.suffix == ".jsonl"
                and age >= retention_seconds
            ):
                actions.append(
                    self._handle_journal(
                        path,
                        age,
                        apply,
                        run_id,
                        quarantine_blocked_journals,
                    )
                )
        manifest_path = self.root / "maintenance" / f"{run_id}.json"
        result = MaintenanceResult(
            run_id=run_id,
            mode="apply" if apply else "report",
            root=str(self.root),
            stale_after_seconds=stale_after_seconds,
            retention_seconds=retention_seconds,
            actions=tuple(actions),
            manifest_uri=str(manifest_path),
        )
        atomic_write_text(
            manifest_path,
            json.dumps(
                result.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            ) + "\n",
        )
        self.audit.append_once(
            AuditEvent(
                event_id=f"evt-{run_id}",
                project_id="workspace",
                event_type="local_maintenance_completed",
                actor_id="operator:local-maintenance",
                actor_role="operator",
                dossier_revision=1,
                details={
                    "mode": result.mode,
                    "action_count": len(actions),
                    "manifest_sha256": self._sha256(manifest_path),
                },
            )
        )
        return result

    def _handle_lock(
        self,
        path: Path,
        age: float,
        apply: bool,
        run_id: str,
    ) -> MaintenanceAction:
        content = path.read_text(encoding="utf-8", errors="replace")
        match = PID_PATTERN.search(content)
        pid = int(match.group(1)) if match else None
        if pid is not None and self._pid_alive(pid):
            return self._action(
                path,
                age,
                kind="stale_lock",
                decision="active_owner",
                reason_code="lock_owner_process_is_alive",
            )
        return self._move_action(
            path,
            age,
            kind="stale_lock",
            apply=apply,
            run_id=run_id,
            target_root="quarantine",
            reason_code=(
                "lock_owner_process_not_alive" if pid is not None else "invalid_lock_owner"
            ),
        )

    def _handle_journal(
        self,
        path: Path,
        age: float,
        apply: bool,
        run_id: str,
        quarantine_blocked: bool,
    ) -> MaintenanceAction:
        status = self._journal_status(path)
        if status == "committed":
            return self._move_action(
                path,
                age,
                kind="transaction_journal",
                apply=apply,
                run_id=run_id,
                target_root="archive",
                reason_code="committed_journal_exceeded_retention",
            )
        if quarantine_blocked and status in {"blocked", "reconcile_required"}:
            return self._move_action(
                path,
                age,
                kind="transaction_journal",
                apply=apply,
                run_id=run_id,
                target_root="quarantine",
                reason_code=f"{status}_journal_explicitly_quarantined",
            )
        return self._action(
            path,
            age,
            kind="transaction_journal",
            decision="manual_review_required",
            reason_code=f"journal_status_{status}_requires_reconciliation",
        )

    def _move_action(
        self,
        path: Path,
        age: float,
        *,
        kind: Literal["stale_lock", "orphan_temp", "transaction_journal"],
        apply: bool,
        run_id: str,
        target_root: Literal["archive", "quarantine"],
        reason_code: str,
    ) -> MaintenanceAction:
        if not apply:
            return self._action(
                path,
                age,
                kind=kind,
                decision="candidate_only",
                reason_code=reason_code,
            )
        relative = path.relative_to(self.root)
        destination = self.root / target_root / run_id / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        digest = self._sha256(path)
        os.replace(path, destination)
        return MaintenanceAction(
            kind=kind,
            relative_path=relative.as_posix(),
            age_seconds=age,
            decision="archived" if target_root == "archive" else "quarantined",
            reason_code=reason_code,
            destination=destination.relative_to(self.root).as_posix(),
            source_sha256=digest,
        )

    def _action(
        self,
        path: Path,
        age: float,
        *,
        kind: Literal["stale_lock", "orphan_temp", "transaction_journal"],
        decision: Literal[
            "active_owner",
            "manual_review_required",
            "candidate_only",
        ],
        reason_code: str,
    ) -> MaintenanceAction:
        return MaintenanceAction(
            kind=kind,
            relative_path=path.relative_to(self.root).as_posix(),
            age_seconds=age,
            decision=decision,
            reason_code=reason_code,
            source_sha256=self._sha256(path),
        )

    def _excluded(self, path: Path) -> bool:
        relative = path.relative_to(self.root)
        return bool({"archive", "quarantine", "maintenance"}.intersection(relative.parts))

    @staticmethod
    def _journal_status(path: Path) -> str:
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line]
        if not lines:
            return "invalid"
        try:
            value = json.loads(lines[-1])
        except json.JSONDecodeError:
            return "invalid"
        return str(value.get("status", "invalid")) if isinstance(value, dict) else "invalid"

    @staticmethod
    def _pid_alive(pid: int) -> bool:
        if pid <= 0:
            return False
        if os.name == "nt":
            # Windows os.kill(pid, 0) is not a POSIX-style existence probe and can
            # terminate the target process. Query the process handle without mutation.
            import ctypes
            from ctypes import wintypes

            process_query_limited_information = 0x1000
            still_active = 259
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            kernel32.OpenProcess.restype = wintypes.HANDLE
            kernel32.GetExitCodeProcess.argtypes = [
                wintypes.HANDLE,
                ctypes.POINTER(wintypes.DWORD),
            ]
            kernel32.GetExitCodeProcess.restype = wintypes.BOOL
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel32.CloseHandle.restype = wintypes.BOOL
            handle = kernel32.OpenProcess(
                process_query_limited_information,
                False,
                pid,
            )
            if not handle:
                # Access denied means a process exists but is not queryable.
                return ctypes.get_last_error() == 5
            try:
                exit_code = wintypes.DWORD()
                if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                    return False
                return exit_code.value == still_active
            finally:
                kernel32.CloseHandle(handle)
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError:
            return False
        return True

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()


__all__ = [
    "LocalWorkspaceMaintenance",
    "MaintenanceAction",
    "MaintenanceResult",
]
