"""Notification port used before a workflow enters administrator review."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True, slots=True)
class NotificationEvent:
    """Minimal, non-secret administrator approval notification."""

    event_type: str
    project_id: str
    stage: str
    required_role: str = "administrator"


class NotificationPort(Protocol):
    """A GitLab, email, outbox, or recording notification adapter."""

    def send(self, event: NotificationEvent) -> None:
        """Persist or deliver an approval request, raising on failure."""


@dataclass(slots=True)
class RecordingNotifier:
    """Offline adapter that records events without external communication."""

    events: list[NotificationEvent] = field(default_factory=list)

    def send(self, event: NotificationEvent) -> None:
        self.events.append(event)

