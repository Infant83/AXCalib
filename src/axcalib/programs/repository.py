"""Local repositories for versioned programs and learner enrollments."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path

from ruamel.yaml import YAML

from axcalib.dossier import atomic_write_text, canonical_json_bytes, exclusive_file_lock
from axcalib.schemas import EducationEnrollment, EducationProgram, ProgramRef

SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class ProgramRepositoryError(RuntimeError):
    """Base education repository error."""


class ProgramVersionConflictError(ProgramRepositoryError):
    """Raised when an immutable program selector is published with new content."""


class EnrollmentRevisionConflictError(ProgramRepositoryError):
    """Raised when a stale enrollment update loses compare-and-swap."""


class ProgramRepository:
    """Immutable, hash-bound education program definitions."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._yaml = YAML(typ="safe")
        self._yaml.default_flow_style = False

    def publish(self, program: EducationProgram) -> ProgramRef:
        """Persist one program version or return its existing identical reference."""

        path = self.path_for(program.program_id, program.version)
        digest = hashlib.sha256(
            canonical_json_bytes(program.model_dump(mode="json"))
        ).hexdigest()
        with exclusive_file_lock(path):
            if path.exists():
                existing = self._load_path(path)
                existing_digest = hashlib.sha256(
                    canonical_json_bytes(existing.model_dump(mode="json"))
                ).hexdigest()
                if existing_digest != digest:
                    raise ProgramVersionConflictError(
                        f"program selector already has different content: "
                        f"{program.program_id}@{program.version}"
                    )
            else:
                self._write(path, program)
        return ProgramRef(
            program_id=program.program_id,
            version=program.version,
            sha256=digest,
            source_uri=str(path),
        )

    def resolve(self, selector: str) -> tuple[EducationProgram, ProgramRef]:
        """Load and hash one exact ``program_id@version`` selector."""

        try:
            program_id, version = selector.rsplit("@", 1)
        except ValueError as error:
            raise ProgramRepositoryError("program selector must be program_id@version") from error
        path = self.path_for(program_id, version)
        if not path.is_file():
            raise ProgramRepositoryError(f"program not found: {selector}")
        program = self._load_path(path)
        if program.program_id != program_id or program.version != version:
            raise ProgramRepositoryError(
                "program content selector does not match its repository path"
            )
        digest = hashlib.sha256(
            canonical_json_bytes(program.model_dump(mode="json"))
        ).hexdigest()
        return program, ProgramRef(
            program_id=program.program_id,
            version=program.version,
            sha256=digest,
            source_uri=str(path),
        )

    def path_for(self, program_id: str, version: str) -> Path:
        if SAFE_NAME.fullmatch(program_id) is None or SAFE_NAME.fullmatch(version) is None:
            raise ProgramRepositoryError("invalid program selector")
        return self.root / f"{program_id}@{version}.program.yaml"

    def _load_path(self, path: Path) -> EducationProgram:
        return EducationProgram.model_validate(
            self._yaml.load(path.read_text(encoding="utf-8"))
        )

    def _write(self, path: Path, program: EducationProgram) -> None:
        buffer = StringIO()
        self._yaml.dump(program.model_dump(mode="json"), buffer)
        atomic_write_text(path, buffer.getvalue())


def load_program(path: Path) -> EducationProgram:
    """Load one strict program blueprint from YAML."""

    yaml = YAML(typ="safe")
    return EducationProgram.model_validate(
        yaml.load(path.resolve().read_text(encoding="utf-8"))
    )


class EnrollmentRepository:
    """Revisioned learner progress records with local compare-and-swap."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._yaml = YAML(typ="safe")
        self._yaml.default_flow_style = False

    def path_for(self, enrollment_id: str) -> Path:
        if SAFE_NAME.fullmatch(enrollment_id) is None:
            raise ProgramRepositoryError("invalid enrollment_id")
        return self.root / f"AXE-{enrollment_id}.enrollment.yaml"

    def create(self, enrollment: EducationEnrollment) -> Path:
        path = self.path_for(enrollment.enrollment_id)
        with exclusive_file_lock(path):
            if path.exists():
                raise ProgramRepositoryError(
                    f"enrollment already exists: {enrollment.enrollment_id}"
                )
            self._write(path, enrollment)
        return path

    def load(self, enrollment_id: str) -> EducationEnrollment:
        path = self.path_for(enrollment_id)
        if not path.is_file():
            raise ProgramRepositoryError(f"enrollment not found: {enrollment_id}")
        enrollment = EducationEnrollment.model_validate(
            self._yaml.load(path.read_text(encoding="utf-8"))
        )
        if enrollment.enrollment_id != enrollment_id:
            raise ProgramRepositoryError(
                "enrollment content ID does not match its repository path"
            )
        return enrollment

    def save(
        self,
        enrollment: EducationEnrollment,
        *,
        expected_revision: int,
    ) -> EducationEnrollment:
        path = self.path_for(enrollment.enrollment_id)
        with exclusive_file_lock(path):
            current = self.load(enrollment.enrollment_id)
            if current.revision != expected_revision:
                raise EnrollmentRevisionConflictError(
                    f"expected revision {expected_revision}; current revision is "
                    f"{current.revision}"
                )
            updated = enrollment.model_copy(
                update={
                    "revision": expected_revision + 1,
                    "updated_at": datetime.now(UTC),
                }
            )
            self._write(path, updated)
        return updated

    def _write(self, path: Path, enrollment: EducationEnrollment) -> None:
        buffer = StringIO()
        self._yaml.dump(enrollment.model_dump(mode="json"), buffer)
        atomic_write_text(path, buffer.getvalue())


__all__ = [
    "EnrollmentRepository",
    "EnrollmentRevisionConflictError",
    "ProgramRepository",
    "ProgramRepositoryError",
    "ProgramVersionConflictError",
    "load_program",
]
