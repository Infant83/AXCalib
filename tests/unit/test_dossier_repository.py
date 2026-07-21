from pathlib import Path
from typing import Any

import pytest

from axcalib.dossier import (
    DossierError,
    DossierRepository,
    RevisionConflictError,
    SnapshotRepository,
    atomic_write_text,
)
from axcalib.dossier import repository as repository_module
from axcalib.schemas import ProjectDossier
from axcalib.workflows.two_gate import ProjectStatus


def _dossier() -> ProjectDossier:
    return ProjectDossier(
        project_id="repository-test-001",
        display_id="AXC-REPO-001",
        title="저장소 테스트",
        revision=1,
        status=ProjectStatus.DRAFT,
    )


def test_round_trip_snapshot_and_stale_write(tmp_path: Path) -> None:
    repository = DossierRepository(tmp_path / "dossiers")
    snapshots = SnapshotRepository(tmp_path / "snapshots")
    original = _dossier()

    path = repository.create(original)
    assert path.name == "AXC-repository-test-001.axc.yaml"
    assert repository.load(original.project_id) == original

    first_snapshot = snapshots.freeze(original)
    second_snapshot = snapshots.freeze(original)
    assert first_snapshot == second_snapshot
    assert Path(first_snapshot.uri).is_file()

    Path(first_snapshot.uri).write_text("tampered", encoding="utf-8")
    with pytest.raises(DossierError, match="integrity failure"):
        snapshots.freeze(original)

    submitted = original.model_copy(update={"status": ProjectStatus.REGISTRATION_READY})
    saved = repository.save(submitted, expected_revision=1)
    assert saved.revision == 2

    with pytest.raises(RevisionConflictError, match="current revision is 2"):
        repository.save(original, expected_revision=1)


def test_atomic_write_retries_a_transient_permission_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "atomic.txt"
    target.write_text("before", encoding="utf-8")
    real_replace = repository_module.os.replace
    attempts = 0

    def flaky_replace(source: Any, destination: Any) -> None:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise PermissionError("synthetic transient lock")
        real_replace(source, destination)

    monkeypatch.setattr(repository_module.os, "replace", flaky_replace)
    monkeypatch.setattr(repository_module.time, "sleep", lambda _seconds: None)

    atomic_write_text(target, "after")

    assert attempts == 3
    assert target.read_text(encoding="utf-8") == "after"


@pytest.mark.parametrize(
    "project_id",
    ["../outside", r"..\outside", "contains space", "", "a" * 129],
)
def test_repository_rejects_unsafe_project_ids(
    tmp_path: Path, project_id: str
) -> None:
    repository = DossierRepository(tmp_path / "dossiers")

    with pytest.raises(DossierError, match="invalid project_id"):
        repository.load(project_id)


def test_repository_rejects_content_id_that_does_not_match_path(tmp_path: Path) -> None:
    repository = DossierRepository(tmp_path / "dossiers")
    path = repository.create(_dossier())
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "project_id: repository-test-001",
            "project_id: repository-test-other",
        ),
        encoding="utf-8",
    )

    with pytest.raises(DossierError, match="does not match"):
        repository.load("repository-test-001")


def test_repository_migrates_v1alpha1_on_load(tmp_path: Path) -> None:
    repository = DossierRepository(tmp_path / "dossiers")
    path = repository.create(_dossier())
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "schema_version: axcalib.dossier/v1alpha2",
            "schema_version: axcalib.dossier/v1alpha1",
        ),
        encoding="utf-8",
    )

    loaded = repository.load("repository-test-001")
    assert loaded.schema_version == "axcalib.dossier/v1alpha2"
