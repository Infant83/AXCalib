from pathlib import Path

import pytest

from axcalib.dossier import (
    DossierError,
    DossierRepository,
    RevisionConflictError,
    SnapshotRepository,
)
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
