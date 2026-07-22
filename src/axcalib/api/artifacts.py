"""Fail-closed staged artifact contracts for the optional HTTP adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Protocol

from axcalib.api.auth import ApiPrincipal
from axcalib.api.models import StagedArtifactRef

ArtifactPurpose = Literal["registration_proposal", "pptx_sidecar"]


class StagedArtifactResolver(Protocol):
    """Resolve an opaque, access-checked artifact ID to deployment-local bytes."""

    def resolve(
        self,
        artifact: StagedArtifactRef,
        *,
        principal: ApiPrincipal,
        purpose: ArtifactPurpose,
    ) -> Path | None:
        """Return an approved local immutable file, or ``None`` when unavailable."""

        ...


class RejectAllStagedArtifactResolver:
    """Safe default used until a deployment injects an approved staging service."""

    def resolve(
        self,
        artifact: StagedArtifactRef,
        *,
        principal: ApiPrincipal,
        purpose: ArtifactPurpose,
    ) -> None:
        """Reject every artifact without interpreting its ID as a path."""

        del artifact, principal, purpose
        return None


__all__ = [
    "ArtifactPurpose",
    "RejectAllStagedArtifactResolver",
    "StagedArtifactResolver",
]
