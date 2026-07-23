from __future__ import annotations

import base64
from collections.abc import Mapping
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from pydantic import ValidationError

from axcalib.api import ApiRole
from axcalib.api.oidc import (
    JsonWebKey,
    JwkSetSnapshot,
    JwkSetUnavailableError,
    OidcIdentityPolicy,
    OidcRoleBinding,
    OidcScopeBinding,
    OidcTokenVerifier,
    StaticJwkSetProvider,
)

ISSUER = "https://identity.example.test"
AUDIENCE = "urn:axcalib:api"
JWKS_URI = "https://identity.example.test/.well-known/jwks.json"
KEY_ID = "synthetic-rsa-2026-07"


def _base64url_uint(value: int) -> str:
    width = (value.bit_length() + 7) // 8
    return base64.urlsafe_b64encode(value.to_bytes(width, "big")).rstrip(b"=").decode()


def _public_jwk(
    private_key: rsa.RSAPrivateKey,
    *,
    key_id: str = KEY_ID,
    algorithm: str = "RS256",
) -> JsonWebKey:
    numbers = private_key.public_key().public_numbers()
    return JsonWebKey(
        kid=key_id,
        kty="RSA",
        alg=algorithm,
        use="sig",
        key_ops=("verify",),
        n=_base64url_uint(numbers.n),
        e=_base64url_uint(numbers.e),
    )


def _policy(**overrides: Any) -> OidcIdentityPolicy:
    data: dict[str, Any] = {
        "policy_id": "synthetic-oidc",
        "policy_version": "v1",
        "issuer": ISSUER,
        "audience": AUDIENCE,
        "jwks_uri": JWKS_URI,
        "role_bindings": (
            OidcRoleBinding(
                claim_value="axcalib-operator",
                role=ApiRole.OPERATOR,
            ),
        ),
        "scope_bindings": (
            OidcScopeBinding(
                claim_value="axcalib.runs.execute",
                api_scope="runs:execute",
            ),
        ),
    }
    data.update(overrides)
    return OidcIdentityPolicy(**data)


def _claims(*, now: int = 2_000_000_000, **overrides: Any) -> dict[str, Any]:
    claims: dict[str, Any] = {
        "iss": ISSUER,
        "sub": "user:synthetic-operator",
        "aud": AUDIENCE,
        "exp": now + 600,
        "iat": now,
        "jti": "token:synthetic-001",
        "client_id": "client:synthetic-web",
        "roles": ["axcalib-operator"],
        "scope": "axcalib.runs.execute",
        "organization_id": "org:synthetic",
    }
    claims.update(overrides)
    return claims


def _token(
    private_key: rsa.RSAPrivateKey,
    claims: Mapping[str, Any],
    *,
    headers: Mapping[str, Any] | None = None,
) -> str:
    token_headers = {"kid": KEY_ID, "typ": "at+jwt"}
    if headers is not None:
        token_headers.update(headers)
    return jwt.encode(
        dict(claims),
        private_key,
        algorithm="RS256",
        headers=token_headers,
    )


def _verifier(
    private_key: rsa.RSAPrivateKey,
    *,
    policy: OidcIdentityPolicy | None = None,
) -> OidcTokenVerifier:
    selected_policy = policy or _policy()
    snapshot = JwkSetSnapshot(
        issuer=ISSUER,
        jwks_uri=JWKS_URI,
        version="synthetic-v1",
        keys=(_public_jwk(private_key),),
    )
    return OidcTokenVerifier(
        policy=selected_policy,
        jwk_set_provider=StaticJwkSetProvider(snapshot),
    )


def _tamper_signature(token: str) -> str:
    header, payload, signature = token.split(".")
    replacement = "A" if signature[0] != "A" else "B"
    return ".".join((header, payload, replacement + signature[1:]))


def test_oidc_verifier_maps_only_approved_claims(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_key = rsa.generate_private_key(public_exponent=65_537, key_size=2048)
    now = 2_000_000_000
    monkeypatch.setattr("jwt.api_jwt.datetime", _FixedDateTime)
    verifier = _verifier(private_key)

    principal = verifier.verify(_token(private_key, _claims(now=now)))

    assert principal is not None
    assert principal.subject == "user:synthetic-operator"
    assert principal.role is ApiRole.OPERATOR
    assert principal.organization_id == "org:synthetic"
    assert principal.scopes == frozenset({"runs:execute"})
    assert verifier.policy_reference == "synthetic-oidc@v1"


@pytest.mark.parametrize("algorithm", ["PS256", "ES256"])
def test_oidc_verifier_supports_only_explicitly_allowlisted_asymmetric_algorithms(
    monkeypatch: pytest.MonkeyPatch,
    algorithm: str,
) -> None:
    now = 2_000_000_000
    monkeypatch.setattr("jwt.api_jwt.datetime", _FixedDateTime)
    policy = _policy(allowed_algorithms=(algorithm,))
    if algorithm == "PS256":
        private_key = rsa.generate_private_key(public_exponent=65_537, key_size=2048)
        public = _public_jwk(private_key, algorithm=algorithm)
    else:
        private_key = ec.generate_private_key(ec.SECP256R1())
        numbers = private_key.public_key().public_numbers()
        public = JsonWebKey(
            kid=KEY_ID,
            kty="EC",
            alg=algorithm,
            use="sig",
            key_ops=("verify",),
            crv="P-256",
            x=_base64url_uint(numbers.x),
            y=_base64url_uint(numbers.y),
        )
    verifier = OidcTokenVerifier(
        policy=policy,
        jwk_set_provider=StaticJwkSetProvider(
            JwkSetSnapshot(
                issuer=ISSUER,
                jwks_uri=JWKS_URI,
                version=f"synthetic-{algorithm.casefold()}",
                keys=(public,),
            )
        ),
    )
    token = jwt.encode(
        _claims(now=now),
        private_key,
        algorithm=algorithm,
        headers={"kid": KEY_ID, "typ": "at+jwt"},
    )

    assert verifier.verify(token) is not None


@pytest.mark.parametrize(
    ("claim_overrides", "removed_claim"),
    [
        ({"iss": "https://wrong-issuer.example.test"}, None),
        ({"aud": "urn:wrong:audience"}, None),
        ({"exp": 2_000_000_901}, None),
        ({"roles": ["unmapped-role"]}, None),
        ({"roles": ["axcalib-operator", "unmapped-role"]}, None),
        ({"scope": "unmapped.scope"}, None),
        ({"organization_id": ""}, None),
        ({}, "client_id"),
        ({}, "jti"),
        ({}, "organization_id"),
    ],
)
def test_oidc_verifier_rejects_invalid_or_unmapped_claims(
    monkeypatch: pytest.MonkeyPatch,
    claim_overrides: dict[str, Any],
    removed_claim: str | None,
) -> None:
    private_key = rsa.generate_private_key(public_exponent=65_537, key_size=2048)
    now = 2_000_000_000
    monkeypatch.setattr("jwt.api_jwt.datetime", _FixedDateTime)
    claims = _claims(now=now, **claim_overrides)
    if removed_claim is not None:
        claims.pop(removed_claim)

    assert _verifier(private_key).verify(_token(private_key, claims)) is None


def test_oidc_verifier_rejects_expired_tampered_and_wrong_key_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_key = rsa.generate_private_key(public_exponent=65_537, key_size=2048)
    other_key = rsa.generate_private_key(public_exponent=65_537, key_size=2048)
    now = 2_000_000_000
    monkeypatch.setattr("jwt.api_jwt.datetime", _FixedDateTime)
    verifier = _verifier(private_key)
    valid = _token(private_key, _claims(now=now))

    assert verifier.verify(_tamper_signature(valid)) is None
    assert verifier.verify(_token(other_key, _claims(now=now))) is None
    assert (
        verifier.verify(
            _token(
                private_key,
                _claims(now=now, iat=now - 300, exp=now - 31),
            )
        )
        is None
    )


@pytest.mark.parametrize(
    "headers",
    [
        {"typ": "JWT"},
        {"typ": "id+jwt"},
        {"kid": "unknown-key"},
        {"jku": "https://attacker.example.test/jwks.json"},
        {"x5u": "https://attacker.example.test/certificate"},
        {"crit": ["unknown"]},
    ],
)
def test_oidc_verifier_rejects_cross_jwt_and_token_controlled_key_headers(
    monkeypatch: pytest.MonkeyPatch,
    headers: dict[str, Any],
) -> None:
    private_key = rsa.generate_private_key(public_exponent=65_537, key_size=2048)
    now = 2_000_000_000
    monkeypatch.setattr("jwt.api_jwt.datetime", _FixedDateTime)
    token = _token(private_key, _claims(now=now), headers=headers)

    assert _verifier(private_key).verify(token) is None


def test_oidc_verifier_rejects_symmetric_algorithm_and_oversized_token() -> None:
    private_key = rsa.generate_private_key(public_exponent=65_537, key_size=2048)
    verifier = _verifier(private_key)
    symmetric = jwt.encode(
        _claims(),
        "not-a-production-secret-but-long-enough-for-this-negative-fixture",
        algorithm="HS256",
        headers={"kid": KEY_ID, "typ": "at+jwt"},
    )

    assert verifier.verify(symmetric) is None
    assert verifier.verify("x" * 16_385) is None
    assert verifier.verify("not-a-jwt") is None
    assert verifier.verify("한글-token") is None
    assert verifier.verify("\ud800") is None


def test_oidc_policy_and_jwks_binding_fail_closed() -> None:
    private_key = rsa.generate_private_key(public_exponent=65_537, key_size=2048)
    snapshot = JwkSetSnapshot(
        issuer=ISSUER,
        jwks_uri=JWKS_URI,
        version="synthetic-v1",
        keys=(_public_jwk(private_key),),
    )
    wrong_binding_policy = _policy(jwks_uri="https://identity.example.test/other-jwks")
    verifier = OidcTokenVerifier(
        policy=wrong_binding_policy,
        jwk_set_provider=StaticJwkSetProvider(snapshot),
    )

    with pytest.raises(JwkSetUnavailableError):
        verifier.verify(_token(private_key, _claims()))

    with pytest.raises(ValidationError):
        _policy(issuer="http://identity.example.test")
    with pytest.raises(ValidationError):
        _policy(allowed_algorithms=("HS256",))
    with pytest.raises(ValidationError):
        _policy(
            role_bindings=(
                OidcRoleBinding(claim_value="duplicate", role=ApiRole.OPERATOR),
                OidcRoleBinding(claim_value="duplicate", role=ApiRole.ADMINISTRATOR),
            )
        )
    with pytest.raises(ValidationError):
        OidcIdentityPolicy.model_validate(_policy().model_dump() | {"unexpected": True})


class _FixedDateTime:
    @classmethod
    def now(cls, tz: Any = None) -> Any:
        from datetime import datetime

        return datetime.fromtimestamp(cls.timestamp, tz=tz)

    timestamp = 2_000_000_000
