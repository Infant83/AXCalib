"""Allowlisted dossier schema migration interface."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

Migration = Callable[[dict[str, Any]], dict[str, Any]]
CURRENT_DOSSIER_SCHEMA = "axcalib.dossier/v1alpha2"


class DossierMigrationRegistry:
    """Register explicit adjacent schema migrations without dynamic imports."""

    def __init__(self) -> None:
        self._migrations: dict[tuple[str, str], Migration] = {}

    def register(self, from_version: str, to_version: str, migration: Migration) -> None:
        key = (from_version, to_version)
        if key in self._migrations:
            raise ValueError(f"dossier migration already registered: {key}")
        if not from_version or not to_version or from_version == to_version:
            raise ValueError("dossier migration versions must be distinct and non-empty")
        self._migrations[key] = migration

    def migrate(
        self,
        value: dict[str, Any],
        *,
        from_version: str,
        to_version: str,
    ) -> dict[str, Any]:
        try:
            migration = self._migrations[(from_version, to_version)]
        except KeyError as error:
            raise KeyError(
                f"dossier migration is not allowlisted: {from_version} -> {to_version}"
            ) from error
        candidate = migration(dict(value))
        if candidate.get("schema_version") != to_version:
            raise ValueError("dossier migration did not set the declared target version")
        return candidate


def migrate_v1alpha1_to_v1alpha2(value: dict[str, Any]) -> dict[str, Any]:
    """Add the v1alpha2 education/config audit fields through model defaults."""

    if value.get("schema_version") != "axcalib.dossier/v1alpha1":
        raise ValueError("v1alpha1 migration received a different schema version")
    return {**value, "schema_version": CURRENT_DOSSIER_SCHEMA}


def default_dossier_migrations() -> DossierMigrationRegistry:
    """Return the code-owned adjacent migration registry."""

    registry = DossierMigrationRegistry()
    registry.register(
        "axcalib.dossier/v1alpha1",
        CURRENT_DOSSIER_SCHEMA,
        migrate_v1alpha1_to_v1alpha2,
    )
    return registry


__all__ = [
    "CURRENT_DOSSIER_SCHEMA",
    "DossierMigrationRegistry",
    "Migration",
    "default_dossier_migrations",
    "migrate_v1alpha1_to_v1alpha2",
]
