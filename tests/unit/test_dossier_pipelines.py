from pathlib import Path

from axcalib import AXCalib
from axcalib.dossier import (
    CURRENT_DOSSIER_SCHEMA,
    DossierMigrationRegistry,
    default_dossier_migrations,
)
from axcalib.pipelines import (
    DossierFreezePipeline,
    DossierFreezeRequest,
    DossierInitializePipeline,
    DossierInitializeRequest,
)
from axcalib.schemas import PipelineStatus

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tests" / "sources" / "oled_qc_project_outline.pptx"
SIDECAR = ROOT / "tests" / "sources" / "oled_qc_project_outline.axcalib.json"


def test_initialize_and_revision_aware_freeze(tmp_path: Path) -> None:
    client = AXCalib(tmp_path)
    initialize = client.registry.create(
        DossierInitializePipeline.pipeline_id,
        DossierInitializePipeline.pipeline_version,
    )
    created = initialize.run(
        DossierInitializeRequest(
            proposal_path=SOURCE,
            sidecar_path=SIDECAR,
            title="독립 dossier pipeline",
            project_id="dossier-pipeline-001",
        )
    )
    freeze = client.registry.create(
        DossierFreezePipeline.pipeline_id,
        DossierFreezePipeline.pipeline_version,
    )
    frozen = freeze.run(
        DossierFreezeRequest(
            project_id=created.project_id,
            expected_revision=created.dossier_revision,
        )
    )
    stale = freeze.run(
        DossierFreezeRequest(
            project_id=created.project_id,
            expected_revision=created.dossier_revision + 1,
        )
    )

    assert frozen.status is PipelineStatus.SUCCEEDED
    assert frozen.snapshot is not None
    assert stale.status is PipelineStatus.STALE
    assert stale.snapshot is None


def test_migration_registry_rejects_unallowlisted_paths() -> None:
    registry = DossierMigrationRegistry()
    registry.register(
        "axcalib.dossier/v0",
        "axcalib.dossier/v1alpha1",
        lambda value: {
            **value,
            "schema_version": "axcalib.dossier/v1alpha1",
        },
    )
    migrated = registry.migrate(
        {"schema_version": "axcalib.dossier/v0"},
        from_version="axcalib.dossier/v0",
        to_version="axcalib.dossier/v1alpha1",
    )
    assert migrated["schema_version"] == "axcalib.dossier/v1alpha1"


def test_builtin_v1alpha1_migration_targets_current_schema() -> None:
    migrated = default_dossier_migrations().migrate(
        {
            "schema_version": "axcalib.dossier/v1alpha1",
            "project_id": "legacy-project-001",
        },
        from_version="axcalib.dossier/v1alpha1",
        to_version=CURRENT_DOSSIER_SCHEMA,
    )
    assert migrated["schema_version"] == "axcalib.dossier/v1alpha2"
