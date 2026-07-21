"""Durable local notification outbox used by offline and future delivery adapters."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from axcalib.dossier import atomic_write_text, exclusive_file_lock
from axcalib.notifications.base import NotificationEvent, NotificationPort


class DurableNotificationOutbox:
    """Record notification attempts before delegating delivery.

    A failed adapter leaves a retryable record while the domain transition still
    fails closed. Reusing the same event is idempotent after successful delivery.
    """

    def __init__(self, root: Path, downstream: NotificationPort) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.downstream = downstream

    def send(self, event: NotificationEvent) -> None:
        """Persist, deliver, and durably record the delivery status."""

        path = self.path_for(event)
        with exclusive_file_lock(path):
            current = self._load(path)
            if current and current.get("delivery_status") == "recorded":
                return
            attempts = int(current.get("attempts", 0)) + 1 if current else 1
            entry = self._entry(event, attempts=attempts, status="pending")
            self._write(path, entry)
            try:
                self.downstream.send(event)
            except Exception as error:
                failed = {
                    **entry,
                    "delivery_status": "failed",
                    # Provider exception messages may echo credentials or source text.
                    "last_error": type(error).__name__,
                    "updated_at": datetime.now(UTC).isoformat(),
                }
                self._write(path, failed)
                raise
            delivered = {
                **entry,
                "delivery_status": "recorded",
                "last_error": None,
                "updated_at": datetime.now(UTC).isoformat(),
            }
            self._write(path, delivered)

    def path_for(self, event: NotificationEvent) -> Path:
        """Return the deterministic idempotency path for an event."""

        identity = "|".join(
            (
                event.event_type,
                event.project_id,
                event.stage,
                event.required_role,
                str(event.revision or ""),
                event.report_ref or "",
            )
        )
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        return self.root / f"notification-{digest[:24]}.json"

    def entries(self) -> tuple[dict[str, Any], ...]:
        """Load all outbox records in deterministic order."""

        return tuple(self._load(path) or {} for path in sorted(self.root.glob("*.json")))

    def retry_failed(self) -> int:
        """Retry failed records and return the number delivered in this pass."""

        delivered = 0
        for path in sorted(self.root.glob("*.json")):
            entry = self._load(path)
            if not entry or entry.get("delivery_status") != "failed":
                continue
            self.send(
                NotificationEvent(
                    event_type=str(entry["event_type"]),
                    project_id=str(entry["project_id"]),
                    stage=str(entry["stage"]),
                    required_role=str(entry["required_role"]),
                    revision=(
                        int(entry["revision"])
                        if entry.get("revision") is not None
                        else None
                    ),
                    report_ref=(
                        str(entry["report_ref"])
                        if entry.get("report_ref") is not None
                        else None
                    ),
                )
            )
            delivered += 1
        return delivered

    @staticmethod
    def _entry(
        event: NotificationEvent,
        *,
        attempts: int,
        status: str,
    ) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        return {
            "schema_version": "axcalib.notification-outbox/v1alpha1",
            "event_type": event.event_type,
            "project_id": event.project_id,
            "stage": event.stage,
            "required_role": event.required_role,
            "revision": event.revision,
            "report_ref": event.report_ref,
            "attempts": attempts,
            "delivery_status": status,
            "last_error": None,
            "updated_at": now,
        }

    @staticmethod
    def _load(path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError(f"invalid notification outbox record: {path}")
        return value

    @staticmethod
    def _write(path: Path, value: dict[str, Any]) -> None:
        content = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        atomic_write_text(path, content)


__all__ = ["DurableNotificationOutbox"]
