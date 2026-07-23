"""Provider-neutral JWT access-token verification for the optional HTTP adapter.

This module intentionally does not discover or fetch remote metadata. A deployment
must bind an approved issuer and JWKS URI to a :class:`JwkSetProvider`. Invalid
tokens return ``None``; provider/configuration failures raise
``JwkSetUnavailableError`` so the HTTP boundary can fail closed with 503.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any, ClassVar, Protocol
from urllib.parse import urlsplit

import jwt
from pydantic import BaseModel, ConfigDict, Field, model_validator

from axcalib.api.auth import ApiPrincipal, ApiRole

_ASYMMETRIC_ALGORITHMS = frozenset({"RS256", "PS256", "ES256"})
_ACCESS_TOKEN_TYPES = frozenset({"at+jwt", "application/at+jwt"})
_FORBIDDEN_JOSE_HEADERS = frozenset({"jku", "x5u", "x5c"})
_CORE_CLAIMS = frozenset({"iss", "sub", "aud", "exp", "iat", "jti", "client_id"})


class OidcRoleBinding(BaseModel):
    """Map one deployment-owned external role value to one AXCalib API role."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_value: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
    role: ApiRole


class OidcScopeBinding(BaseModel):
    """Map one deployment-owned external scope value to one AXCalib API scope."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_value: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
    api_scope: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:*:-]{0,255}$")


class OidcIdentityPolicy(BaseModel):
    """Versioned, explicit validation and claim-mapping policy.

    The defaults are conservative reference values, not approval of an issuer,
    audience, role vocabulary, or token lifetime for an operating environment.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    policy_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
    policy_version: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
    issuer: str = Field(min_length=1, max_length=500)
    audience: str = Field(min_length=1, max_length=500)
    jwks_uri: str = Field(min_length=1, max_length=1000)
    allowed_algorithms: tuple[str, ...] = ("RS256",)
    role_claim: str = Field(
        default="roles",
        pattern=r"^[A-Za-z][A-Za-z0-9._:-]{0,127}$",
    )
    scope_claim: str = Field(
        default="scope",
        pattern=r"^[A-Za-z][A-Za-z0-9._:-]{0,127}$",
    )
    organization_claim: str = Field(
        default="organization_id",
        pattern=r"^[A-Za-z][A-Za-z0-9._:-]{0,127}$",
    )
    role_bindings: tuple[OidcRoleBinding, ...]
    scope_bindings: tuple[OidcScopeBinding, ...]
    require_organization: bool = True
    clock_skew_seconds: int = Field(default=30, ge=0, le=300)
    max_token_lifetime_seconds: int = Field(default=900, ge=60, le=86_400)
    max_token_bytes: int = Field(default=16_384, ge=1024, le=65_536)

    @model_validator(mode="after")
    def validate_policy(self) -> OidcIdentityPolicy:
        _require_https_identity_uri(self.issuer, field_name="issuer")
        _require_https_identity_uri(self.jwks_uri, field_name="jwks_uri")
        if not self.allowed_algorithms:
            raise ValueError("allowed_algorithms must not be empty")
        if len(set(self.allowed_algorithms)) != len(self.allowed_algorithms):
            raise ValueError("allowed_algorithms must be unique")
        unsupported = set(self.allowed_algorithms).difference(_ASYMMETRIC_ALGORITHMS)
        if unsupported:
            raise ValueError("allowed_algorithms may only contain RS256, PS256, or ES256")
        claim_names = {self.role_claim, self.scope_claim, self.organization_claim}
        if len(claim_names) != 3 or claim_names.intersection(_CORE_CLAIMS):
            raise ValueError("authorization claim names must be distinct from core claims")
        if not self.role_bindings:
            raise ValueError("role_bindings must not be empty")
        if not self.scope_bindings:
            raise ValueError("scope_bindings must not be empty")
        _require_unique(
            (binding.claim_value for binding in self.role_bindings),
            field_name="role_bindings.claim_value",
        )
        _require_unique(
            (binding.claim_value for binding in self.scope_bindings),
            field_name="scope_bindings.claim_value",
        )
        _require_unique(
            (binding.api_scope for binding in self.scope_bindings),
            field_name="scope_bindings.api_scope",
        )
        return self

    @property
    def reference(self) -> str:
        """Return the stable policy selector available to deployment audit wiring."""

        return f"{self.policy_id}@{self.policy_version}"


class JsonWebKey(BaseModel):
    """Strict subset of public JWK fields accepted by the reference verifier."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kid: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
    kty: str
    alg: str
    use: str = "sig"
    key_ops: tuple[str, ...] | None = None
    n: str | None = None
    e: str | None = None
    crv: str | None = None
    x: str | None = None
    y: str | None = None

    @model_validator(mode="after")
    def validate_key(self) -> JsonWebKey:
        if self.alg not in _ASYMMETRIC_ALGORITHMS:
            raise ValueError("JWK alg is not an approved asymmetric algorithm")
        if self.use != "sig":
            raise ValueError("JWK use must be sig")
        if self.key_ops is not None and ("verify" not in self.key_ops or "sign" in self.key_ops):
            raise ValueError("JWK key_ops must permit verify and must not permit sign")
        if self.alg in {"RS256", "PS256"}:
            if self.kty != "RSA" or not self.n or not self.e:
                raise ValueError("RSA algorithms require RSA n/e public key material")
            if any(value is not None for value in (self.crv, self.x, self.y)):
                raise ValueError("RSA JWK must not contain EC key material")
        elif (
            self.kty != "EC"
            or self.crv != "P-256"
            or not self.x
            or not self.y
            or self.n is not None
            or self.e is not None
        ):
            raise ValueError("ES256 requires an EC P-256 x/y public key")
        return self

    def verification_dict(self) -> dict[str, Any]:
        """Return only fields required by the cryptographic verifier."""

        return self.model_dump(exclude_none=True)


class JwkSetSnapshot(BaseModel):
    """Issuer-bound immutable public-key snapshot supplied by a deployment port."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    issuer: str = Field(min_length=1, max_length=500)
    jwks_uri: str = Field(min_length=1, max_length=1000)
    version: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
    keys: tuple[JsonWebKey, ...]

    @model_validator(mode="after")
    def validate_snapshot(self) -> JwkSetSnapshot:
        _require_https_identity_uri(self.issuer, field_name="issuer")
        _require_https_identity_uri(self.jwks_uri, field_name="jwks_uri")
        if not self.keys:
            raise ValueError("keys must not be empty")
        _require_unique((key.kid for key in self.keys), field_name="keys.kid")
        return self


class JwkSetUnavailableError(RuntimeError):
    """An approved key source is unavailable or does not match its binding."""


class JwkSetProvider(Protocol):
    """Load a trusted issuer-bound key snapshot without using token-controlled URLs."""

    def get_jwk_set(self, *, issuer: str, jwks_uri: str) -> JwkSetSnapshot:
        """Return the exact approved issuer/JWKS snapshot or raise an availability error."""

        ...


class StaticJwkSetProvider:
    """Offline provider for local fixtures and controlled validation snapshots."""

    def __init__(self, snapshot: JwkSetSnapshot) -> None:
        self._snapshot = snapshot

    def get_jwk_set(self, *, issuer: str, jwks_uri: str) -> JwkSetSnapshot:
        """Return a pinned snapshot only when both trust bindings match exactly."""

        if issuer != self._snapshot.issuer or jwks_uri != self._snapshot.jwks_uri:
            raise JwkSetUnavailableError("issuer/JWKS binding does not match the snapshot")
        return self._snapshot


class OidcTokenVerifier:
    """Verify RFC 9068-style JWT access tokens into an AXCalib principal."""

    _accepted_token_types: ClassVar[frozenset[str]] = _ACCESS_TOKEN_TYPES

    def __init__(
        self,
        *,
        policy: OidcIdentityPolicy,
        jwk_set_provider: JwkSetProvider,
    ) -> None:
        self._policy = policy
        self._jwk_set_provider = jwk_set_provider

    @property
    def policy_reference(self) -> str:
        """Return the versioned policy selector for deployment audit wiring."""

        return self._policy.reference

    def verify(self, token: str) -> ApiPrincipal | None:
        """Return a mapped principal, or ``None`` for every invalid-token condition."""

        try:
            token_bytes = token.encode("ascii")
        except UnicodeEncodeError:
            return None
        if not token_bytes or len(token_bytes) > self._policy.max_token_bytes:
            return None
        header = self._read_header(token)
        if header is None:
            return None
        algorithm = header.get("alg")
        token_type = header.get("typ")
        key_id = header.get("kid")
        if (
            not isinstance(algorithm, str)
            or algorithm not in self._policy.allowed_algorithms
            or not isinstance(token_type, str)
            or token_type.casefold() not in self._accepted_token_types
            or not isinstance(key_id, str)
            or not key_id
            or len(key_id) > 128
            or any(name in header for name in _FORBIDDEN_JOSE_HEADERS)
            or header.get("crit") not in (None, [])
        ):
            return None

        snapshot = self._jwk_set_provider.get_jwk_set(
            issuer=self._policy.issuer,
            jwks_uri=self._policy.jwks_uri,
        )
        if snapshot.issuer != self._policy.issuer or snapshot.jwks_uri != self._policy.jwks_uri:
            raise JwkSetUnavailableError("provider returned an unbound JWK snapshot")
        candidates = [key for key in snapshot.keys if key.kid == key_id and key.alg == algorithm]
        if len(candidates) != 1:
            return None

        try:
            verification_key = jwt.PyJWK.from_dict(
                candidates[0].verification_dict(),
                algorithm=algorithm,
            )
            required_claims = [
                "iss",
                "sub",
                "aud",
                "exp",
                "iat",
                "jti",
                "client_id",
                self._policy.role_claim,
                self._policy.scope_claim,
            ]
            if self._policy.require_organization:
                required_claims.append(self._policy.organization_claim)
            claims = jwt.decode(
                token,
                key=verification_key,
                algorithms=list(self._policy.allowed_algorithms),
                audience=self._policy.audience,
                issuer=self._policy.issuer,
                leeway=self._policy.clock_skew_seconds,
                options={"require": required_claims},
            )
        except (jwt.PyJWTError, TypeError, ValueError):
            return None
        return self._map_principal(claims)

    @staticmethod
    def _read_header(token: str) -> Mapping[str, Any] | None:
        try:
            header = jwt.get_unverified_header(token)
        except (jwt.PyJWTError, TypeError, ValueError):
            return None
        return header if isinstance(header, Mapping) else None

    def _map_principal(self, claims: Mapping[str, Any]) -> ApiPrincipal | None:
        subject = claims.get("sub")
        client_id = claims.get("client_id")
        issued_at = claims.get("iat")
        expires_at = claims.get("exp")
        token_id = claims.get("jti")
        if (
            not isinstance(subject, str)
            or not subject
            or len(subject) > 300
            or not isinstance(client_id, str)
            or not client_id
            or not isinstance(token_id, str)
            or not token_id
            or isinstance(issued_at, bool)
            or not isinstance(issued_at, int)
            or isinstance(expires_at, bool)
            or not isinstance(expires_at, int)
            or expires_at <= issued_at
            or expires_at - issued_at > self._policy.max_token_lifetime_seconds
        ):
            return None

        role_values = _claim_values(
            claims.get(self._policy.role_claim),
            split_space_delimited=False,
        )
        scope_values = _claim_values(
            claims.get(self._policy.scope_claim),
            split_space_delimited=True,
        )
        if role_values is None or scope_values is None:
            return None
        role_map = {binding.claim_value: binding.role for binding in self._policy.role_bindings}
        scope_map = {
            binding.claim_value: binding.api_scope for binding in self._policy.scope_bindings
        }
        if set(role_values).difference(role_map) or set(scope_values).difference(scope_map):
            return None
        mapped_roles = {role_map[value] for value in role_values}
        if len(mapped_roles) != 1:
            return None

        organization: str | None = None
        raw_organization = claims.get(self._policy.organization_claim)
        if raw_organization is not None:
            if (
                not isinstance(raw_organization, str)
                or not raw_organization.strip()
                or len(raw_organization) > 200
            ):
                return None
            organization = raw_organization
        if self._policy.require_organization and organization is None:
            return None
        try:
            return ApiPrincipal(
                subject=subject,
                role=next(iter(mapped_roles)),
                organization_id=organization,
                scopes=frozenset(scope_map[value] for value in scope_values),
            )
        except ValueError:
            return None


def _claim_values(
    value: Any,
    *,
    split_space_delimited: bool,
) -> tuple[str, ...] | None:
    if isinstance(value, str):
        values = value.split() if split_space_delimited else [value]
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        values = list(value)
    else:
        return None
    if (
        not values
        or any(not isinstance(item, str) or not item for item in values)
        or len(values) != len(set(values))
    ):
        return None
    return tuple(values)


def _require_https_identity_uri(value: str, *, field_name: str) -> None:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(f"{field_name} must be an exact HTTPS URI without userinfo/query/fragment")


def _require_unique(values: Iterable[str], *, field_name: str) -> None:
    materialized = tuple(values)
    if len(materialized) != len(set(materialized)):
        raise ValueError(f"{field_name} must be unique")


__all__ = [
    "JsonWebKey",
    "JwkSetProvider",
    "JwkSetSnapshot",
    "JwkSetUnavailableError",
    "OidcIdentityPolicy",
    "OidcRoleBinding",
    "OidcScopeBinding",
    "OidcTokenVerifier",
    "StaticJwkSetProvider",
]
