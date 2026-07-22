"""Fail-closed authentication contracts for the optional HTTP adapter."""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ApiRole(StrEnum):
    """Coarse delivery roles; domain HITL authority remains separately enforced."""

    VIEWER = "viewer"
    OPERATOR = "operator"
    ADMINISTRATOR = "administrator"


class ApiPrincipal(BaseModel):
    """Verified caller identity supplied by a deployment-owned token verifier."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    subject: str = Field(min_length=1, max_length=300)
    role: ApiRole
    organization_id: str | None = Field(default=None, max_length=200)
    scopes: frozenset[str] = Field(default_factory=frozenset)


class ApiPipelineGrant(BaseModel):
    """Deployment-owned allowlist entry for one transport-safe pipeline."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pipeline_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
    pipeline_version: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
    execute_roles: frozenset[ApiRole] = Field(
        default_factory=lambda: frozenset({ApiRole.OPERATOR, ApiRole.ADMINISTRATOR})
    )

    @model_validator(mode="after")
    def require_execute_role(self) -> ApiPipelineGrant:
        if not self.execute_roles:
            raise ValueError("execute_roles must not be empty")
        if ApiRole.VIEWER in self.execute_roles:
            raise ValueError("viewer cannot be granted pipeline execution")
        return self


class TokenVerifier(Protocol):
    """Verify a bearer token without exposing token material to AXCalib records."""

    def verify(self, token: str) -> ApiPrincipal | None:
        """Return a principal for a valid token, otherwise ``None``."""

        ...


class RejectAllTokenVerifier:
    """Safe default used until a deployment injects an approved verifier."""

    def verify(self, token: str) -> None:
        """Reject every token without recording it."""

        del token
        return None


__all__ = [
    "ApiPipelineGrant",
    "ApiPrincipal",
    "ApiRole",
    "RejectAllTokenVerifier",
    "TokenVerifier",
]
