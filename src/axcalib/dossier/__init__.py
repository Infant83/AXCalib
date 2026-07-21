"""Local dossier persistence and snapshot contracts."""

from axcalib.dossier.migrations import (
    CURRENT_DOSSIER_SCHEMA,
    DossierMigrationRegistry,
    Migration,
    default_dossier_migrations,
    migrate_v1alpha1_to_v1alpha2,
)
from axcalib.dossier.repository import (
    DossierAlreadyExistsError,
    DossierError,
    DossierNotFoundError,
    DossierRepository,
    FileLockTimeoutError,
    RevisionConflictError,
    SnapshotRepository,
    atomic_write_text,
    canonical_json_bytes,
    exclusive_file_lock,
)

__all__ = [
    "CURRENT_DOSSIER_SCHEMA",
    "DossierAlreadyExistsError",
    "DossierMigrationRegistry",
    "DossierError",
    "DossierNotFoundError",
    "DossierRepository",
    "FileLockTimeoutError",
    "Migration",
    "RevisionConflictError",
    "SnapshotRepository",
    "atomic_write_text",
    "canonical_json_bytes",
    "default_dossier_migrations",
    "exclusive_file_lock",
    "migrate_v1alpha1_to_v1alpha2",
]
