"""Atomic local dossier and immutable snapshot repositories."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from axcalib.dossier.migrations import (
    CURRENT_DOSSIER_SCHEMA,
    default_dossier_migrations,
)
from axcalib.schemas import ProjectDossier, SnapshotRef


class DossierError(RuntimeError):
    """Base local dossier error."""


class DossierAlreadyExistsError(DossierError):
    """Raised when a project is initialized twice."""


class DossierNotFoundError(DossierError):
    """Raised when a project dossier cannot be found."""


class RevisionConflictError(DossierError):
    """Raised on stale or concurrent writes."""


class FileLockTimeoutError(DossierError):
    """Raised when another process keeps a local repository lock."""


PROJECT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
ATOMIC_REPLACE_ATTEMPTS = 6
ATOMIC_REPLACE_INITIAL_BACKOFF_SECONDS = 0.02


def validate_project_id(project_id: str) -> str:
    """Validate a project identifier before using it in a filesystem path."""

    if PROJECT_ID_PATTERN.fullmatch(project_id) is None:
        raise DossierError("invalid project_id")
    return project_id


def atomic_write_text(path: Path, content: str) -> None:
    """Write text in the target directory and atomically replace the destination."""

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        text=True,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        _replace_with_bounded_retry(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _replace_with_bounded_retry(source: Path, target: Path) -> None:
    """Retry only transient Windows-style permission failures, then fail normally."""

    for attempt in range(ATOMIC_REPLACE_ATTEMPTS):
        try:
            os.replace(source, target)
            return
        except PermissionError:
            if attempt + 1 == ATOMIC_REPLACE_ATTEMPTS:
                raise
            time.sleep(ATOMIC_REPLACE_INITIAL_BACKOFF_SECONDS * (2**attempt))


@contextmanager
def exclusive_file_lock(
    target: Path,
    *,
    timeout_seconds: float = 10.0,
    poll_seconds: float = 0.05,
) -> Iterator[None]:
    """Hold a small cross-process lock beside ``target``.

    The lock guards the compare-and-swap read/write window. It contains only a
    process identifier and is removed when the operation completes.
    """

    lock_path = target.with_name(f".{target.name}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout_seconds
    descriptor: int | None = None
    while descriptor is None:
        try:
            descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as error:
            if time.monotonic() >= deadline:
                raise FileLockTimeoutError(f"timed out acquiring lock for {target.name}") from error
            time.sleep(poll_seconds)
    try:
        os.write(descriptor, f"pid={os.getpid()}\n".encode())
        os.fsync(descriptor)
        yield
    finally:
        os.close(descriptor)
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize a JSON-compatible value for stable hashing."""

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


class DossierRepository:
    """Filesystem repository for one editable YAML dossier per project."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._yaml = YAML(typ="safe")
        self._yaml.default_flow_style = False
        self._migrations = default_dossier_migrations()

    def path_for(self, project_id: str) -> Path:
        """Return the canonical dossier path."""

        safe_project_id = validate_project_id(project_id)
        return self.root / f"AXC-{safe_project_id}.axc.yaml"

    def create(self, dossier: ProjectDossier) -> Path:
        """Create a new dossier without overwriting an existing project."""

        path = self.path_for(dossier.project_id)
        with exclusive_file_lock(path):
            if path.exists():
                raise DossierAlreadyExistsError(
                    f"dossier already exists: {dossier.project_id}"
                )
            self._write(path, dossier)
        return path

    def load(self, project_id: str) -> ProjectDossier:
        """Load and validate one dossier."""

        path = self.path_for(project_id)
        if not path.exists():
            raise DossierNotFoundError(f"dossier not found: {project_id}")
        raw = self._yaml.load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise DossierError("dossier YAML root must be an object")
        schema_version = raw.get("schema_version")
        if schema_version == "axcalib.dossier/v1alpha1":
            raw = self._migrations.migrate(
                raw,
                from_version="axcalib.dossier/v1alpha1",
                to_version=CURRENT_DOSSIER_SCHEMA,
            )
        elif schema_version != CURRENT_DOSSIER_SCHEMA:
            raise DossierError(f"unsupported dossier schema version: {schema_version}")
        dossier = ProjectDossier.model_validate(raw)
        if dossier.project_id != project_id:
            raise DossierError("dossier content project_id does not match its repository path")
        return dossier

    def save(self, dossier: ProjectDossier, *, expected_revision: int) -> ProjectDossier:
        """Persist a mutation only when the current revision matches."""

        path = self.path_for(dossier.project_id)
        with exclusive_file_lock(path):
            current = self.load(dossier.project_id)
            if current.revision != expected_revision:
                raise RevisionConflictError(
                    f"expected revision {expected_revision}; current revision is {current.revision}"
                )
            updated = dossier.model_copy(
                update={"revision": expected_revision + 1, "updated_at": datetime.now(UTC)}
            )
            self._write(path, updated)
        return updated

    def _write(self, path: Path, dossier: ProjectDossier) -> None:
        data = dossier.model_dump(mode="json")
        buffer = StringIO()
        self._yaml.dump(data, buffer)
        atomic_write_text(path, buffer.getvalue())


class SnapshotRepository:
    """Content-addressed immutable JSON snapshots."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def freeze(self, dossier: ProjectDossier) -> SnapshotRef:
        """Freeze exactly the supplied revision and return its hash reference."""

        validate_project_id(dossier.project_id)
        data = dossier.model_dump(mode="json")
        payload = canonical_json_bytes(data)
        digest = hashlib.sha256(payload).hexdigest()
        snapshot_id = f"snap-{dossier.project_id}-{dossier.revision}-{digest[:12]}"
        path = self.root / f"{snapshot_id}.json"
        envelope = {
            "snapshot_id": snapshot_id,
            "dossier_revision": dossier.revision,
            "dossier_sha256": digest,
            "dossier": data,
        }
        content = json.dumps(
            envelope,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ) + "\n"
        if not path.exists():
            atomic_write_text(path, content)
        elif path.read_text(encoding="utf-8") != content:
            raise DossierError(f"immutable snapshot integrity failure: {snapshot_id}")
        return SnapshotRef(
            snapshot_id=snapshot_id,
            dossier_revision=dossier.revision,
            dossier_sha256=digest,
            uri=str(path),
        )
