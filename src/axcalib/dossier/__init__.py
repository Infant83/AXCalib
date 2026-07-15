"""Local dossier persistence and snapshot contracts."""

from axcalib.dossier.repository import (
    DossierAlreadyExistsError,
    DossierError,
    DossierNotFoundError,
    DossierRepository,
    RevisionConflictError,
    SnapshotRepository,
    atomic_write_text,
    canonical_json_bytes,
)

__all__ = [
    "DossierAlreadyExistsError",
    "DossierError",
    "DossierNotFoundError",
    "DossierRepository",
    "RevisionConflictError",
    "SnapshotRepository",
    "atomic_write_text",
    "canonical_json_bytes",
]
