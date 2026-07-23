from __future__ import annotations

import base64
import time
from pathlib import Path

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from axcalib import AXCalib
from axcalib.api import ApiPipelineGrant, ApiRole, create_app
from axcalib.api.oidc import (
    JsonWebKey,
    JwkSetSnapshot,
    OidcIdentityPolicy,
    OidcRoleBinding,
    OidcScopeBinding,
    OidcTokenVerifier,
    StaticJwkSetProvider,
)

ISSUER = "https://identity.example.test"
AUDIENCE = "urn:axcalib:api"
JWKS_URI = "https://identity.example.test/.well-known/jwks.json"
KEY_ID = "synthetic-api-rsa"


def _base64url_uint(value: int) -> str:
    width = (value.bit_length() + 7) // 8
    return base64.urlsafe_b64encode(value.to_bytes(width, "big")).rstrip(b"=").decode()


def _identity_components(
    *,
    policy_jwks_uri: str = JWKS_URI,
) -> tuple[rsa.RSAPrivateKey, OidcTokenVerifier]:
    private_key = rsa.generate_private_key(public_exponent=65_537, key_size=2048)
    numbers = private_key.public_key().public_numbers()
    snapshot = JwkSetSnapshot(
        issuer=ISSUER,
        jwks_uri=JWKS_URI,
        version="synthetic-contract-v1",
        keys=(
            JsonWebKey(
                kid=KEY_ID,
                kty="RSA",
                alg="RS256",
                use="sig",
                key_ops=("verify",),
                n=_base64url_uint(numbers.n),
                e=_base64url_uint(numbers.e),
            ),
        ),
    )
    policy = OidcIdentityPolicy(
        policy_id="synthetic-api-identity",
        policy_version="v1",
        issuer=ISSUER,
        audience=AUDIENCE,
        jwks_uri=policy_jwks_uri,
        role_bindings=(
            OidcRoleBinding(
                claim_value="axcalib-operator",
                role=ApiRole.OPERATOR,
            ),
        ),
        scope_bindings=(
            OidcScopeBinding(
                claim_value="axcalib.runs.execute",
                api_scope="runs:execute",
            ),
        ),
    )
    return private_key, OidcTokenVerifier(
        policy=policy,
        jwk_set_provider=StaticJwkSetProvider(snapshot),
    )


def _access_token(private_key: rsa.RSAPrivateKey) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "iss": ISSUER,
            "sub": "user:oidc-operator",
            "aud": AUDIENCE,
            "iat": now,
            "exp": now + 300,
            "jti": "token:oidc-contract",
            "client_id": "client:oidc-contract",
            "roles": ["axcalib-operator"],
            "scope": "axcalib.runs.execute",
            "organization_id": "org:synthetic",
        },
        private_key,
        algorithm="RS256",
        headers={"kid": KEY_ID, "typ": "at+jwt"},
    )


def _client(
    tmp_path: Path,
    *,
    verifier: OidcTokenVerifier,
) -> TestClient:
    runtime = AXCalib(tmp_path / "workspace")
    app = create_app(
        runtime,
        token_verifier=verifier,
        pipeline_grants=(
            ApiPipelineGrant(
                pipeline_id="workspace.maintenance",
                pipeline_version="v1alpha1",
            ),
        ),
    )
    return TestClient(app)


def test_oidc_principal_reaches_the_existing_authorization_boundary_without_token_storage(
    tmp_path: Path,
) -> None:
    private_key, verifier = _identity_components()
    client = _client(tmp_path, verifier=verifier)
    token = _access_token(private_key)
    headers = {"Authorization": f"Bearer {token}"}

    catalog = client.get("/v1/pipelines", headers=headers)
    assert catalog.status_code == 200
    executed = client.post(
        "/v1/pipelines/workspace.maintenance/versions/v1alpha1/runs",
        headers=headers | {"Idempotency-Key": "oidc-contract-run"},
        json={"payload": {}},
    )

    assert executed.status_code == 200, executed.text
    assert executed.json()["status"] == "succeeded"
    assert token not in "\n".join(
        path.read_text(encoding="utf-8") for path in (tmp_path / "workspace").rglob("*.json")
    )


def test_oidc_invalid_token_is_401_and_key_source_failure_is_503(
    tmp_path: Path,
) -> None:
    private_key, verifier = _identity_components()
    client = _client(tmp_path / "invalid", verifier=verifier)

    invalid = client.get(
        "/v1/pipelines",
        headers={"Authorization": "Bearer malformed-token"},
    )
    assert invalid.status_code == 401
    assert invalid.json()["code"] == "invalid_bearer_token"

    _, unavailable_verifier = _identity_components(
        policy_jwks_uri="https://identity.example.test/unavailable-jwks.json"
    )
    unavailable = _client(tmp_path / "unavailable", verifier=unavailable_verifier)
    response = unavailable.get(
        "/v1/pipelines",
        headers={"Authorization": f"Bearer {_access_token(private_key)}"},
    )
    assert response.status_code == 503
    assert response.json()["code"] == "authentication_unavailable"
    assert "jwks" not in response.text.casefold()
