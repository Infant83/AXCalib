"""Recoverable local transactions for education enrollment and audit files."""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from axcalib.audit import AuditLog
from axcalib.dossier import canonical_json_bytes, exclusive_file_lock
from axcalib.runtime.transactions import (
    TransactionArtifactRequirement,
    TransactionBlockedError,
    TransactionConflictError,
    TransactionError,
    TransactionIntegrityError,
    TransactionStatus,
)
from axcalib.schemas import EducationEnrollment, ProgramAuditEvent

TRANSACTION_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
SHA256_PATTERN = r"^[a-f0-9]{64}$"
FailureInjector = Callable[[str], None]


class EnrollmentRepositoryPort(Protocol):
    """Small repository boundary that avoids a runtime package cycle."""

    def path_for(self, enrollment_id: str) -> Path: ...

    def create(self, enrollment: EducationEnrollment) -> Path: ...

    def load(self, enrollment_id: str) -> EducationEnrollment: ...

    def save(
        self,
        enrollment: EducationEnrollment,
        *,
        expected_revision: int,
    ) -> EducationEnrollment: ...


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _enrollment_sha256(enrollment: EducationEnrollment) -> str:
    return hashlib.sha256(
        canonical_json_bytes(enrollment.model_dump(mode="json"))
    ).hexdigest()


def _target_semantic_sha256(
    enrollment: EducationEnrollment,
    target_revision: int,
) -> str:
    value = enrollment.model_dump(mode="json")
    value["revision"] = target_revision
    value.pop("updated_at", None)
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


class EnrollmentTransactionPlan(BaseModel):
    """Immutable enrollment/audit commit plan."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["axcalib.enrollment-transaction/v1alpha1"] = (
        "axcalib.enrollment-transaction/v1alpha1"
    )
    transaction_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
    operation: Literal["create", "update"]
    enrollment_id: str
    command: str = Field(min_length=1, max_length=200)
    idempotency_key: str = Field(min_length=1, max_length=128)
    base_revision: int = Field(ge=0)
    target_revision: int = Field(ge=1)
    base_enrollment_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    candidate_enrollment: EducationEnrollment
    audit_event: ProgramAuditEvent
    required_artifacts: tuple[TransactionArtifactRequirement, ...] = ()

    @model_validator(mode="after")
    def validate_plan(self) -> EnrollmentTransactionPlan:
        candidate = self.candidate_enrollment
        event = self.audit_event
        if candidate.enrollment_id != self.enrollment_id:
            raise ValueError("candidate enrollment ID does not match transaction")
        if event.enrollment_id != self.enrollment_id:
            raise ValueError("audit enrollment ID does not match transaction")
        if event.event_id not in candidate.audit_event_ids:
            raise ValueError("candidate enrollment must reference the audit event")
        if event.enrollment_revision != self.target_revision:
            raise ValueError("audit event revision must equal target revision")
        if self.operation == "create":
            if (
                self.base_revision != 0
                or self.target_revision != 1
                or candidate.revision != 1
                or self.base_enrollment_sha256 is not None
            ):
                raise ValueError("create enrollment transaction revisions are invalid")
        elif (
            self.target_revision != self.base_revision + 1
            or candidate.revision != self.base_revision
            or self.base_enrollment_sha256 is None
        ):
            raise ValueError("update enrollment transaction revisions are invalid")
        return self


class EnrollmentJournalEvent(BaseModel):
    """One immutable hash-chained enrollment transaction event."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["axcalib.enrollment-journal-event/v1alpha1"] = (
        "axcalib.enrollment-journal-event/v1alpha1"
    )
    transaction_id: str
    sequence: int = Field(ge=1)
    status: TransactionStatus
    occurred_at: datetime
    previous_event_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    reason_code: str | None = None
    plan: EnrollmentTransactionPlan | None = None
    event_sha256: str = Field(pattern=SHA256_PATTERN)


class EnrollmentJournalRecord(BaseModel):
    """Validated view of one enrollment transaction journal."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    plan: EnrollmentTransactionPlan
    events: tuple[EnrollmentJournalEvent, ...]

    @property
    def latest_status(self) -> TransactionStatus:
        return self.events[-1].status


class EnrollmentReconciliationResult(BaseModel):
    """Result of one idempotent enrollment reconciliation pass."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    transaction_id: str
    enrollment_id: str
    status: Literal["committed", "already_committed", "blocked"]
    recovered_artifacts: tuple[str, ...] = ()
    reason_code: str | None = None


class EnrollmentTransactionJournal:
    """Append-only JSONL hash chain for education transactions."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def prepare(self, plan: EnrollmentTransactionPlan) -> EnrollmentJournalRecord:
        path = self.path_for(plan.transaction_id)
        with exclusive_file_lock(path):
            if path.exists():
                record = self._read_unlocked(path)
                if record.plan != plan:
                    raise TransactionConflictError(
                        "enrollment transaction ID was reused for a different plan"
                    )
                return record
            return self._append_unlocked(
                path,
                plan.transaction_id,
                TransactionStatus.PREPARED,
                plan=plan,
            )

    def append_status(
        self,
        transaction_id: str,
        status: TransactionStatus,
        *,
        reason_code: str | None = None,
    ) -> EnrollmentJournalRecord:
        path = self.path_for(transaction_id)
        with exclusive_file_lock(path):
            record = self._read_unlocked(path)
            if record.latest_status is TransactionStatus.COMMITTED:
                return record
            return self._append_unlocked(
                path,
                transaction_id,
                status,
                reason_code=reason_code,
            )

    def load(self, transaction_id: str) -> EnrollmentJournalRecord:
        path = self.path_for(transaction_id)
        with exclusive_file_lock(path):
            return self._read_unlocked(path)

    def records(self) -> tuple[EnrollmentJournalRecord, ...]:
        values: list[EnrollmentJournalRecord] = []
        for path in sorted(self.root.glob("transaction-*.jsonl")):
            with exclusive_file_lock(path):
                values.append(self._read_unlocked(path))
        return tuple(values)

    def path_for(self, transaction_id: str) -> Path:
        if TRANSACTION_ID_PATTERN.fullmatch(transaction_id) is None:
            raise TransactionError("invalid enrollment transaction_id")
        digest = hashlib.sha256(transaction_id.encode("utf-8")).hexdigest()
        return self.root / f"transaction-{digest[:24]}.jsonl"

    def _append_unlocked(
        self,
        path: Path,
        transaction_id: str,
        status: TransactionStatus,
        *,
        reason_code: str | None = None,
        plan: EnrollmentTransactionPlan | None = None,
    ) -> EnrollmentJournalRecord:
        existing = self._read_unlocked(path) if path.exists() else None
        sequence = len(existing.events) + 1 if existing else 1
        previous = existing.events[-1].event_sha256 if existing else None
        payload: dict[str, object] = {
            "schema_version": "axcalib.enrollment-journal-event/v1alpha1",
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
    def _read_unlocked(path: Path) -> EnrollmentJournalRecord:
        if not path.exists():
            raise TransactionError("enrollment transaction journal does not exist")
        events: list[EnrollmentJournalEvent] = []
        previous: str | None = None
        plan: EnrollmentTransactionPlan | None = None
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            if not line.strip():
                raise TransactionIntegrityError("enrollment journal contains an empty line")
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as error:
                raise TransactionIntegrityError(
                    f"invalid enrollment journal JSON at line {line_number}"
                ) from error
            if not isinstance(raw, dict):
                raise TransactionIntegrityError("enrollment journal line must be an object")
            claimed_hash = raw.get("event_sha256")
            payload = {key: value for key, value in raw.items() if key != "event_sha256"}
            if claimed_hash != hashlib.sha256(canonical_json_bytes(payload)).hexdigest():
                raise TransactionIntegrityError("enrollment journal hash mismatch")
            event = EnrollmentJournalEvent.model_validate(raw)
            if event.sequence != line_number or event.previous_event_sha256 != previous:
                raise TransactionIntegrityError("enrollment journal sequence is broken")
            if line_number == 1:
                if event.status is not TransactionStatus.PREPARED or event.plan is None:
                    raise TransactionIntegrityError(
                        "first enrollment journal event must contain a prepared plan"
                    )
                plan = event.plan
            elif event.plan is not None:
                raise TransactionIntegrityError(
                    "enrollment plan may appear only in the first event"
                )
            if plan is not None and event.transaction_id != plan.transaction_id:
                raise TransactionIntegrityError("enrollment journal identity changed")
            events.append(event)
            previous = event.event_sha256
        if not events or plan is None:
            raise TransactionIntegrityError("enrollment transaction journal is empty")
        return EnrollmentJournalRecord(plan=plan, events=tuple(events))


class EnrollmentTransactionCoordinator:
    """Apply and reconcile enrollment/audit changes without resending notifications."""

    def __init__(
        self,
        workspace: Path,
        *,
        enrollments: EnrollmentRepositoryPort,
        audit: AuditLog,
        failure_injector: FailureInjector | None = None,
    ) -> None:
        self.workspace = workspace.resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.enrollments = enrollments
        self.audit = audit
        self.journal = EnrollmentTransactionJournal(self.workspace / "transactions")
        self.failure_injector = failure_injector

    def require_outbox(self, path: Path) -> TransactionArtifactRequirement:
        """Hash-bind one already recorded education approval request."""

        resolved = path.resolve()
        try:
            relative = resolved.relative_to(self.workspace.parent).as_posix()
        except ValueError as error:
            raise TransactionError("education outbox is outside the AXCalib workspace") from error
        if not resolved.is_file():
            raise TransactionBlockedError("missing_notification_outbox")
        return TransactionArtifactRequirement(
            kind="notification_outbox",
            relative_path=relative,
            sha256=_file_sha256(resolved),
            expected_delivery_status="recorded",
        )

    def execute_create(
        self,
        enrollment: EducationEnrollment,
        event: ProgramAuditEvent,
        *,
        command: str,
        idempotency_key: str,
    ) -> EducationEnrollment:
        plan = EnrollmentTransactionPlan(
            transaction_id=f"txn-edu-{event.event_id}",
            operation="create",
            enrollment_id=enrollment.enrollment_id,
            command=command,
            idempotency_key=idempotency_key,
            base_revision=0,
            target_revision=1,
            candidate_enrollment=enrollment,
            audit_event=event,
        )
        return self._execute(plan)

    def execute_update(
        self,
        enrollment: EducationEnrollment,
        *,
        expected_revision: int,
        event: ProgramAuditEvent,
        command: str,
        idempotency_key: str,
        required_artifacts: tuple[TransactionArtifactRequirement, ...] = (),
    ) -> EducationEnrollment:
        base = self.enrollments.load(enrollment.enrollment_id)
        if base.revision != expected_revision:
            raise TransactionConflictError(
                f"expected enrollment revision {expected_revision}; current is {base.revision}"
            )
        plan = EnrollmentTransactionPlan(
            transaction_id=f"txn-edu-{event.event_id}",
            operation="update",
            enrollment_id=enrollment.enrollment_id,
            command=command,
            idempotency_key=idempotency_key,
            base_revision=expected_revision,
            target_revision=expected_revision + 1,
            base_enrollment_sha256=_enrollment_sha256(base),
            candidate_enrollment=enrollment,
            audit_event=event,
            required_artifacts=required_artifacts,
        )
        return self._execute(plan)

    def reconcile(self, transaction_id: str) -> EnrollmentReconciliationResult:
        record = self.journal.load(transaction_id)
        plan = record.plan
        if record.latest_status is TransactionStatus.COMMITTED:
            return EnrollmentReconciliationResult(
                transaction_id=transaction_id,
                enrollment_id=plan.enrollment_id,
                status="already_committed",
            )
        self.journal.append_status(transaction_id, TransactionStatus.RECONCILING)
        recovered: list[str] = []
        try:
            self._verify_requirements(plan)
            _, changed = self._ensure_enrollment(plan)
            if changed:
                recovered.append("enrollment")
            if self.audit.append_once(plan.audit_event):
                recovered.append("audit")
        except (TransactionBlockedError, TransactionConflictError) as error:
            reason = (
                error.reason_code
                if isinstance(error, TransactionBlockedError)
                else "revision_conflict"
            )
            self.journal.append_status(
                transaction_id,
                TransactionStatus.BLOCKED,
                reason_code=reason,
            )
            return EnrollmentReconciliationResult(
                transaction_id=transaction_id,
                enrollment_id=plan.enrollment_id,
                status="blocked",
                reason_code=reason,
            )
        self.journal.append_status(transaction_id, TransactionStatus.COMMITTED)
        return EnrollmentReconciliationResult(
            transaction_id=transaction_id,
            enrollment_id=plan.enrollment_id,
            status="committed",
            recovered_artifacts=tuple(recovered),
        )

    def reconcile_all(self) -> tuple[EnrollmentReconciliationResult, ...]:
        return tuple(
            self.reconcile(record.plan.transaction_id)
            for record in self.journal.records()
        )

    def _execute(self, plan: EnrollmentTransactionPlan) -> EducationEnrollment:
        record = self.journal.prepare(plan)
        if record.latest_status is TransactionStatus.COMMITTED:
            return self.enrollments.load(plan.enrollment_id)
        self.journal.append_status(plan.transaction_id, TransactionStatus.APPLYING)
        try:
            self._inject("after_prepare")
            self._verify_requirements(plan)
            enrollment, _ = self._ensure_enrollment(plan)
            self._inject("after_enrollment")
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
        return enrollment

    def _ensure_enrollment(
        self,
        plan: EnrollmentTransactionPlan,
    ) -> tuple[EducationEnrollment, bool]:
        path = self.enrollments.path_for(plan.enrollment_id)
        if plan.operation == "create":
            if not path.exists():
                self.enrollments.create(plan.candidate_enrollment)
                return plan.candidate_enrollment, True
            current = self.enrollments.load(plan.enrollment_id)
            self._verify_target(current, plan)
            return current, False
        current = self.enrollments.load(plan.enrollment_id)
        if current.revision == plan.base_revision:
            if _enrollment_sha256(current) != plan.base_enrollment_sha256:
                raise TransactionBlockedError("base_enrollment_hash_mismatch")
            saved = self.enrollments.save(
                plan.candidate_enrollment,
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
        raise TransactionBlockedError("enrollment_revision_conflict")

    @staticmethod
    def _verify_target(
        enrollment: EducationEnrollment,
        plan: EnrollmentTransactionPlan,
    ) -> None:
        if enrollment.revision != plan.target_revision:
            raise TransactionBlockedError("enrollment_target_revision_mismatch")
        if plan.audit_event.event_id not in enrollment.audit_event_ids:
            raise TransactionBlockedError("enrollment_target_missing_event")
        expected = _target_semantic_sha256(
            plan.candidate_enrollment,
            plan.target_revision,
        )
        actual = _target_semantic_sha256(enrollment, enrollment.revision)
        if actual != expected:
            raise TransactionBlockedError("enrollment_target_hash_mismatch")

    def _verify_requirements(self, plan: EnrollmentTransactionPlan) -> None:
        root = self.workspace.parent
        for requirement in plan.required_artifacts:
            path = (root / requirement.relative_path).resolve()
            try:
                path.relative_to(root)
            except ValueError as error:
                raise TransactionBlockedError("artifact_path_escape") from error
            if not path.is_file():
                raise TransactionBlockedError(f"missing_{requirement.kind}")
            if _file_sha256(path) != requirement.sha256:
                raise TransactionBlockedError(f"changed_{requirement.kind}")
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise TransactionBlockedError(f"invalid_{requirement.kind}") from error
            if not isinstance(value, dict):
                raise TransactionBlockedError(f"invalid_{requirement.kind}")
            if value.get("delivery_status") != requirement.expected_delivery_status:
                raise TransactionBlockedError("notification_not_recorded")

    def _inject(self, boundary: str) -> None:
        if self.failure_injector is not None:
            self.failure_injector(boundary)


__all__ = [
    "EnrollmentJournalEvent",
    "EnrollmentJournalRecord",
    "EnrollmentReconciliationResult",
    "EnrollmentTransactionCoordinator",
    "EnrollmentTransactionJournal",
    "EnrollmentTransactionPlan",
]
