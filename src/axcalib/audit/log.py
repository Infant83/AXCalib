"""Append-only local audit log for the offline workflow."""

from __future__ import annotations

import json
import os
from pathlib import Path

from axcalib.dossier import exclusive_file_lock
from axcalib.schemas import AuditEvent, ProgramAuditEvent


class AuditLog:
    """Append small, secret-free structured events to JSON Lines."""

    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: AuditEvent | ProgramAuditEvent) -> None:
        """Durably append one validated event."""

        payload = json.dumps(
            event.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ) + "\n"
        with exclusive_file_lock(self.path):
            with self.path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())


__all__ = ["AuditLog"]
