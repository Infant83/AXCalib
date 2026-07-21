"""Append-only local project transaction journal and reconciliation service."""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from axcalib.audit import AuditLog
from axcalib.dossier import (
    DossierRepository,
    canonical_json_bytes,
    exclusive_file_lock,
)
from axcalib.schemas import AuditEvent, ProjectDossier

TRANSACTION_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
SHA256_PATTERN = r"^[a-f0-9]{64}$"


class TransactionError(RuntimeError):
    """Base transaction journal error."""


class TransactionConflictError(TransactionError):
    """Raised when a transaction identity or project revision conflicts."""


class TransactionIntegrityError(TransactionError):
    """Raised when the append-only hash chain is invalid."""


class TransactionBlockedError(TransactionError):
    """A safe reconciliation precondition was not satisfied."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


class TransactionStatus(StrEnum):
    """Journal states; committed is the only successful terminal state."""

    PREPARED = "prepared"
    APPLYING = "applying"
    RECONCILE_REQUIRED = "reconcile_required"
    RECONCILING = "reconciling"
    BLOCKED = "blocked"
    COMMITTED = "committed"


class TransactionArtifactRequirement(BaseModel):
    """Hash-bound internal artifact required before applying a dossier state."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["report_json", "report_markdown", "notification_outbox"]
    relative_path: str = Field(min_length=1, max_length=1000)
    sha256: str = Field(pattern=SHA256_PATTERN)
    expected_report_id: str | None = None
    expected_delivery_status: Literal["recorded"] | None = None

    @field_validator("relative_path")
    @classmethod
    def validate_relative_path(cls, value: str) -> str:
        normalized = value.replace("\\", "/")
        candidate = PurePosixPath(normalized)
        if candidate.is_absolute() or ".." in candidate.parts or normalized.startswith("/"):
            raise ValueError("transaction artifact path must stay inside the workspace")
        return candidate.as_posix()


class ProjectTransactionPlan(BaseModel):
    """Immutable plan stored in the first journal event."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["axcalib.project-transaction/v1alpha1"] = (
        "axcalib.project-transaction/v1alpha1"
    )
    transaction_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
    operation: Literal["create", "update"]
    project_id: str
    command: str = Field(min_length=1, max_length=200)
    idempotency_key: str = Field(min_length=1, max_length=128)
    base_revision: int = Field(ge=0)
    target_revision: int = Field(ge=1)
    base_dossier_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    candidate_dossier: ProjectDossier
    audit_event: AuditEvent
    required_artifacts: tuple[TransactionArtifactRequirement, ...] = ()

    @model_validator(mode="after")
    def validate_plan_integrity(self) -> ProjectTransactionPlan:
        candidate = self.candidate_dossier
        event = self.audit_event
        if candidate.project_id != self.project_id or event.project_id != self.project_id:
            raise ValueError("transaction project IDs must match")
        if event.event_id not in candidate.audit_event_ids:
            raise ValueError("candidate dossier must reference the transaction audit event")
        if event.dossier_revision != self.target_revision:
            raise ValueError("audit event revision must equal transaction target revision")
        if self.operation == "create":
            if (
                self.base_revision != 0
                or self.target_revision != 1
                or candidate.revision != 1
                or self.base_dossier_sha256 is not None
            ):
                raise ValueError("create transaction revisions are invalid")
        elif (
            self.target_revision != self.base_revision + 1
            or candidate.revision != self.base_revision
            or self.base_dossier_sha256 is None
        ):
            raise ValueError("update transaction revisions are invalid")
        return self


class TransactionJournalEvent(BaseModel):
    """One immutable hash-chained journal line."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["axcalib.transaction-journal-event/v1alpha1"] = (
        "axcalib.transaction-journal-event/v1alpha1"
    )
    transaction_id: str
    sequence: int = Field(ge=1)
    status: TransactionStatus
    occurred_at: datetime
    previous_event_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    reason_code: str | None = Field(default=None, max_length=200)
    plan: ProjectTransactionPlan | None = None
    event_sha256: str = Field(pattern=SHA256_PATTERN)


class TransactionJournalRecord(BaseModel):
    """Validated view of one transaction journal file."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    plan: ProjectTransactionPlan
    events: tuple[TransactionJournalEvent, ...]

    @property
    def latest_status(self) -> TransactionStatus:
        return self.events[-1].status


class TransactionReconciliationResult(BaseModel):
    """Secret-free result of one idempotent reconciliation pass."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    transaction_id: str
    project_id: str
    status: Literal["committed", "already_committed", "blocked"]
    recovered_artifacts: tuple[str, ...] = ()
    reason_code: str | None = None


FailureInjector = Callable[[str], None]


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _dossier_sha256(dossier: ProjectDossier) -> str:
    return hashlib.sha256(
        canonical_json_bytes(dossier.model_dump(mode="json"))
    ).hexdigest()


def _target_semantic_sha256(dossier: ProjectDossier, target_revision: int) -> str:
    value = dossier.model_dump(mode="json")
    value["revision"] = target_revision
    value.pop("updated_at", None)
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


class TransactionJournal:
    """One append-only JSONL hash chain per project transaction."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def prepare(self, plan: ProjectTransactionPlan) -> TransactionJournalRecord:
        """Create the immutable plan or validate an identical retry."""

        path = self.path_for(plan.transaction_id)
        with exclusive_file_lock(path):
            if path.exists():
                record = self._read_unlocked(path)
                if record.plan != plan:
                    raise TransactionConflictError(
                        "transaction ID was reused for a different plan"
                    )
                return record
            return self._append_unlocked(
                path,
                transaction_id=plan.transaction_id,
                status=TransactionStatus.PREPARED,
                plan=plan,
            )

    def append_status(
        self,
        transaction_id: str,
        status: TransactionStatus,
        *,
        reason_code: str | None = None,
    ) -> TransactionJournalRecord:
        """Append a state event without rewriting earlier journal entries."""

        path = self.path_for(transaction_id)
        with exclusive_file_lock(path):
            record = self._read_unlocked(path)
            if record.latest_status is TransactionStatus.COMMITTED:
                return record
            return self._append_unlocked(
                path,
                transaction_id=transaction_id,
                status=status,
                reason_code=reason_code,
            )

    def load(self, transaction_id: str) -> TransactionJournalRecord:
        """Load and verify one complete hash chain."""

        path = self.path_for(transaction_id)
        with exclusive_file_lock(path):
            return self._read_unlocked(path)

    def records(self) -> tuple[TransactionJournalRecord, ...]:
        """Load all transaction records in deterministic order."""

        records: list[TransactionJournalRecord] = []
        for path in sorted(self.root.glob("transaction-*.jsonl")):
            with exclusive_file_lock(path):
                records.append(self._read_unlocked(path))
        return tuple(records)

    def path_for(self, transaction_id: str) -> Path:
        if TRANSACTION_ID_PATTERN.fullmatch(transaction_id) is None:
            raise TransactionError("invalid transaction_id")
        digest = hashlib.sha256(transaction_id.encode("utf-8")).hexdigest()
        return self.root / f"transaction-{digest[:24]}.jsonl"

    def _append_unlocked(
        self,
        path: Path,
        *,
        transaction_id: str,
        status: TransactionStatus,
        reason_code: str | None = None,
        plan: ProjectTransactionPlan | None = None,
    ) -> TransactionJournalRecord:
        existing = self._read_unlocked(path) if path.exists() else None
        sequence = len(existing.events) + 1 if existing else 1
        previous = existing.events[-1].event_sha256 if existing else None
        payload: dict[str, object] = {
            "schema_version": "axcalib.transaction-journal-event/v1alpha1",
            "transaction_id": transaction_id,
            "sequence": sequence,
            "status": status.value,
            "occurred_at": datetime.now(UTC).isoformat(),
            "previous_event_sha256": previous,
            "reason_code": reason_code,
            "plan": plan.model_dump(mode="json") if plan else None,
        }
        event_sha256 = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
        line = json.dumps(
            {**payload, "event_sha256": event_sha256},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ) + "\n"
        with path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(line)
            stream.flush()
            os.fsync(stream.fileno())
        return self._read_unlocked(path)

    @staticmethod
    def _read_unlocked(path: Path) -> TransactionJournalRecord:
        if not path.exists():
            raise TransactionError("transaction journal does not exist")
        events: list[TransactionJournalEvent] = []
        previous: str | None = None
        plan: ProjectTransactionPlan | None = None
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            if not line.strip():
                raise TransactionIntegrityError("transaction journal contains an empty line")
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as error:
                raise TransactionIntegrityError(
                    f"invalid transaction journal JSON at line {line_number}"
                ) from error
            if not isinstance(raw, dict):
                raise TransactionIntegrityError("transaction journal line must be an object")
            claimed_hash = raw.get("event_sha256")
            payload = {key: value for key, value in raw.items() if key != "event_sha256"}
            actual_hash = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
            if claimed_hash != actual_hash:
                raise TransactionIntegrityError("transaction journal hash mismatch")
            event = TransactionJournalEvent.model_validate(raw)
            if event.sequence != line_number or event.previous_event_sha256 != previous:
                raise TransactionIntegrityError("transaction journal sequence is broken")
            if line_number == 1:
                if event.status is not TransactionStatus.PREPARED or event.plan is None:
                    raise TransactionIntegrityError(
                        "first journal event must contain a prepared plan"
                    )
                plan = event.plan
            elif event.plan is not None:
                raise TransactionIntegrityError(
                    "transaction plan may appear only in the first event"
                )
            if plan is not None and event.transaction_id != plan.transaction_id:
                raise TransactionIntegrityError("transaction journal identity changed")
            events.append(event)
            previous = event.event_sha256
        if not events or plan is None:
            raise TransactionIntegrityError("transaction journal is empty")
        return TransactionJournalRecord(plan=plan, events=tuple(events))


class ProjectTransactionCoordinator:
    """Apply and reconcile dossier/audit changes behind hash-bound prerequisites."""

    def __init__(
        self,
        workspace: Path,
        *,
        dossiers: DossierRepository,
        audit: AuditLog,
        failure_injector: FailureInjector | None = None,
    ) -> None:
        self.workspace = workspace.resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.dossiers = dossiers
        self.audit = audit
        self.journal = TransactionJournal(self.workspace / "transactions")
        self.failure_injector = failure_injector

    def require_file(
        self,
        path: Path,
        *,
        kind: Literal["report_json", "report_markdown", "notification_outbox"],
        expected_report_id: str | None = None,
        expected_delivery_status: Literal["recorded"] | None = None,
    ) -> TransactionArtifactRequirement:
        """Bind an existing internal artifact to one transaction plan."""

        resolved = path.resolve()
        try:
            relative = resolved.relative_to(self.workspace).as_posix()
        except ValueError as error:
            raise TransactionError("transaction artifact is outside the workspace") from error
        if not resolved.is_file():
            raise TransactionBlockedError(f"missing_{kind}")
        return TransactionArtifactRequirement(
            kind=kind,
            relative_path=relative,
            sha256=_file_sha256(resolved),
            expected_report_id=expected_report_id,
            expected_delivery_status=expected_delivery_status,
        )

    def execute_create(
        self,
        dossier: ProjectDossier,
        audit_event: AuditEvent,
        *,
        command: str,
        idempotency_key: str,
        required_artifacts: tuple[TransactionArtifactRequirement, ...] = (),
    ) -> ProjectDossier:
        """Create a dossier and its first audit event as a recoverable command."""

        plan = ProjectTransactionPlan(
            transaction_id=f"txn-{audit_event.event_id}",
            operation="create",
            project_id=dossier.project_id,
            command=command,
            idempotency_key=idempotency_key,
            base_revision=0,
            target_revision=1,
            candidate_dossier=dossier,
            audit_event=audit_event,
            required_artifacts=required_artifacts,
        )
        return self._execute(plan)

    def execute_update(
        self,
        dossier: ProjectDossier,
        *,
        expected_revision: int,
        audit_event: AuditEvent,
        command: str,
        idempotency_key: str,
        required_artifacts: tuple[TransactionArtifactRequirement, ...] = (),
    ) -> ProjectDossier:
        """Apply one revision and its audit event through a durable plan."""

        base = self.dossiers.load(dossier.project_id)
        if base.revision != expected_revision:
            raise TransactionConflictError(
                f"expected revision {expected_revision}; current revision is {base.revision}"
            )
        plan = ProjectTransactionPlan(
            transaction_id=f"txn-{audit_event.event_id}",
            operation="update",
            project_id=dossier.project_id,
            command=command,
            idempotency_key=idempotency_key,
            base_revision=expected_revision,
            target_revision=expected_revision + 1,
            base_dossier_sha256=_dossier_sha256(base),
            candidate_dossier=dossier,
            audit_event=audit_event,
            required_artifacts=required_artifacts,
        )
        return self._execute(plan)

    def reconcile(self, transaction_id: str) -> TransactionReconciliationResult:
        """Idempotently finish one prepared transaction or report a safe block."""

        record = self.journal.load(transaction_id)
        plan = record.plan
        if record.latest_status is TransactionStatus.COMMITTED:
            return TransactionReconciliationResult(
                transaction_id=transaction_id,
                project_id=plan.project_id,
                status="already_committed",
            )
        self.journal.append_status(transaction_id, TransactionStatus.RECONCILING)
        recovered: list[str] = []
        try:
            self._verify_requirements(plan)
            _, dossier_changed = self._ensure_dossier(plan)
            if dossier_changed:
                recovered.append("dossier")
            if self.audit.append_once(plan.audit_event):
                recovered.append("audit")
        except (TransactionBlockedError, TransactionConflictError) as error:
            reason_code = (
                error.reason_code
                if isinstance(error, TransactionBlockedError)
                else "revision_conflict"
            )
            self.journal.append_status(
                transaction_id,
                TransactionStatus.BLOCKED,
                reason_code=reason_code,
            )
            return TransactionReconciliationResult(
                transaction_id=transaction_id,
                project_id=plan.project_id,
                status="blocked",
                reason_code=reason_code,
            )
        self.journal.append_status(transaction_id, TransactionStatus.COMMITTED)
        return TransactionReconciliationResult(
            transaction_id=transaction_id,
            project_id=plan.project_id,
            status="committed",
            recovered_artifacts=tuple(recovered),
        )

    def reconcile_all(self) -> tuple[TransactionReconciliationResult, ...]:
        """Reconcile every journal safely; committed items remain no-ops."""

        return tuple(
            self.reconcile(record.plan.transaction_id)
            for record in self.journal.records()
        )

    def _execute(self, plan: ProjectTransactionPlan) -> ProjectDossier:
        record = self.journal.prepare(plan)
        if record.latest_status is TransactionStatus.COMMITTED:
            return self.dossiers.load(plan.project_id)
        self.journal.append_status(plan.transaction_id, TransactionStatus.APPLYING)
        try:
            self._inject("after_prepare")
            self._verify_requirements(plan)
            dossier, _ = self._ensure_dossier(plan)
            self._inject("after_dossier")
            self.audit.append_once(plan.audit_event)
            self._inject("after_audit")
        except Exception as error:
            try:
                self.journal.append_status(
                    plan.transaction_id,
                    TransactionStatus.RECONCILE_REQUIRED,
                    reason_code=type(error).__name__,
                )
            except Exception:
                pass
            raise
        self.journal.append_status(plan.transaction_id, TransactionStatus.COMMITTED)
        return dossier

    def _ensure_dossier(self, plan: ProjectTransactionPlan) -> tuple[ProjectDossier, bool]:
        path = self.dossiers.path_for(plan.project_id)
        if plan.operation == "create":
            if not path.exists():
                self.dossiers.create(plan.candidate_dossier)
                return plan.candidate_dossier, True
            current = self.dossiers.load(plan.project_id)
            self._verify_target(current, plan)
            return current, False

        current = self.dossiers.load(plan.project_id)
        if current.revision == plan.base_revision:
            if _dossier_sha256(current) != plan.base_dossier_sha256:
                raise TransactionBlockedError("base_dossier_hash_mismatch")
            saved = self.dossiers.save(
                plan.candidate_dossier,
                expected_revision=plan.base_revision,
            )
            self._verify_target(saved, plan)
            return saved, True
        if current.revision >= plan.target_revision:
            if plan.audit_event.event_id not in current.audit_event_ids:
                raise TransactionBlockedError("target_revision_missing_event")
            if current.revision == plan.target_revision:
                self._verify_target(current, plan)
            return current, False
        raise TransactionBlockedError("dossier_revision_conflict")

    @staticmethod
    def _verify_target(dossier: ProjectDossier, plan: ProjectTransactionPlan) -> None:
        if dossier.revision != plan.target_revision:
            raise TransactionBlockedError("dossier_target_revision_mismatch")
        if plan.audit_event.event_id not in dossier.audit_event_ids:
            raise TransactionBlockedError("dossier_target_missing_event")
        expected_hash = _target_semantic_sha256(
            plan.candidate_dossier,
            plan.target_revision,
        )
        actual_hash = _target_semantic_sha256(dossier, dossier.revision)
        if actual_hash != expected_hash:
            raise TransactionBlockedError("dossier_target_hash_mismatch")

    def _verify_requirements(self, plan: ProjectTransactionPlan) -> None:
        for requirement in plan.required_artifacts:
            path = (self.workspace / requirement.relative_path).resolve()
            try:
                path.relative_to(self.workspace)
            except ValueError as error:
                raise TransactionBlockedError("artifact_path_escape") from error
            if not path.is_file():
                raise TransactionBlockedError(f"missing_{requirement.kind}")
            if _file_sha256(path) != requirement.sha256:
                raise TransactionBlockedError(f"changed_{requirement.kind}")
            if requirement.expected_report_id or requirement.expected_delivery_status:
                try:
                    value = json.loads(path.read_text(encoding="utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as error:
                    raise TransactionBlockedError(
                        f"invalid_{requirement.kind}"
                    ) from error
                if not isinstance(value, dict):
                    raise TransactionBlockedError(f"invalid_{requirement.kind}")
                if (
                    requirement.expected_report_id is not None
                    and value.get("report_id") != requirement.expected_report_id
                ):
                    raise TransactionBlockedError("report_id_mismatch")
                if (
                    requirement.expected_delivery_status is not None
                    and value.get("delivery_status")
                    != requirement.expected_delivery_status
                ):
                    raise TransactionBlockedError("notification_not_recorded")

    def _inject(self, boundary: str) -> None:
        if self.failure_injector is not None:
            self.failure_injector(boundary)


__all__ = [
    "FailureInjector",
    "ProjectTransactionCoordinator",
    "ProjectTransactionPlan",
    "TransactionArtifactRequirement",
    "TransactionBlockedError",
    "TransactionConflictError",
    "TransactionError",
    "TransactionIntegrityError",
    "TransactionJournal",
    "TransactionJournalEvent",
    "TransactionJournalRecord",
    "TransactionReconciliationResult",
    "TransactionStatus",
]
