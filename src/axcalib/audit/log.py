"""Append-only local audit log for the offline workflow."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from axcalib.dossier import exclusive_file_lock
from axcalib.schemas import AuditEvent, ProgramAuditEvent


class AuditLogConflictError(RuntimeError):
    """Raised when one event ID is reused with different content."""


class AuditLog:
    """Append small, secret-free structured events to JSON Lines."""

    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: AuditEvent | ProgramAuditEvent) -> None:
        """Durably append one validated event."""

        self.append_once(event)

    def append_once(self, event: AuditEvent | ProgramAuditEvent) -> bool:
        """Append once by event ID and return whether a new line was written."""

        value = event.model_dump(mode="json")
        with exclusive_file_lock(self.path):
            for current in self._read_unlocked():
                if current.get("event_id") != event.event_id:
                    continue
                if current != value:
                    raise AuditLogConflictError(
                        f"audit event ID has different content: {event.event_id}"
                    )
                return False
            payload = json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ) + "\n"
            with self.path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
        return True

    def contains(self, event_id: str) -> bool:
        """Return whether a validated event ID already exists."""

        with exclusive_file_lock(self.path):
            return any(
                item.get("event_id") == event_id for item in self._read_unlocked()
            )

    def entries(self) -> tuple[dict[str, Any], ...]:
        """Return validated JSON objects in append order."""

        with exclusive_file_lock(self.path):
            return tuple(self._read_unlocked())

    def _read_unlocked(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        values: list[dict[str, Any]] = []
        for line_number, line in enumerate(
            self.path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"invalid audit event at line {line_number}")
            values.append(value)
        return values


__all__ = ["AuditLog", "AuditLogConflictError"]
